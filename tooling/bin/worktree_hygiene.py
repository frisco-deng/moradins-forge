from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from worktree_retirement import verify_archive_retirement


WORKTREE_DISPOSITIONS = {
    "merged_exact_tree",
    "stacked_redundant",
    "active_dirty",
    "active_process",
    "recent_unmerged",
    "stale_unmerged",
    "detached_release_evidence",
    "prunable_registration",
    "uncertain",
}
REMOVABLE_DISPOSITIONS = {"merged_exact_tree", "stacked_redundant", "prunable_registration"}


def _expand_reviewed_path(value: str, *, workspace_root: Path | None) -> Path | None:
    expanded = value
    if workspace_root is not None:
        expanded = expanded.replace("${WORKSPACE_ROOT}", workspace_root.resolve().as_posix())
    expanded = expanded.replace("${HOME}", Path.home().resolve().as_posix())
    if "${" in expanded or "%USERPROFILE%" in expanded:
        return None
    return Path(expanded).expanduser()


def _run(
    cwd: Path,
    *args: str,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _git_value(cwd: Path, *args: str) -> str:
    result = _run(cwd, *args)
    return result.stdout.strip() if result.returncode == 0 else ""


def _parse_worktree_porcelain(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for raw_line in [*text.splitlines(), ""]:
        line = raw_line.strip()
        if not line:
            if current:
                rows.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key in {"bare", "detached", "locked", "prunable"}:
            current[key] = value or True
        else:
            current[key] = value
    return rows


def _process_cwds(proc_root: Path = Path("/proc")) -> dict[str, list[int]]:
    rows: dict[str, list[int]] = {}
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return rows
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            cwd = (entry / "cwd").resolve(strict=True)
        except OSError:
            continue
        rows.setdefault(cwd.as_posix(), []).append(int(entry.name))
    return rows


def process_visibility(proc_root: Path = Path("/proc"), *, owner_uids: set[int] | None = None) -> dict[str, Any]:
    """Unknown managed-owner process access is not evidence of inactivity."""
    paths: dict[str, list[int]] = {}
    unknown: set[int] = set()
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return {"known": False, "paths": {}, "unknown_pids": [0]}
    try:
        if (proc_root / "1/comm").read_text(encoding="utf-8").strip() not in {"init", "systemd"}:
            unknown.add(0)
    except OSError:
        unknown.add(0)
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            if entry.stat().st_uid not in (owner_uids if owner_uids is not None else {os.getuid(), 1000, 1001}):
                continue
            references = [Path(os.readlink(entry / "cwd").removesuffix(" (deleted)"))]
            descriptors = list((entry / "fd").iterdir())
            if len(descriptors) > 4096:
                unknown.add(pid)
            for descriptor in descriptors[:4096]:
                try:
                    value = os.readlink(descriptor)
                except FileNotFoundError:
                    continue
                if value.startswith("/"):
                    references.append(Path(value.removesuffix(" (deleted)")))
            for line in (entry / "maps").read_text(encoding="utf-8").splitlines():
                columns = line.split(maxsplit=5)
                if len(columns) == 6 and columns[5].startswith("/"):
                    references.append(Path(columns[5].removesuffix(" (deleted)")))
            for reference in references:
                paths.setdefault(reference.as_posix(), []).append(pid)
        except OSError:
            if entry.exists():
                unknown.add(pid)
    return {"known": not unknown, "paths": paths, "unknown_pids": sorted(unknown)}


def _matching_processes(path: Path, process_cwds: dict[str, list[int]]) -> list[int]:
    target = path.resolve().as_posix()
    matched: set[int] = set()
    for cwd, pids in process_cwds.items():
        if cwd == target or cwd.startswith(target.rstrip("/") + "/"):
            matched.update(pids)
    return sorted(matched)


def consumer_visibility() -> dict[str, Any]:
    """Probe only caller-owned rootless Docker; other runtimes remain unknown."""
    evidence = process_visibility()
    evidence["mounts"] = []
    evidence["container_visibility_known"] = False
    try:
        context = subprocess.run(["docker", "context", "inspect"], capture_output=True, text=True, timeout=10, check=True)
        rows = json.loads(context.stdout)
        endpoint = rows[0]["Endpoints"]["docker"]["Host"]
        # Never fall through to the privileged socket or a different user's daemon.
        if endpoint.startswith(f"unix:///run/user/{os.getuid()}/") and not os.environ.get("DOCKER_HOST"):
            listed = subprocess.run(["docker", "ps", "-aq"], capture_output=True, text=True, timeout=10, check=True)
            ids = listed.stdout.split()
            containers = []
            if ids:
                inspected = subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True, timeout=10, check=True)
                containers = json.loads(inspected.stdout)
            evidence["mounts"] = [mount["Source"] for row in containers for mount in row.get("Mounts", []) if mount.get("Source")]
            # A same-user probe cannot establish cross-user container safety.
            evidence["container_visibility_known"] = not ({1000, 1001} - {os.getuid()})
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        pass
    evidence["known"] = bool(evidence["known"] and evidence["container_visibility_known"])
    return evidence


def consumer_in_use(path: Path, evidence: dict[str, Any]) -> bool:
    if _matching_processes(path, evidence.get("paths", {})):
        return True
    target = path.resolve()
    return any(target == Path(value) or target.is_relative_to(Path(value)) or Path(value).is_relative_to(target)
               for value in evidence.get("mounts", []))


def _disk_usage_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    result = subprocess.run(
        ["du", "-s", "-B1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        try:
            return int(result.stdout.split()[0])
        except (IndexError, ValueError):
            pass
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += (Path(root) / name).lstat().st_size
            except OSError:
                continue
    return total


def _iso_to_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    if not ancestor or not descendant or ancestor == descendant:
        return False
    return _run(repo_root, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _tree_equal(repo_root: Path, left: str, right: str) -> bool | None:
    if not left or not right:
        return None
    if _run(repo_root, "cat-file", "-e", f"{left}^{{commit}}").returncode != 0:
        return None
    if _run(repo_root, "cat-file", "-e", f"{right}^{{commit}}").returncode != 0:
        return None
    return _run(repo_root, "diff", "--quiet", left, right, "--").returncode == 0


def _origin_slug(repo_root: Path) -> str:
    remote = _git_value(repo_root, "remote", "get-url", "origin")
    if not remote:
        return ""
    value = remote.removesuffix(".git")
    if value.startswith("git@") and ":" in value:
        return value.split(":", 1)[1]
    if ":" in value and "/" not in value.split(":", 1)[0]:
        possible = value.split(":", 1)[1]
        if possible.count("/") == 1:
            return possible
    marker = "github.com/"
    if marker in value:
        return value.split(marker, 1)[1]
    return ""


def github_pr_for_branch(repo_root: Path, branch: str) -> dict[str, Any]:
    if not branch:
        return {"status": "not_applicable", "state": "", "number": 0, "merge_commit": ""}
    slug = _origin_slug(repo_root)
    if not slug:
        return {"status": "unavailable", "state": "", "number": 0, "merge_commit": ""}
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            slug,
            "--head",
            branch,
            "--state",
            "all",
            "--limit",
            "20",
            "--json",
            "number,state,mergedAt,mergeCommit,url",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {"status": "unavailable", "state": "", "number": 0, "merge_commit": ""}
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "unavailable", "state": "", "number": 0, "merge_commit": ""}
    if not isinstance(rows, list) or not rows:
        return {"status": "available", "state": "NONE", "number": 0, "merge_commit": ""}
    row = next((item for item in rows if isinstance(item, dict) and item.get("state") == "MERGED"), rows[0])
    merge_commit = row.get("mergeCommit") if isinstance(row, dict) else {}
    return {
        "status": "available",
        "state": str(row.get("state") or "") if isinstance(row, dict) else "",
        "number": int(row.get("number") or 0) if isinstance(row, dict) else 0,
        "merge_commit": str(merge_commit.get("oid") or "") if isinstance(merge_commit, dict) else "",
        "url": str(row.get("url") or "") if isinstance(row, dict) else "",
    }


def worktree_plan_digest(row: dict[str, Any]) -> str:
    critical = {
        "canonical_repo": row.get("canonical_repo", ""),
        "path": row.get("path", ""),
        "head": row.get("head", ""),
        "branch": row.get("branch", ""),
        "dirty": bool(row.get("dirty")),
        "dirty_count": int(row.get("dirty_count") or 0),
        "process_pids": sorted(int(pid) for pid in row.get("process_pids", [])),
        "process_visibility_known": row.get("process_visibility_known"),
        "process_unknown_pids": row.get("process_unknown_pids", []),
        "status_known": row.get("status_known"),
        "pr_state": row.get("pr_state", ""),
        "pr_merge_commit": row.get("pr_merge_commit", ""),
        "exact_tree_equal": row.get("exact_tree_equal"),
        "disposition": row.get("disposition", ""),
        "registration_prunable": bool(row.get("registration_prunable")),
    }
    return hashlib.sha256(json.dumps(critical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _classify(
    *,
    exists: bool,
    dirty: bool,
    process_pids: list[int],
    detached: bool,
    registration_prunable: bool,
    pr_state: str,
    exact_tree_equal: bool | None,
    stacked_into: str,
    age_days: float | None,
    github_status: str,
) -> tuple[str, str]:
    if registration_prunable or not exists:
        return "prunable_registration", "git worktree prune --expire now"
    if dirty:
        return "active_dirty", "preserve or hand off dirty work before cleanup"
    if process_pids:
        return "active_process", "stop or restart the process from a neutral directory"
    if detached:
        return "detached_release_evidence", "retain until immutable replacement evidence exists"
    if pr_state == "MERGED" and exact_tree_equal is True:
        return "merged_exact_tree", "remove the clean worktree through a reviewed plan"
    if stacked_into:
        return "stacked_redundant", "remove after confirming the containing branch remains preserved"
    if pr_state == "MERGED" and exact_tree_equal is not True:
        return "uncertain", "inspect post-merge commits or tree differences before removal"
    if github_status == "unavailable":
        return "uncertain", "restore GitHub evidence or prove preservation locally"
    if age_days is not None and age_days >= 30:
        return "stale_unmerged", "archive or preserve the branch before removing its worktree"
    return "recent_unmerged", "keep active or preserve it before cleanup"


def inspect_repo_worktrees(
    canonical_repo: Path,
    *,
    default_branch: str = "main",
    include_github: bool = False,
    process_cwds: dict[str, list[int]] | None = None,
    process_evidence: dict[str, Any] | None = None,
    now: datetime | None = None,
    pr_lookup: Callable[[Path, str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    canonical_repo = canonical_repo.resolve()
    listed = _run(canonical_repo, "worktree", "list", "--porcelain")
    if listed.returncode != 0:
        return []
    raw_rows = _parse_worktree_porcelain(listed.stdout)
    if not raw_rows:
        return []
    primary_path = Path(str(raw_rows[0].get("worktree", canonical_repo))).resolve()
    evidence = process_evidence or (
        {"known": True, "paths": process_cwds, "unknown_pids": []}
        if process_cwds is not None else {"known": True, "paths": _process_cwds(), "unknown_pids": []}
    )
    process_map = evidence["paths"]
    timestamp = now or datetime.now(timezone.utc)
    candidate_heads = {
        str(row.get("worktree", "")): str(row.get("HEAD", ""))
        for row in raw_rows
        if str(row.get("HEAD", ""))
    }
    result: list[dict[str, Any]] = []
    for raw in raw_rows:
        path = Path(str(raw.get("worktree", ""))).expanduser()
        if path.resolve() == primary_path:
            continue
        exists = path.exists()
        head = str(raw.get("HEAD", ""))
        branch_ref = str(raw.get("branch", ""))
        branch = branch_ref.removeprefix("refs/heads/")
        detached = bool(raw.get("detached")) or not branch
        registration_prunable = bool(raw.get("prunable")) or not exists
        dirty_lines: list[str] = []
        status_known = not exists
        if exists:
            status = _run(path, "status", "--porcelain=v1", "--untracked-files=all")
            if status.returncode == 0:
                status_known = True
                dirty_lines = [line for line in status.stdout.splitlines() if line]
        upstream = _git_value(canonical_repo, "for-each-ref", "--format=%(upstream:short)", branch_ref) if branch_ref else ""
        committed_at = _git_value(canonical_repo, "show", "-s", "--format=%cI", head)
        committed_dt = _iso_to_datetime(committed_at)
        age_days = round((timestamp - committed_dt).total_seconds() / 86400, 2) if committed_dt else None
        pids = _matching_processes(path, process_map) if exists else []
        stacked_into = ""
        for other_path, other_head in candidate_heads.items():
            if other_path != str(raw.get("worktree", "")) and _is_ancestor(canonical_repo, head, other_head):
                stacked_into = other_head
                break
        target_ref = f"refs/remotes/origin/{default_branch}"
        if not _git_value(canonical_repo, "rev-parse", "--verify", target_ref):
            target_ref = f"refs/heads/{default_branch}"
        if not stacked_into and _is_ancestor(canonical_repo, head, target_ref):
            stacked_into = target_ref
        pr = (
            (pr_lookup or github_pr_for_branch)(canonical_repo, branch)
            if include_github
            else {"status": "not_requested", "state": "", "number": 0, "merge_commit": ""}
        )
        exact_tree = _tree_equal(canonical_repo, head, str(pr.get("merge_commit", "")))
        disposition, next_action = _classify(
            exists=exists,
            dirty=bool(dirty_lines),
            process_pids=pids,
            detached=detached,
            registration_prunable=registration_prunable,
            pr_state=str(pr.get("state", "")),
            exact_tree_equal=exact_tree,
            stacked_into=stacked_into,
            age_days=age_days,
            github_status=str(pr.get("status", "")),
        )
        if exists and not status_known:
            disposition, next_action = "uncertain", "resolve unreadable Git status before retirement"
        elif exists and not evidence["known"] and disposition not in {"active_dirty", "active_process", "detached_release_evidence"}:
            disposition, next_action = "uncertain", "resolve unknown managed-owner process visibility before retirement"
        row: dict[str, Any] = {
            "canonical_repo": canonical_repo.as_posix(),
            "path": path.resolve().as_posix() if exists else path.absolute().as_posix(),
            "branch": branch,
            "head": head,
            "upstream": upstream,
            "exists": exists,
            "dirty": bool(dirty_lines),
            "dirty_count": len(dirty_lines),
            "detached": detached,
            "registration_prunable": registration_prunable,
            "process_pids": pids,
            "process_cwd_in_use": bool(pids),
            "process_visibility_known": bool(evidence["known"]),
            "process_unknown_pids": evidence["unknown_pids"],
            "status_known": status_known,
            "head_committed_at": committed_at,
            "age_days": age_days,
            "size_bytes": _disk_usage_bytes(path) if exists else 0,
            "github_status": str(pr.get("status", "")),
            "pr_state": str(pr.get("state", "")),
            "pr_number": int(pr.get("number") or 0),
            "pr_merge_commit": str(pr.get("merge_commit", "")),
            "exact_tree_equal": exact_tree,
            "stacked_into": stacked_into,
            "disposition": disposition,
            "next_action": next_action,
        }
        row["plan_digest"] = worktree_plan_digest(row)
        result.append(row)
    return result


def inspect_workspace_worktrees(
    repos: Iterable[tuple[Path, str]],
    *,
    include_github: bool = False,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    process_evidence = consumer_visibility()
    rows: list[dict[str, Any]] = []
    seen_common_dirs: set[str] = set()
    for repo_root, default_branch in repos:
        repo_root = repo_root.resolve()
        common_dir = _git_value(repo_root, "rev-parse", "--git-common-dir")
        if not common_dir:
            continue
        common_path = Path(common_dir)
        if not common_path.is_absolute():
            common_path = (repo_root / common_path).resolve()
        key = common_path.as_posix()
        if key in seen_common_dirs:
            continue
        seen_common_dirs.add(key)
        rows.extend(
            inspect_repo_worktrees(
                repo_root,
                default_branch=default_branch or "main",
                include_github=include_github,
                process_evidence=process_evidence,
                now=now,
            )
        )
    return sorted(rows, key=lambda row: str(row.get("path", "")))


def removal_actions(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for row in rows:
        if row.get("disposition") not in REMOVABLE_DISPOSITIONS:
            continue
        actions.append(
            {
                "id": f"worktree:{row.get('path', '')}",
                "type": "remove_registered_worktree",
                "scope": "worktree_lifecycle",
                "source_path": row.get("path", ""),
                "canonical_repo": row.get("canonical_repo", ""),
                "safety": "reviewed_worktree_remove",
                "requires_review": True,
                "apply_supported": True,
                "status": "planned",
                "expected_plan_digest": row.get("plan_digest", ""),
                "expected_disposition": row.get("disposition", ""),
                "rationale": "worktree is clean and has preservation evidence",
            }
        )
    return actions


def apply_worktree_removal(
    action: dict[str, Any],
    *,
    workspace_root: Path | None = None,
    pr_lookup: Callable[[Path, str], dict[str, Any]] | None = None,
    process_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_path = _expand_reviewed_path(str(action.get("canonical_repo", "")), workspace_root=workspace_root)
    target = _expand_reviewed_path(str(action.get("source_path", "")), workspace_root=workspace_root)
    if canonical_path is None or target is None:
        return {"id": action.get("id"), "status": "refused", "reason": "unresolved_path_placeholder"}
    canonical = canonical_path.resolve()
    if not canonical.exists():
        return {"id": action.get("id"), "status": "refused", "reason": "canonical_repo_missing"}
    current_rows = inspect_repo_worktrees(canonical, include_github=True, pr_lookup=pr_lookup, process_evidence=process_evidence)
    target_key = target.resolve().as_posix() if target.exists() else target.absolute().as_posix()
    row = next((item for item in current_rows if item.get("path") == target_key), None)
    if row is None:
        return {"id": action.get("id"), "status": "refused", "reason": "worktree_registration_changed"}
    if row.get("plan_digest") != action.get("expected_plan_digest"):
        return {"id": action.get("id"), "status": "refused", "reason": "plan_digest_mismatch"}
    proof = action.get("retirement_proof", {})
    archived = proof.get("mode") == "archive_reviewed"
    if archived:
        try:
            verify_archive_retirement(canonical, target, str(row.get("head", "")), proof)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            return {"id": action.get("id"), "status": "refused", "reason": str(error)}
    if row.get("disposition") not in REMOVABLE_DISPOSITIONS and not archived:
        return {"id": action.get("id"), "status": "refused", "reason": "disposition_not_removable"}
    if not row.get("status_known") or not row.get("process_visibility_known"):
        return {"id": action.get("id"), "status": "refused", "reason": "consumer_or_status_visibility_unknown"}
    if row.get("dirty"):
        return {"id": action.get("id"), "status": "refused", "reason": "worktree_dirty"}
    if row.get("process_cwd_in_use"):
        return {"id": action.get("id"), "status": "refused", "reason": "worktree_process_in_use"}
    if row.get("detached") and not archived:
        return {"id": action.get("id"), "status": "refused", "reason": "detached_release_evidence"}
    if not archived and (proof.get("task_completed") is not True or proof.get("head") != row.get("head")):
        return {"id": action.get("id"), "status": "refused", "reason": "completed_task_proof_required"}
    if not archived and (not proof.get("published_evidence_index") or not proof.get("published_evidence_commit")):
        return {"id": action.get("id"), "status": "refused", "reason": "published_preservation_index_required"}
    # Ignored environments and evidence are not covered by clean Git status.
    ignored = _run(target, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    if ignored.returncode or (ignored.stdout and not archived):
        return {"id": action.get("id"), "status": "refused", "reason": "ignored_content_requires_separate_preservation_plan"}
    try:
        if not archived:
            evidence_index = Path(str(proof["published_evidence_index"]))
            if evidence_index.is_symlink() or hashlib.sha256(evidence_index.read_bytes()).hexdigest() != proof.get("index_sha256"):
                raise ValueError("preservation index changed")
            record = json.loads(evidence_index.read_text())
            if record.get("head") != row.get("head") or record.get("task_completed") is not True:
                raise ValueError("preservation index does not prove task completion")
            published = _run(canonical, "show", f"{proof['published_evidence_commit']}:{proof['index_repo_path']}")
            remote = _run(canonical, "ls-remote", "--exit-code", "origin", f"refs/heads/{proof['published_branch']}")
            if published.returncode or not remote.stdout.strip() or hashlib.sha256(published.stdout.encode()).hexdigest() != proof["index_sha256"]:
                raise ValueError("index not published")
            remote_head = remote.stdout.split()[0]
            if proof["published_evidence_commit"] != remote_head and not _is_ancestor(canonical, str(proof["published_evidence_commit"]), remote_head):
                raise ValueError("index commit not on published branch")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return {"id": action.get("id"), "status": "refused", "reason": "preservation_index_unverified"}
    if consumer_in_use(target, process_evidence or consumer_visibility()):
        return {"id": action.get("id"), "status": "refused", "reason": "worktree_consumer_in_use"}
    if target.exists():
        for root, directories, files in os.walk(target, followlinks=False):
            if Path(root) != target and (".git" in directories or ".git" in files):
                return {"id": action.get("id"), "status": "refused", "reason": "nested_checkout_requires_separate_preservation"}
            directories[:] = [name for name in directories if name != ".git"]
    if row.get("registration_prunable"):
        return {"id": action.get("id"), "status": "refused", "reason": "global_registration_prune_requires_separate_plan"}
    else:
        result = _run(canonical, "worktree", "remove", str(target))
    if result.returncode != 0:
        # Native Git can remove its registration even when filesystem cleanup
        # fails. A nonzero exit must never imply that no mutation occurred.
        remaining = _parse_worktree_porcelain(_git_value(canonical, "worktree", "list", "--porcelain"))
        return {
            "id": action.get("id"),
            "status": "reconcile_required",
            "reason": "git_worktree_remove_failed",
            "detail": result.stderr.strip()[:500],
            "registration_remaining": any(item.get("worktree") == target_key for item in remaining),
            "path_remaining": target.exists(),
            "preserved_head": row.get("head"),
            "archive_path": proof.get("archive_path"),
            "archive_sha256": proof.get("archive_sha256"),
        }
    return {"id": action.get("id"), "status": "applied", "path": target_key}
