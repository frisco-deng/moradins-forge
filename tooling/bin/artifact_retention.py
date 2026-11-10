"""Retention for explicitly completed, immutable, repo-owned run bundles."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
try:
    import fcntl
except ImportError:
    fcntl = None
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import uuid
from typing import Any

from worktree_hygiene import consumer_in_use, consumer_visibility

SCHEMA = "completed-artifact-retention-v1"
MARKER = ".retention.json"
MODEL_SUFFIXES = {".safetensors", ".gguf", ".ckpt", ".pth", ".pt", ".onnx"}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)


def safe_path(repo: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or any(part in {"..", ".git"} for part in relative.parts):
        raise ValueError("unsafe relative path")
    current = repo
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink path component")
    if not current.resolve().is_relative_to(repo.resolve()):
        raise ValueError("path escapes repository")
    return current


def load_policy(repo: Path, policy_path: Path) -> dict[str, Any]:
    if policy_path.is_symlink():
        raise ValueError("symlink policy")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("schema_version") != 1 or policy.get("approved") is not True:
        raise ValueError("retention policy is not approved")
    if int(policy.get("retention_days", 30)) < 30 or int(policy.get("keep_latest", 3)) < 3:
        raise ValueError("policy weakens approved 30-day/latest-three minimum")
    roots = policy.get("roots", [])
    if not roots:
        raise ValueError("no declared artifact roots")
    for value in roots:
        path = safe_path(repo, value)
        if Path(value).parts[0] not in {"artifacts", "outputs", "runs", "logs"}:
            raise ValueError("not a declared generated-output root")
        if not _git(repo, "check-ignore", "--quiet", str(path / ".retention-probe")).returncode == 0:
            raise ValueError("artifact root is not ignored")
    return policy


def _identity(path: Path) -> list[int]:
    value = path.lstat()
    return [value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink]


def tree_inventory(root: Path) -> tuple[list[dict[str, Any]], int]:
    files = []
    links: Counter[tuple[int, int]] = Counter()
    allocation: dict[tuple[int, int], tuple[int, int]] = {}
    def unreadable(error: OSError) -> None:
        raise error

    for current, directories, names in os.walk(root, followlinks=False, onerror=unreadable):
        if ".git" in directories or ".git" in names:
            raise ValueError("nested checkout")
        for name in directories:
            if (Path(current) / name).is_symlink():
                raise ValueError("symlink in run bundle")
        for name in sorted(names):
            path = Path(current) / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or path.suffix.lower() in MODEL_SUFFIXES:
                raise ValueError("special file or model in run bundle")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            files.append({"path": path.relative_to(root).as_posix(), "identity": _identity(path), "sha256": digest})
            key = (info.st_dev, info.st_ino)
            links[key] += 1
            allocation[key] = (info.st_blocks * 512, info.st_nlink)
    total = sum(size for key, (size, count) in allocation.items() if links[key] >= count)
    return sorted(files, key=lambda row: row["path"]), total


def lesson_published(repo: Path, lesson: dict[str, Any]) -> bool:
    try:
        path = safe_path(repo, lesson["path"])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != lesson["sha256"]:
            return False
        commit = lesson["commit"]
        branch = lesson["branch"]
        if not commit or not branch or branch.startswith("-"):
            return False
        committed = _git(repo, "show", f"{commit}:{lesson['path']}")
        if committed.returncode or hashlib.sha256(committed.stdout.encode()).hexdigest() != digest:
            return False
        remote = _git(repo, "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}")
        if remote.returncode or not remote.stdout.strip():
            return False
        remote_head = remote.stdout.split()[0]
        return _git(repo, "merge-base", "--is-ancestor", commit, remote_head).returncode == 0
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        return False


def _referenced(repo: Path, path: Path, policy: dict[str, Any]) -> bool:
    relative = path.relative_to(repo).as_posix()
    result = _git(repo, "grep", "--untracked", "--exclude-standard", "-F", "-l", "-e", relative, "-e", str(path), "--", ".")
    if result.returncode != 1:
        return True
    for value in policy.get("reference_indexes", []):
        index = safe_path(repo, value)
        if index.exists():
            if index.is_dir():
                indexes = list(index.glob("*.json"))
            else:
                indexes = [index]
            for item in indexes:
                if item.is_symlink() or item.stat().st_size > 2 * 1024**2:
                    return True
                text = item.read_text(encoding="utf-8")
                if relative in text or str(path) in text:
                    return True
    return False


def plan_retention(repo: Path, policy_path: Path, *, now: float | None = None,
                   consumer_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    repo = repo.resolve()
    policy = load_policy(repo, policy_path)
    stamp = time.time() if now is None else now
    consumers = consumer_evidence if consumer_evidence is not None else consumer_visibility()
    rows = []
    seen: set[Path] = set()
    for value in policy["roots"]:
        artifact_root = safe_path(repo, value)
        for current, directories, files in os.walk(artifact_root, followlinks=False):
            directories[:] = [name for name in directories if name not in {".git", ".venv", "node_modules", "data", "datasets", "models"}
                              and not (Path(current) / name).is_symlink()]
            if MARKER not in files:
                continue
            path = Path(current)
            if path in seen:
                continue
            seen.add(path)
            row = {"path": path.relative_to(repo).as_posix(), "holds": []}
            try:
                safe_path(repo, row["path"])
                if (path / MARKER).is_symlink():
                    raise ValueError("symlink completion marker")
                metadata = json.loads((path / MARKER).read_text(encoding="utf-8"))
                row.update(workflow=metadata["workflow"], completed_at=float(metadata["completed_at"]), metadata=metadata)
                if not isinstance(row["workflow"], str) or not row["workflow"].strip() or not math.isfinite(row["completed_at"]) or row["completed_at"] <= 0:
                    raise ValueError("invalid workflow or completion time")
                row["metadata_valid"] = True
                if metadata.get("schema_version") != 1 or metadata.get("immutable") is not True:
                    row["holds"].append("unclassified_or_mutable")
                if metadata.get("status") != "pass" or metadata.get("holds") or metadata.get("references") or any(
                    metadata.get(flag) for flag in ("protected", "accepted", "baseline", "release_evidence", "dataset", "fixture", "reproducibility_input", "unresolved")
                ):
                    row["holds"].append("failed_incomplete_accepted_referenced_or_explicit_hold")
                if row["completed_at"] > stamp or stamp - row["completed_at"] <= int(policy.get("retention_days", 30)) * 86400:
                    row["holds"].append("retention_window")
                if not consumers.get("known", False):
                    row["holds"].append("consumer_visibility_unknown")
                elif consumer_in_use(path, consumers):
                    row["holds"].append("active_consumer")
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                row["holds"].append("metadata_or_reference_unreadable")
            rows.append(row)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("metadata_valid") and row.get("metadata", {}).get("schema_version") == 1 and row.get("metadata", {}).get("status") == "pass":
            grouped.setdefault(row["workflow"], []).append(row)
    for group in grouped.values():
        for row in sorted(group, key=lambda item: (-item["completed_at"], item["path"]))[:int(policy.get("keep_latest", 3))]:
            row["holds"].append("latest_completed_runs")
    actions = []
    publication_cache: dict[str, bool] = {}
    for row in rows:
        if row["holds"]:
            continue
        path = safe_path(repo, row["path"])
        try:
            if _referenced(repo, path, policy):
                row["holds"].append("external_reference")
                continue
            lesson = row["metadata"].get("published_lesson", {})
            lesson_key = json.dumps(lesson, sort_keys=True)
            if lesson_key not in publication_cache:
                publication_cache[lesson_key] = lesson_published(repo, lesson)
            if not publication_cache[lesson_key]:
                row["holds"].append("lesson_not_published")
                continue
            files, allocated = tree_inventory(path)
            if any(other != path and other.is_relative_to(path) for other in seen):
                raise ValueError("nested completed run requires separate review")
            actions.append({"type": "remove_completed_artifact", "path": row["path"], "root_identity": _identity(path),
                            "files": files, "allocated_bytes": allocated, "workflow": row["workflow"],
                            "owner": policy.get("owner", str(repo)), "eligibility": "completed_pass_outside_retention_union",
                            "dependencies": {"references_clear": True, "consumer_visibility_known": True},
                            "preservation": lesson})
        except (OSError, ValueError):
            row["holds"].append("unsafe_bundle_or_nested_run")
    return {"schema_version": SCHEMA, "reviewed": False, "created_at": stamp, "repo": str(repo),
            "policy_path": str(policy_path.resolve()), "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
            "actions": actions, "runs": rows, "consumer_unknown_pids": consumers.get("unknown_pids", []),
            "estimated_allocated_bytes": sum(action["allocated_bytes"] for action in actions)}


def apply_retention(plan: dict[str, Any], ledger_path: Path, *,
                    consumer_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    if fcntl is None:
        raise ValueError("native locking unavailable; retention is report-only")
    if plan.get("schema_version") != SCHEMA or plan.get("reviewed") is not True:
        raise ValueError("unreviewed retention plan")
    if not 0 <= time.time() - plan["created_at"] <= 86400:
        raise ValueError("stale retention plan")
    repo = Path(plan["repo"]).resolve()
    policy_path = Path(plan["policy_path"])
    if hashlib.sha256(policy_path.read_bytes()).hexdigest() != plan["policy_sha256"]:
        raise ValueError("retention policy changed")
    digest = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    lock_path = repo / "artifacts/retention/.lock"
    safe_path(repo, "artifacts/retention/.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = {"schema_version": SCHEMA, "plan_sha256": digest, "actions": []}
        if ledger_path.exists():
            ledger = json.loads(ledger_path.read_text())
            if ledger["plan_sha256"] != digest:
                raise ValueError("ledger belongs to another plan")
            if all(row["status"] == "deleted" and not safe_path(repo, row["path"]).exists() for row in ledger["actions"]) and len(ledger["actions"]) == len(plan["actions"]):
                return ledger
            raise ValueError("interrupted or changed execution requires reconciliation")
        current = plan_retention(repo, policy_path, now=plan["created_at"], consumer_evidence=consumer_evidence)
        if current["actions"] != plan["actions"]:
            raise ValueError("file identity, preservation or consumers changed")
        write_json(ledger_path, ledger)
        for action in plan["actions"]:
            path = safe_path(repo, action["path"])
            consumers = consumer_evidence if consumer_evidence is not None else consumer_visibility()
            if not consumers.get("known") or consumer_in_use(path, consumers):
                raise ValueError("consumer visibility changed immediately before deletion")
            policy = load_policy(repo, policy_path)
            if _referenced(repo, path, policy) or not lesson_published(repo, action["preservation"]):
                raise ValueError("references or preservation changed immediately before deletion")
            row = {"path": action["path"], "status": "running", "started_at": time.time()}
            ledger["actions"].append(row)
            write_json(ledger_path, ledger)
            parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            tombstone = ".retention-delete-" + uuid.uuid4().hex
            try:
                if _identity(path) != action["root_identity"] or tree_inventory(path)[0] != action["files"]:
                    raise ValueError("run changed immediately before deletion")
                os.rename(path.name, tombstone, src_dir_fd=parent, dst_dir_fd=parent)
                row["tombstone"] = str(path.parent / tombstone)
                write_json(ledger_path, ledger)
                if _identity(path.parent / tombstone)[:3] != action["root_identity"][:3]:
                    raise ValueError("renamed directory identity changed")
                shutil.rmtree(tombstone, dir_fd=parent)
                os.fsync(parent)
                row.update(status="deleted", finished_at=time.time())
                write_json(ledger_path, ledger)
            finally:
                os.close(parent)
        return ledger


def finalize_run(repo: Path, artifact_dir: Path, summary: dict[str, Any], policy_path: Path) -> dict[str, Any]:
    """Snapshot only owned summaries/logs; do not alter the primary run status."""
    policy = load_policy(repo, policy_path)
    relative = artifact_dir.resolve().relative_to(repo.resolve()).as_posix()
    safe_path(repo, relative)
    if not any(artifact_dir.resolve().is_relative_to(safe_path(repo, root).resolve()) for root in policy["roots"]):
        raise ValueError("run outside declared retention roots")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    snapshot = policy.get("snapshot_runs") is True
    bundle = artifact_dir / "runs" / run_id if snapshot else artifact_dir
    if snapshot:
        bundle.mkdir(parents=True)
        for name in ("summary.json", "summary.md"):
            source = artifact_dir / name
            if source.exists():
                if source.is_symlink():
                    raise ValueError("symlink summary")
                shutil.copy2(source, bundle / name)
        logs = artifact_dir / "logs"
        if logs.exists():
            before_logs = tree_inventory(logs)[0]
            shutil.copytree(logs, bundle / "logs")
            if tree_inventory(logs)[0] != before_logs:
                raise ValueError("logs changed while snapshotting")
    signature = str(summary.get("analysis", {}).get("run_signature", ""))
    holds = ["release_or_security_evidence"] if any(word in str(summary.get("target", "")) for word in ("release", "security", "production", "candidate", "baseline")) else []
    if not snapshot:
        holds.append("current_flat_reader")
    write_json(bundle / MARKER, {"schema_version": 1, "workflow": summary["target"], "completed_at": time.time(),
        "status": summary["status"], "immutable": snapshot, "holds": holds, "references": [],
        "published_lesson": policy.get("published_lessons", {}).get(signature, {}),
        "repo_commit": summary.get("git", {}).get("head_sha"), "run_signature": signature})
    plan = plan_retention(repo, policy_path)
    evidence = repo / "artifacts/retention" / run_id
    write_json(evidence / "plan.json", plan)
    outcome = {"status": "planned", "bundle": str(bundle), "plan": str(evidence / "plan.json"),
               "eligible_count": len(plan["actions"]), "held_count": len(plan["runs"]) - len(plan["actions"])}
    if policy.get("apply_after_run") is True:
        plan["reviewed"] = True
        write_json(evidence / "plan.json", plan)
        ledger = apply_retention(plan, evidence / "ledger.json")
        outcome.update(status="applied", deleted_count=len(ledger["actions"]))
    write_json(evidence / "summary.json", outcome)
    return outcome
