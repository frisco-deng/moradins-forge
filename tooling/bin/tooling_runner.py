#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from python_runtime import route_advice as python_route_advice, runtime_info as python_runtime_info  # noqa: E402


SCHEMA_VERSION = 1
SHELL = "/bin/bash"
RESERVED_SHELL_WORDS = {
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "for",
    "do",
    "done",
    "while",
    "case",
    "esac",
    "function",
    "export",
    "local",
    "test",
    "[",
    "[[",
    "time",
}
WORKSPACE_ROOT_PLACEHOLDER = "${WORKSPACE_ROOT}"
LOCAL_BIN_DIR = Path.home() / ".local" / "bin"
DOMAIN_LANE_HINTS = {
    "meta-rag": "for demo and status work, start with `make demo-brief`, then `make verify-demo-fast`",
    "waifu-stack": "for Plan V2 start with `make v2-brief`; for harvest work start with `make sample-library-brief`",
    "aiproject": "for runtime and profile work, start with `make runtime-brief`, then `make verify-profile-small`",
    "waifu-ui": "for repo state, prefer `make repo-brief` and `npm run status:dev` before raw dashboard polling",
    "moradins-forge": "for Forge work, start with `make forge-explain`, then `make payload-validate` or `make public-portability-check` before broader gates",
}
HEAVY_RERUN_TARGETS = {
    "review-bundle",
    "review-ready",
    "release-gate-local",
    "verify-fast",
    "verify",
    "verify-ci",
    "verify-container",
    "ci-local",
    "sbom",
}
CACHEABLE_STEP_TARGETS = {"verify-security"}
CACHEABLE_STEP_CATEGORIES = {"secret-scan", "security-scan", "workflow", "dependency-scan", "sbom", "container"}
SECURITY_EVIDENCE_CATEGORIES = [
    "sast",
    "sca",
    "secrets",
    "iac_misconfig",
    "workflow_policy",
    "sbom",
    "license",
    "exceptions",
]
STATE_HASH_FILE_SIZE_LIMIT_BYTES = 2_000_000
STATE_HASH_TOTAL_SIZE_LIMIT_BYTES = 10_000_000
STATE_HASH_FILE_COUNT_LIMIT = 200
TOOL_VERSION_TIMEOUT_SECONDS = 5
LONG_LOG_LINE_THRESHOLD = int(os.environ.get("TOOLING_LONG_LOG_LINE_THRESHOLD", "200"))
LONG_LOG_TOKEN_THRESHOLD = int(os.environ.get("TOOLING_LONG_LOG_TOKEN_THRESHOLD", "8000"))
DIAGNOSTIC_FAILURE_TERMS = (
    "nan",
    "black",
    "invalid value",
    "sampler",
    "ksampler",
    "checkpoint",
    "similar control works",
)
COMMAND_FAILURE_ADVISORIES = (
    (
        ("python: command not found", "/bin/bash: python:", "python: not found"),
        "use the repo Python route from `make repo-brief`; do not retry raw `python`",
    ),
    (
        ("no rule to make target 'fmt-md'", "no rule to make target `fmt-md`", "no rule to make target fmt-md"),
        "use the repo-local markdown/check target from `make repo-brief`; do not retry missing `make fmt-md`",
    ),
    (
        ("gh: command not found", "gh is not installed", "gh is not authenticated"),
        "use `tpl pr-status <pr-or-branch> --repo owner/name`; if local gh auth is blocked, use Codex GitHub connector/App PR metadata",
    ),
)
UI_CONFIG_NAMES = (
    "playwright.config.ts",
    "playwright.config.js",
    "playwright.config.mjs",
    "playwright.config.cjs",
    "cypress.config.ts",
    "cypress.config.js",
    "vitest.config.ts",
    "vitest.config.js",
    "vite.browser.config.ts",
    "vite.browser.config.js",
)
UI_SCRIPT_TERMS = ("browser", "e2e", "playwright", "cypress")
TOOLING_WORKFLOW_CONTEXTS = {
    "tooling-ci-core.yml": "Tooling / CI Core",
    "tooling-security-core.yml": "Tooling / Security Core",
    "tooling-docker-image.yml": "Tooling / Docker Image",
    "tooling-dependency-submission.yml": "Tooling / Dependency Submission",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def relative_or_absolute(base: Path, value: str | None, fallback: str) -> Path:
    raw = value or fallback
    path = Path(raw)
    return path if path.is_absolute() else base / path


def capture(
    command: list[str],
    *,
    cwd: Path,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def capture_version(command: list[str], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=TOOL_VERSION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    output = (result.stdout or result.stderr or "").strip().splitlines()
    return output[0].strip()[:200] if output else f"exit-{result.returncode}"


def run_shell(command: str, *, cwd: Path, log_path: Path) -> tuple[int, float]:
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            [SHELL, "-lc", command],
            cwd=cwd,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    return proc.returncode, round(time.monotonic() - start, 3)


def log_excerpt(path: Path, *, failed: bool) -> str:
    if not path.exists():
        return "no log captured"
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        return "no output"
    sample = lines[-8:] if failed else lines[:4]
    return " | ".join(sample)


def log_stats(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "full_log_path": "",
            "full_log_line_count": 0,
            "full_log_token_estimate": 0,
            "long_log_summary_required": False,
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    line_count = len(text.splitlines())
    token_estimate = max(0, len(text) // 4)
    return {
        "full_log_path": str(path),
        "full_log_line_count": line_count,
        "full_log_token_estimate": token_estimate,
        "long_log_summary_required": line_count > LONG_LOG_LINE_THRESHOLD or token_estimate > LONG_LOG_TOKEN_THRESHOLD,
    }


def parse_status(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line and not line.startswith("## ")]


def git_available(root: Path) -> bool:
    result = capture(["git", "rev-parse", "--git-dir"], cwd=root)
    return result.returncode == 0


def _split_nul_paths(stdout: str) -> list[str]:
    return [item for item in stdout.split("\0") if item]


def _hash_path_bytes(path: Path, *, remaining_bytes: int) -> tuple[dict[str, Any], int]:
    entry: dict[str, Any] = {"state": "missing"}
    try:
        stat = path.lstat()
    except FileNotFoundError:
        return entry, remaining_bytes
    entry.update(
        {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "ctime_ns": stat.st_ctime_ns,
            "is_file": path.is_file(),
            "is_symlink": path.is_symlink(),
        }
    )
    if path.is_symlink():
        entry.update({"state": "symlink", "sha256": hashlib.sha256(os.readlink(path).encode("utf-8")).hexdigest()})
        return entry, remaining_bytes
    if not path.is_file():
        entry["state"] = "non-file"
        return entry, remaining_bytes
    if stat.st_size > STATE_HASH_FILE_SIZE_LIMIT_BYTES or stat.st_size > remaining_bytes:
        entry["state"] = "content-not-hashed-size-limit"
        return entry, remaining_bytes
    try:
        data = path.read_bytes()
    except OSError as exc:
        entry.update({"state": "content-unreadable", "error": exc.__class__.__name__})
        return entry, remaining_bytes
    entry.update({"state": "content-hashed", "sha256": hashlib.sha256(data).hexdigest()})
    return entry, remaining_bytes - len(data)


def _tracked_index_blob(root: Path, raw_path: str) -> str:
    result = capture(["git", "ls-files", "-s", "--", raw_path], cwd=root)
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    first = result.stdout.splitlines()[0].split()
    return first[1] if len(first) >= 2 else ""


def _changed_tracked_paths(root: Path) -> list[str]:
    paths: set[str] = set()
    for args in (
        ["git", "diff", "--name-only", "-z", "--", "."],
        ["git", "diff", "--name-only", "--cached", "-z", "--", "."],
    ):
        result = capture(args, cwd=root)
        if result.returncode == 0:
            paths.update(_split_nul_paths(result.stdout))
    return sorted(paths)


def _tracked_content_hash(root: Path, paths: list[str]) -> tuple[str, int, bool]:
    limited = len(paths) > STATE_HASH_FILE_COUNT_LIMIT
    remaining = STATE_HASH_TOTAL_SIZE_LIMIT_BYTES
    material: list[dict[str, Any]] = []
    for raw_path in paths[:STATE_HASH_FILE_COUNT_LIMIT]:
        worktree_entry, remaining = _hash_path_bytes(root / raw_path, remaining_bytes=remaining)
        if worktree_entry.get("state") in {"content-not-hashed-size-limit", "content-unreadable"}:
            limited = True
        material.append(
            {
                "path": raw_path,
                "index_blob": _tracked_index_blob(root, raw_path),
                "worktree": worktree_entry,
            }
        )
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()[:16], len(material), limited


def _untracked_hashes(root: Path, paths: list[str]) -> tuple[str, str, int, bool]:
    limited = len(paths) > STATE_HASH_FILE_COUNT_LIMIT
    remaining = STATE_HASH_TOTAL_SIZE_LIMIT_BYTES
    metadata: list[dict[str, Any]] = []
    content: list[dict[str, Any]] = []
    for raw_path in paths[:STATE_HASH_FILE_COUNT_LIMIT]:
        path = root / raw_path
        try:
            stat = path.lstat()
        except FileNotFoundError:
            continue
        metadata.append(
            {
                "path": raw_path,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "is_file": path.is_file(),
                "is_symlink": path.is_symlink(),
            }
        )
        content_entry, remaining = _hash_path_bytes(path, remaining_bytes=remaining)
        if content_entry.get("state") in {"content-not-hashed-size-limit", "content-unreadable"}:
            limited = True
        content.append({"path": raw_path, **content_entry})
    metadata_hash = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return metadata_hash, content_hash, len(content), limited


def git_info(root: Path, repo_meta: dict[str, Any]) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "branch": "unavailable",
        "upstream": "unavailable",
        "ahead": 0,
        "behind": 0,
        "dirty": None,
        "head_sha": "",
        "untracked_count": 0,
        "untracked_hash": "",
        "untracked_content_hash": "",
        "untracked_content_hash_files": 0,
        "untracked_content_hash_limited": False,
        "diffstat_hash": "",
        "tracked_content_hash": "",
        "tracked_content_hash_files": 0,
        "tracked_content_hash_limited": False,
        "state_fingerprint": "",
        "status_lines": [],
        "stash_count": 0,
        "worktrees": [],
        "remotes": [],
        "default_branch": repo_meta.get("default_branch", ""),
        "integration_branch": repo_meta.get("integration_branch", ""),
        "production_branch": repo_meta.get("production_branch", ""),
        "protected_branch": False,
    }
    if not git_available(root):
        return info

    info["available"] = True
    branch = capture(["git", "branch", "--show-current"], cwd=root).stdout.strip()
    info["branch"] = branch or "detached"
    upstream = capture(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=root)
    if upstream.returncode == 0:
        info["upstream"] = upstream.stdout.strip()
        ahead_behind = capture(["git", "rev-list", "--left-right", "--count", f"HEAD...{info['upstream']}"], cwd=root)
        if ahead_behind.returncode == 0:
            try:
                ahead, behind = ahead_behind.stdout.strip().split()
                info["ahead"] = int(ahead)
                info["behind"] = int(behind)
            except ValueError:
                pass
    status = capture(["git", "status", "--short", "--branch"], cwd=root)
    if status.returncode == 0:
        status_lines = parse_status(status.stdout)
        info["status_lines"] = status_lines
        info["dirty"] = any(not line.startswith("## ") for line in status.stdout.splitlines())
        info["untracked_count"] = sum(1 for line in status_lines if line.startswith("?? "))
    head_sha = capture(["git", "rev-parse", "HEAD"], cwd=root)
    if head_sha.returncode == 0:
        info["head_sha"] = head_sha.stdout.strip()
    diffstat = capture(["git", "diff", "--stat", "--cached", "--", "."], cwd=root)
    worktree_diffstat = capture(["git", "diff", "--stat", "--", "."], cwd=root)
    diffstat_text = (diffstat.stdout or "") + "\n" + (worktree_diffstat.stdout or "")
    info["diffstat_hash"] = hashlib.sha256(diffstat_text.encode("utf-8")).hexdigest()[:16]
    tracked_hash, tracked_file_count, tracked_limited = _tracked_content_hash(root, _changed_tracked_paths(root))
    info["tracked_content_hash"] = tracked_hash
    info["tracked_content_hash_files"] = tracked_file_count
    info["tracked_content_hash_limited"] = tracked_limited
    untracked = capture(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root)
    if untracked.returncode == 0:
        untracked_paths = _split_nul_paths(untracked.stdout)
        metadata_hash, content_hash, content_count, content_limited = _untracked_hashes(root, untracked_paths)
        info["untracked_hash"] = metadata_hash
        info["untracked_content_hash"] = content_hash
        info["untracked_content_hash_files"] = content_count
        info["untracked_content_hash_limited"] = content_limited
    stash = capture(["git", "stash", "list"], cwd=root)
    if stash.returncode == 0:
        info["stash_count"] = len([line for line in stash.stdout.splitlines() if line.strip()])
    worktrees = capture(["git", "worktree", "list", "--porcelain"], cwd=root)
    if worktrees.returncode == 0:
        current: dict[str, str] = {}
        parsed: list[dict[str, str]] = []
        for raw in worktrees.stdout.splitlines():
            if not raw.strip():
                if current:
                    parsed.append(current)
                    current = {}
                continue
            key, _, value = raw.partition(" ")
            current[key] = value
        if current:
            parsed.append(current)
        info["worktrees"] = parsed
    remotes = capture(["git", "remote", "-v"], cwd=root)
    if remotes.returncode == 0:
        info["remotes"] = [line for line in remotes.stdout.splitlines() if line.strip()]

    protected = {item for item in (info["default_branch"], info["integration_branch"], info["production_branch"]) if item}
    info["protected_branch"] = info["branch"] in protected
    state_material = json.dumps(
        {
            "branch": info["branch"],
            "upstream": info["upstream"],
            "head_sha": info["head_sha"],
            "dirty": info["dirty"],
            "diffstat_hash": info["diffstat_hash"],
            "tracked_content_hash": info["tracked_content_hash"],
            "tracked_content_hash_limited": info["tracked_content_hash_limited"],
            "untracked_count": info["untracked_count"],
            "untracked_hash": info["untracked_hash"],
            "untracked_content_hash": info["untracked_content_hash"],
            "untracked_content_hash_limited": info["untracked_content_hash_limited"],
            "status_lines": info["status_lines"],
        },
        sort_keys=True,
    )
    info["state_fingerprint"] = hashlib.sha256(state_material.encode("utf-8")).hexdigest()[:16]
    return info


def gh_info(root: Path, current_branch: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": shutil.which("gh") is not None,
        "authenticated": False,
        "repo": None,
        "pull_request": None,
        "error": "",
    }
    if not info["available"]:
        info["error"] = "gh not installed"
        return info

    auth = capture(["gh", "auth", "status"], cwd=root)
    if auth.returncode != 0:
        info["error"] = "gh not authenticated"
        return info

    info["authenticated"] = True
    repo_view = capture(
        [
            "gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner,defaultBranchRef,isPrivate,url",
        ],
        cwd=root,
    )
    if repo_view.returncode == 0 and repo_view.stdout.strip():
        info["repo"] = json.loads(repo_view.stdout)

    if current_branch and current_branch not in {"", "detached", "unavailable"}:
        pr_list = capture(
            [
                "gh",
                "pr",
                "list",
                "--head",
                current_branch,
                "--json",
                "number,title,baseRefName,headRefName,state,isDraft,url,reviewDecision",
                "--limit",
                "1",
            ],
            cwd=root,
        )
        if pr_list.returncode == 0 and pr_list.stdout.strip():
            try:
                payload = json.loads(pr_list.stdout)
                info["pull_request"] = payload[0] if payload else None
            except json.JSONDecodeError:
                info["error"] = "unable to parse gh pr list output"
    return info


def workflow_info(root: Path) -> dict[str, Any]:
    workflow_dir = root / ".github" / "workflows"
    tooling_workflows = sorted(path.name for path in workflow_dir.glob("tooling-*.yml"))
    all_workflows = sorted(path.name for path in workflow_dir.glob("*.yml"))
    return {
        "available": workflow_dir.exists(),
        "workflow_dir": str(workflow_dir.relative_to(root)),
        "tooling_workflows": tooling_workflows,
        "all_workflows": all_workflows,
    }


def manifest_info(root: Path, repo_cfg: dict[str, Any]) -> dict[str, Any]:
    common = [
        "pyproject.toml",
        "uv.lock",
        "package.json",
        "Dockerfile",
        "compose.yaml",
        "compose.yml",
        ".pre-commit-config.yaml",
    ]
    files = {name: (root / name).exists() for name in common}
    for path in repo_cfg.get("dockerfiles", []):
        files[path] = (root / path).exists()
    for path in repo_cfg.get("compose_files", []):
        files[path] = (root / path).exists()
    for path in repo_cfg.get("npm_directories", []):
        files[f"{path}/package.json"] = (root / path / "package.json").exists()
    return files


def package_json_payload(path: Path) -> dict[str, Any]:
    payload = read_json_optional(path)
    return payload if payload else {}


def ui_cli_info(root: Path, repo_cfg: dict[str, Any], targets: dict[str, Any]) -> dict[str, Any]:
    npm_dirs = [""]
    for item in repo_cfg.get("npm_directories", []):
        if item not in npm_dirs:
            npm_dirs.append(item)
    package_jsons: list[str] = []
    browser_scripts: dict[str, list[str]] = {}
    configs: list[str] = []
    playwright_detected = False
    cypress_detected = False
    vitest_browser_detected = False

    for directory in npm_dirs:
        base = root / directory if directory else root
        package_path = base / "package.json"
        if package_path.exists():
            rel_package = str(package_path.relative_to(root))
            package_jsons.append(rel_package)
            payload = package_json_payload(package_path)
            scripts = payload.get("scripts", {})
            if isinstance(scripts, dict):
                matched = sorted(
                    name
                    for name, command in scripts.items()
                    if any(term in name.lower() or term in str(command).lower() for term in UI_SCRIPT_TERMS)
                )
                if matched:
                    browser_scripts[rel_package] = matched
            dependency_text = json.dumps(
                {
                    "dependencies": payload.get("dependencies", {}),
                    "devDependencies": payload.get("devDependencies", {}),
                },
                sort_keys=True,
            ).lower()
            playwright_detected = playwright_detected or "playwright" in dependency_text
            cypress_detected = cypress_detected or "cypress" in dependency_text
            vitest_browser_detected = vitest_browser_detected or "vitest-browser" in dependency_text or "@vitest/browser" in dependency_text
        for config_name in UI_CONFIG_NAMES:
            config_path = base / config_name
            if config_path.exists():
                configs.append(str(config_path.relative_to(root)))
                lowered = config_name.lower()
                playwright_detected = playwright_detected or "playwright" in lowered
                cypress_detected = cypress_detected or "cypress" in lowered
                vitest_browser_detected = vitest_browser_detected or "browser" in lowered or "vitest" in lowered

    mode = str(repo_cfg.get("ui_cli", {}).get("mode", "")).strip()
    return {
        "detected": bool(package_jsons or configs or browser_scripts),
        "rendered_target": "verify-ui-cli" in targets,
        "mode": mode,
        "declared_commands": list(repo_cfg.get("ui_cli", {}).get("commands", [])),
        "package_jsons": package_jsons,
        "configs": sorted(set(configs)),
        "browser_scripts": browser_scripts,
        "playwright_detected": playwright_detected,
        "cypress_detected": cypress_detected,
        "vitest_browser_detected": vitest_browser_detected,
        "tools": {
            "node": shutil.which("node") is not None,
            "npm": shutil.which("npm") is not None,
            "npx": shutil.which("npx") is not None,
            "xvfb-run": resolve_tool("xvfb-run") is not None,
        },
    }


def ui_review_info(root: Path, repo_cfg: dict[str, Any], targets: dict[str, Any]) -> dict[str, Any]:
    review_cfg = repo_cfg.get("ui_review", {})
    if not isinstance(review_cfg, dict):
        review_cfg = {}
    declared_targets = [str(target) for target in review_cfg.get("targets", []) if isinstance(target, str)]
    summary_rel = str(review_cfg.get("summary") or "artifacts/ui-review/latest/summary.md")
    screenshots_rel = str(review_cfg.get("screenshots") or "artifacts/ui-review/latest/screenshots")
    lighthouse_rel = str(review_cfg.get("lighthouse") or "artifacts/ui-review/latest/lighthouse")
    summary_path = root / summary_rel
    screenshots_dir = root / screenshots_rel
    lighthouse_dir = root / lighthouse_rel
    screenshot_count = (
        sum(1 for path in screenshots_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
        if screenshots_dir.exists()
        else 0
    )
    lighthouse_report_count = (
        sum(1 for path in lighthouse_dir.rglob("*.json") if path.is_file())
        if lighthouse_dir.exists()
        else 0
    )
    return {
        "enabled": bool(review_cfg.get("enabled") or declared_targets),
        "rendered_targets": [target for target in declared_targets if target in targets],
        "declared_targets": declared_targets,
        "declared_commands": dict(review_cfg.get("commands", {})) if isinstance(review_cfg.get("commands"), dict) else {},
        "artifact_summary": summary_rel,
        "artifact_summary_exists": summary_path.exists(),
        "screenshots_dir": screenshots_rel,
        "screenshot_count": screenshot_count,
        "lighthouse_dir": lighthouse_rel,
        "lighthouse_report_count": lighthouse_report_count,
    }


def last_artifacts(log_root: Path, current_target: str) -> list[dict[str, Any]]:
    if not log_root.exists():
        return []
    results: list[dict[str, Any]] = []
    for child in sorted(log_root.iterdir()):
        if not child.is_dir() or child.name == current_target:
            continue
        summary_path = child / "summary.json"
        if not summary_path.exists():
            continue
        results.append(
            {
                "target": child.name,
                "summary": str(summary_path),
                "updated_at": datetime.fromtimestamp(summary_path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return results


def extract_primary_command(command: str) -> str | None:
    try:
        parts = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return None
    for token in parts:
        if "=" in token and not token.startswith(("/", "./")) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token):
            continue
        if token in RESERVED_SHELL_WORDS or token.startswith(("${", "`")):
            return None
        return token
    return None


def tool_readiness(target_cfg: dict[str, Any], root: Path) -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for cfg in target_cfg.values():
        for step in list(cfg.get("prep_steps", [])) + list(cfg.get("steps", [])):
            binary = step.get("tool")
            if binary:
                tools[binary] = {"available": resolve_tool(binary) is not None}
                continue
            primary = extract_primary_command(step.get("command", ""))
            if primary and primary not in tools:
                tools[primary] = {"available": shutil.which(primary) is not None}
        if cfg.get("kind") == "ci-local":
            tools["gh"] = {"available": shutil.which("gh") is not None}
            tools["act"] = {"available": shutil.which("act") is not None}
    if (root / ".github" / "workflows").exists():
        tools.setdefault("gh", {"available": shutil.which("gh") is not None})
    return tools


def resolve_tool(binary: str) -> str | None:
    codex_user = os.environ.get("CODEX_TOOL_USER", "codex")
    current_user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if current_user == codex_user and shutil.which(binary):
        return binary
    local_bin = LOCAL_BIN_DIR / binary
    if local_bin.exists():
        return str(local_bin)
    codex_binary = f"codex-{binary}"
    if shutil.which(codex_binary):
        return codex_binary
    return shutil.which(binary)


def missing_tool_note(summary: dict[str, Any], tool: str) -> str:
    target = str(summary.get("target") or "")
    available_targets = set(summary.get("targets", {}).get("available", []))
    if target == "verify-security" and "bootstrap-security" in available_targets:
        return f"missing tool: {tool}; run `make bootstrap-security` before rerunning security checks on a fresh runner"
    if target in {"verify-ci", "verify"} and "bootstrap-ci" in available_targets:
        return f"missing tool: {tool}; run `make bootstrap-ci` before rerunning verification on a fresh runner"
    if target == "verify-container" and "bootstrap-container" in available_targets:
        return f"missing tool: {tool}; run `make bootstrap-container` before rerunning container checks on a fresh runner"
    return f"missing tool: {tool}; run the matching bootstrap target before rerunning this generated lane"


def docker_ready(binary: str) -> bool:
    probe = subprocess.run(
        [binary, "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return probe.returncode == 0


def resolve_docker() -> str | None:
    codex_user = os.environ.get("CODEX_TOOL_USER", "codex")
    current_user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if current_user == codex_user and shutil.which("docker") and docker_ready("docker"):
        return "docker"
    if shutil.which("codex-docker"):
        return "codex-docker"
    if os.environ.get("GITHUB_ACTIONS") == "true" and shutil.which("docker") and docker_ready("docker"):
        return "docker"
    if os.environ.get("TOOLING_ALLOW_PLAIN_DOCKER") == "1" and shutil.which("docker"):
        return "docker"
    return None


def rewrite_command(binary: str, launcher: str, command: str) -> str:
    if Path(launcher).name == binary:
        return command
    pattern = re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(binary)}(?![A-Za-z0-9_.-])")
    if not pattern.search(command):
        raise ValueError(f"tool command does not reference expected binary: {binary}")
    return pattern.sub(launcher, command)


def discover_workspace_root(root: Path) -> Path:
    for candidate in (root, *root.parents):
        if (candidate / ".templates").exists():
            return candidate
    return root


def format_command(command: str, artifact_root: Path, root: Path) -> str:
    workspace_root = discover_workspace_root(root)
    return (
        command.replace("{artifact_root}", shlex.quote(str(artifact_root)))
        .replace("{root}", shlex.quote(str(root)))
        .replace(WORKSPACE_ROOT_PLACEHOLDER, shlex.quote(str(workspace_root)))
    )


def initial_status(target_kind: str) -> str:
    return "pass"


def combine_status(current: str, new: str) -> str:
    order = {
        "pass": 0,
        "skipped": 0,
        "not_applicable": 0,
        "warn": 1,
        "unavailable": 1,
        "blocked": 2,
        "fail": 3,
    }
    return new if order[new] > order[current] else current


def make_artifact_dir(root: Path, target: str) -> tuple[Path, Path]:
    log_root = relative_or_absolute(root, os.environ.get("TOOLING_LOG_ROOT"), "artifacts/tooling")
    artifact_dir = log_root / target
    logs_dir = artifact_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir, log_root


def latest_summary_path(log_root: Path, target: str) -> Path:
    latest_root = log_root / "latest"
    latest_root.mkdir(parents=True, exist_ok=True)
    return latest_root / f"{target}.json"


def load_latest_summary(log_root: Path, target: str) -> dict[str, Any] | None:
    latest_path = latest_summary_path(log_root, target)
    if not latest_path.exists():
        return None
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def compact_previous_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary:
        return None
    active_lane = summary.get("analysis", {}).get("active_lane", {})
    if not isinstance(active_lane, dict):
        active_lane = {}
    failure_excerpt = " | ".join(
        str(step.get("note", "")).strip()
        for step in summary.get("prep_steps", []) + summary.get("steps", [])
        if step.get("status") == "fail" and str(step.get("note", "")).strip()
    )[:1200]
    return {
        "target": summary.get("target", ""),
        "status": summary.get("status", ""),
        "generated_at": summary.get("generated_at", ""),
        "run_signature": summary.get("analysis", {}).get("run_signature", ""),
        "failure_fingerprint": summary.get("analysis", {}).get("failure_fingerprint", ""),
        "failure_excerpt": failure_excerpt,
        "repo_state_fingerprint": summary.get("analysis", {}).get("repo_state_fingerprint", ""),
        "artifact_path": summary.get("analysis", {}).get("artifact_path", ""),
        "recommended_next_command": summary.get("analysis", {}).get("recommended_next_command", ""),
        "rerun_policy": summary.get("analysis", {}).get("rerun_policy", ""),
        "state_fingerprint": summary.get("git", {}).get("state_fingerprint", ""),
        "branch": summary.get("git", {}).get("branch", ""),
        "head_sha": summary.get("git", {}).get("head_sha", ""),
        "dirty": summary.get("git", {}).get("dirty", None),
        "active_lane_name": active_lane.get("name", ""),
        "active_lane_marker": active_lane.get("marker_path", ""),
        "active_lane_fresh": active_lane.get("brief_fresh", False),
        "summary_json": summary.get("artifacts", {}).get("summary_json", ""),
        "summary_md": summary.get("artifacts", {}).get("summary_md", ""),
        "security_evidence": summary.get("security_evidence", {}),
    }


def artifact_freshness(previous_summary: dict[str, Any] | None, summary: dict[str, Any]) -> tuple[bool, list[str]]:
    if not previous_summary:
        return False, ["no previous artifact"]

    reasons: list[str] = []
    comparisons = [
        ("target", previous_summary.get("target"), summary.get("target")),
        ("branch", previous_summary.get("branch"), summary.get("git", {}).get("branch")),
        ("head_sha", previous_summary.get("head_sha"), summary.get("git", {}).get("head_sha")),
        ("dirty", previous_summary.get("dirty"), summary.get("git", {}).get("dirty")),
        ("repo_state_fingerprint", previous_summary.get("repo_state_fingerprint") or previous_summary.get("state_fingerprint"), summary.get("git", {}).get("state_fingerprint")),
        ("run_signature", previous_summary.get("run_signature"), summary.get("analysis", {}).get("run_signature")),
    ]
    for label, previous, current in comparisons:
        if previous != current:
            reasons.append(f"{label} changed: previous={previous!r} current={current!r}")

    active_lane = summary.get("analysis", {}).get("active_lane", {})
    if not isinstance(active_lane, dict):
        active_lane = {}
    lane_comparisons = [
        ("active_lane_name", previous_summary.get("active_lane_name"), active_lane.get("name", "")),
        ("active_lane_marker", previous_summary.get("active_lane_marker"), active_lane.get("marker_path", "")),
        ("active_lane_fresh", previous_summary.get("active_lane_fresh"), active_lane.get("brief_fresh", False)),
    ]
    for label, previous, current in lane_comparisons:
        if previous != current:
            reasons.append(f"{label} changed: previous={previous!r} current={current!r}")
    if active_lane.get("name") and not active_lane.get("brief_fresh"):
        reasons.append(f"active lane `{active_lane.get('name')}` does not have a fresh brief artifact")
    return not reasons, reasons


def _step_scope_tokens(command: str) -> dict[str, list[str]]:
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return {"exclude": [], "skip_dirs": [], "roots": []}
    excludes: list[str] = []
    skip_dirs: list[str] = []
    roots: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"--exclude", "--skip-dirs", "--skip-dir"} and index + 1 < len(tokens):
            target = tokens[index + 1]
            if token == "--exclude":
                excludes.append(target)
            else:
                skip_dirs.append(target)
            index += 2
            continue
        if token.startswith("--exclude="):
            excludes.append(token.partition("=")[2])
        elif token.startswith("--skip-dirs=") or token.startswith("--skip-dir="):
            skip_dirs.append(token.partition("=")[2])
        elif token in {".", "./"} or token.startswith("./"):
            roots.append(token)
        index += 1
    return {"exclude": sorted(excludes), "skip_dirs": sorted(skip_dirs), "roots": sorted(set(roots))}


def _tool_version(root: Path, launcher: str | None, primary: str | None) -> str:
    binary = launcher or primary or ""
    if not binary:
        return ""
    return capture_version([binary, "--version"], cwd=root)


def _security_step_cache_key(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _step_cache_metadata(
    *,
    root: Path,
    summary: dict[str, Any],
    name: str,
    required: bool,
    category: str,
    resolved_command: str,
    tool: str | None,
    launcher: str | None,
) -> dict[str, str]:
    primary = tool or extract_primary_command(resolved_command) or ""
    version = _tool_version(root, launcher, primary)
    scope_payload = {
        "command_scope": _step_scope_tokens(resolved_command),
        "manifests": summary["repo"].get("manifests", {}),
        "repo_state_fingerprint": summary["analysis"].get("repo_state_fingerprint", ""),
    }
    scope_fingerprint = hashlib.sha256(json.dumps(scope_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    key_payload = {
        "repo_id": summary["repo"].get("repo_id", ""),
        "target": summary.get("target", ""),
        "repo_state_fingerprint": summary["analysis"].get("repo_state_fingerprint", ""),
        "step_name": name,
        "category": category,
        "required": required,
        "command": resolved_command,
        "tool": primary,
        "tool_version": version,
        "scanner_input_scope": scope_fingerprint,
    }
    return {
        "step_cache_key": _security_step_cache_key(key_payload),
        "tool_name": primary,
        "tool_version": version,
        "scanner_input_scope": scope_fingerprint,
    }


def _previous_target_summary(summary: dict[str, Any]) -> dict[str, Any] | None:
    try:
        latest_path = Path(summary["artifacts"]["latest_index"])
    except (KeyError, TypeError):
        return None
    if not latest_path.exists():
        return None
    return read_json_optional(latest_path)


def _eligible_for_step_reuse(summary: dict[str, Any], *, required: bool, category: str) -> tuple[bool, str]:
    if summary.get("target") not in CACHEABLE_STEP_TARGETS:
        return False, "target is not step-cacheable"
    if category not in CACHEABLE_STEP_CATEGORIES:
        return False, "step category is not step-cacheable"
    env = summary.get("environment", {})
    if env.get("force_rerun"):
        return False, "FORCE_RERUN is set"
    if env.get("tooling_disable_step_reuse"):
        return False, "TOOLING_DISABLE_STEP_REUSE is set"
    if env.get("github_actions") and required and not env.get("tooling_allow_ci_step_reuse"):
        return False, "required scanner reuse is disabled in GitHub Actions by default"
    git = summary.get("git", {})
    if git.get("tracked_content_hash_limited"):
        return False, "tracked changed file content was too large to hash safely"
    if git.get("untracked_content_hash_limited"):
        return False, "untracked changed file content was too large or numerous to hash safely"
    return True, ""


def _previous_reusable_step(summary: dict[str, Any], cache_key: str) -> tuple[dict[str, Any] | None, str]:
    previous = _previous_target_summary(summary)
    if not previous:
        return None, "no previous summary"
    previous_state = str(
        previous.get("analysis", {}).get("repo_state_fingerprint") or previous.get("git", {}).get("state_fingerprint") or ""
    ).strip()
    current_state = str(summary["analysis"].get("repo_state_fingerprint") or "").strip()
    if not previous_state or previous_state != current_state:
        return None, "repo state changed"
    if previous.get("target") != summary.get("target"):
        return None, "target changed"
    for step in previous.get("steps", []):
        if step.get("step_cache_key") == cache_key:
            status = str(step.get("status") or "").strip()
            if status == "pass":
                return step, ""
            return None, f"previous matching step status was {status or 'unknown'}"
    return None, "no matching step cache key"


def _record_reused_step(
    summary: dict[str, Any],
    *,
    previous_step: dict[str, Any],
    name: str,
    resolved_command: str,
    required: bool,
    category: str,
    cache_metadata: dict[str, str],
    evidence_categories: list[str] | None = None,
    gate: str = "",
) -> None:
    previous_duration = float(previous_step.get("duration_seconds") or previous_step.get("previous_duration_seconds") or 0.0)
    previous_log = str(previous_step.get("log_path") or "").strip()
    note = str(previous_step.get("note") or "previous step artifact reused").strip()
    status = str(previous_step.get("status") or "warn").strip()
    if status not in {"pass", "warn", "fail", "skipped", "not_applicable", "unavailable"}:
        status = "warn"
    step = record_step(
        summary,
        name=name,
        status=status,
        command=resolved_command,
        duration_seconds=0.0,
        log_path=None,
        required=required,
        category=category,
        note=f"reused_previous_step_artifact: previous_duration={previous_duration}s previous_log={previous_log or 'none'}; {note}",
        exit_code=previous_step.get("exit_code"),
        evidence_categories=evidence_categories,
        gate=gate,
    )
    step.update(cache_metadata)
    step["reused_previous_step_artifact"] = True
    step["previous_duration_seconds"] = previous_duration
    step["previous_log_path"] = previous_log
    summary["analysis"]["reused_step_artifacts"].append(
        {
            "name": name,
            "status": status,
            "previous_duration_seconds": previous_duration,
            "previous_log_path": previous_log,
        }
    )
    summary["analysis"]["step_reuse_saved_seconds"] = round(
        float(summary["analysis"].get("step_reuse_saved_seconds") or 0.0) + previous_duration,
        3,
    )


def load_active_lane(root: Path, repo_cfg: dict[str, Any], git: dict[str, Any]) -> dict[str, Any]:
    lane_policy = repo_cfg.get("lane_policy", {}) if isinstance(repo_cfg, dict) else {}
    if not isinstance(lane_policy, dict):
        return {}
    marker_raw = str(lane_policy.get("active_lane_marker", "")).strip()
    if not marker_raw:
        return {}
    marker_path = relative_or_absolute(root, marker_raw, marker_raw)
    payload = read_json_optional(marker_path) or {}
    if not payload:
        return {
            "marker_path": str(marker_path),
            "name": "",
            "present": False,
            "brief_fresh": False,
        }
    lane_name = str(payload.get("lane") or payload.get("name") or "").strip()
    domain_lanes = lane_policy.get("domain_lanes", {}) if isinstance(lane_policy.get("domain_lanes", {}), dict) else {}
    lane_cfg = domain_lanes.get(lane_name, {}) if lane_name else {}
    brief_artifact_raw = str(lane_cfg.get("brief_artifact") or payload.get("brief_artifact") or "").strip()
    brief_artifact_path = relative_or_absolute(root, brief_artifact_raw, brief_artifact_raw) if brief_artifact_raw else None
    brief_summary = read_json_optional(brief_artifact_path) if brief_artifact_path else None
    brief_state = ""
    if brief_summary:
        brief_state = str(brief_summary.get("git", {}).get("state_fingerprint", "")).strip()
    marker_state = str(payload.get("state_fingerprint", "")).strip()
    current_state = str(git.get("state_fingerprint", "")).strip()
    marker_git = payload.get("git", {}) if isinstance(payload.get("git", {}), dict) else {}
    branch_match = str(marker_git.get("branch", "")).strip() == str(git.get("branch", "")).strip()
    head_match = str(marker_git.get("head_sha", "")).strip() == str(git.get("head_sha", "")).strip()
    dirty_match = marker_git.get("dirty") == git.get("dirty")
    return {
        "marker_path": str(marker_path),
        "name": lane_name,
        "present": True,
        "payload": payload,
        "brief_target": str(lane_cfg.get("brief_target", "")).strip(),
        "fast_target": str(lane_cfg.get("fast_target", "")).strip(),
        "repair_target": str(lane_cfg.get("repair_target", "")).strip(),
        "ci_target": str(lane_cfg.get("ci_target", "")).strip(),
        "heavy_targets": list(lane_cfg.get("heavy_targets", [])),
        "status_targets": list(lane_cfg.get("status_targets", [])),
        "brief_artifact": str(brief_artifact_path) if brief_artifact_path else "",
        "brief_artifact_exists": bool(brief_artifact_path and brief_artifact_path.exists()),
        "brief_fresh": bool(
            (brief_summary and brief_state and brief_state == current_state)
            or (marker_state and current_state and marker_state == current_state)
            or (branch_match and head_match and dirty_match)
        ),
        "brief_state_fingerprint": brief_state or marker_state,
        "current_state_fingerprint": current_state,
        "updated_at": str(payload.get("updated_at", "")).strip(),
    }


def environment_info() -> dict[str, Any]:
    return {
        "tooling_output_format": os.environ.get("TOOLING_OUTPUT_FORMAT", "both"),
        "tooling_summary_only": os.environ.get("TOOLING_SUMMARY_ONLY", "0") == "1",
        "tooling_allow_missing_tools": os.environ.get("TOOLING_ALLOW_MISSING_TOOLS", "0") == "1",
        "tooling_allow_plain_docker": os.environ.get("TOOLING_ALLOW_PLAIN_DOCKER", "0") == "1",
        "tooling_allow_mutating_checks": os.environ.get("TOOLING_ALLOW_MUTATING_CHECKS", "0") == "1",
        "tooling_disable_step_reuse": os.environ.get("TOOLING_DISABLE_STEP_REUSE", "0") == "1",
        "tooling_allow_ci_step_reuse": os.environ.get("TOOLING_ALLOW_CI_STEP_REUSE", "0") == "1",
        "force_rerun": os.environ.get("FORCE_RERUN", "0") == "1",
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        "ci_local_mode": os.environ.get("CI_LOCAL_MODE", "lint"),
        "watch_mode": os.environ.get("WATCH_MODE", "show"),
        "review_ready_scope": os.environ.get("REVIEW_READY_SCOPE", "core"),
    }


def collect_base_summary(root: Path, config: dict[str, Any], target: str, artifact_dir: Path, log_root: Path) -> dict[str, Any]:
    repo_cfg = config["repo"]
    repo_agents_path = root / "AGENTS.md"
    git = git_info(root, repo_cfg)
    workflows = workflow_info(root)
    previous_summary = load_latest_summary(log_root, target)
    previous_compact = compact_previous_summary(previous_summary)
    active_lane = load_active_lane(root, repo_cfg, git)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "target": target,
        "status": initial_status(config["targets"][target]["kind"]),
        "repo": {
            **repo_cfg,
            "root": str(root),
            "manifests": manifest_info(root, repo_cfg),
            "python_runtime": python_runtime_info(root, repo_cfg=repo_cfg, targets=config["targets"]),
            "ui_cli": ui_cli_info(root, repo_cfg, config["targets"]),
            "ui_review": ui_review_info(root, repo_cfg, config["targets"]),
            "repo_local_agents": repo_agents_path.exists(),
            "repo_local_agents_path": str(repo_agents_path) if repo_agents_path.exists() else "",
        },
        "git": git,
        "targets": {
            "available": sorted(config["targets"].keys()),
            "tool_readiness": tool_readiness(config["targets"], root),
        },
        "environment": environment_info(),
        "workflows": workflows,
        "prep_steps": [],
        "steps": [],
        "findings": [],
        "blockers": [],
        "next_actions": [],
        "artifacts": {
            "artifact_root": str(artifact_dir),
            "log_root": str(log_root),
            "last_known": last_artifacts(log_root, target),
            "latest_index": str(latest_summary_path(log_root, target)),
        },
        "github": gh_info(root, git["branch"]),
        "analysis": {
            "run_signature": "",
            "failure_fingerprint": "",
            "repo_state_fingerprint": str(git.get("state_fingerprint", "")).strip(),
            "artifact_path": "",
            "artifact_review_required": False,
            "preferred_existing_artifact": "",
            "loop_suppression_reason": "",
            "recommended_next_command": "",
            "rerun_policy": "fresh-run",
            "same_signature_as_previous": False,
            "same_failure_as_previous": False,
            "reused_previous_artifact": False,
            "artifact_fresh_for_current_state": False,
            "artifact_stale_reasons": [],
            "previous_artifact_fresh_for_current_state": False,
            "previous_artifact_stale_reasons": [],
            "previous_summary": previous_compact,
            "active_lane": active_lane,
            "reused_step_artifacts": [],
            "step_reuse_refusals": [],
            "step_reuse_saved_seconds": 0.0,
            "slow_steps": [],
            "production_efficiency": {
                "full_log_path_count": 0,
                "raw_log_token_estimate": 0,
                "long_log_summary_required_count": 0,
                "summary_missing_full_log_path": False,
                "same_failure_diagnostic_required": False,
                "same_failure_retry_without_diagnostic": False,
            },
        },
    }
    summary["analysis"]["run_signature"] = compute_run_signature(summary)
    artifact_fresh, artifact_stale_reasons = artifact_freshness(previous_compact, summary)
    summary["analysis"]["previous_artifact_fresh_for_current_state"] = artifact_fresh
    summary["analysis"]["previous_artifact_stale_reasons"] = artifact_stale_reasons
    return summary


def compute_run_signature(summary: dict[str, Any]) -> str:
    payload = {
        "target": summary["target"],
        "repo_id": summary["repo"]["repo_id"],
        "state_fingerprint": summary["git"].get("state_fingerprint", ""),
        "review_ready_scope": summary["environment"].get("review_ready_scope", ""),
        "ci_local_mode": summary["environment"].get("ci_local_mode", ""),
        "watch_mode": summary["environment"].get("watch_mode", ""),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def compute_failure_fingerprint(summary: dict[str, Any]) -> str:
    def normalized_note(value: object) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())[:400]

    failed_steps = [
        {
            "name": step["name"],
            "command": step["command"],
            "exit_code": step.get("exit_code"),
            "note": normalized_note(step.get("note")),
        }
        for step in summary.get("prep_steps", []) + summary.get("steps", [])
        if step.get("status") == "fail"
    ]
    if not failed_steps:
        return ""
    return hashlib.sha256(json.dumps(failed_steps, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def repo_uses_local_only_git_policy(summary: dict[str, Any]) -> bool:
    return str(summary.get("repo", {}).get("git_policy_profile", "")).strip() == "local-only"


def populate_brief_findings(summary: dict[str, Any]) -> None:
    git = summary["git"]
    workflows = summary["workflows"]
    github = summary["github"]
    repo = summary["repo"]
    local_only_git = repo_uses_local_only_git_policy(summary)

    if not git["available"]:
        summary["findings"].append("unavailable: git metadata is unavailable in the current working tree")
        return
    if git["branch"] == "detached":
        summary["findings"].append("warn: detached HEAD; confirm the intended review base before making changes")
    if not git["remotes"]:
        if local_only_git:
            summary["findings"].append("local_only: no git remotes are configured by policy")
        else:
            summary["findings"].append("unavailable: no git remotes are configured")
    if git["upstream"] == "unavailable":
        if local_only_git:
            summary["findings"].append("local_only: current branch intentionally has no upstream")
        else:
            summary["findings"].append("warn: current branch has no upstream")
    if not workflows["available"] or not workflows["all_workflows"]:
        summary["findings"].append("not_applicable: no GitHub workflows detected")
    if not repo["repo_local_agents"]:
        summary["findings"].append("unavailable: repo-local AGENTS.md missing; use repo docs plus the shared fallback template")
    if not github["available"]:
        summary["findings"].append("unavailable: gh is not installed")
    elif not github["authenticated"]:
        summary["findings"].append(f"unavailable: {github['error'] or 'gh is not authenticated'}")
    python_runtime = repo.get("python_runtime", {})
    if python_runtime.get("detected"):
        preferred = python_runtime.get("preferred_python_command") or python_runtime.get("fallback_python_command") or "python3"
        summary["findings"].append(
            "python-runtime: "
            + f"{python_runtime.get('manager')} via `{preferred}`; "
            + f"notebook=`{python_runtime.get('notebook_inspection_command') or preferred}`; "
            + f"test=`{python_runtime.get('test_command') or 'repo-local make target'}`; "
            + str(python_runtime.get("route_note") or "")
        )
        if not python_runtime.get("raw_python_allowed"):
            summary["findings"].append("python-runtime: raw `python` is not a repo contract; use the route above or a repo-local make target")
    ui_cli = repo.get("ui_cli", {})
    if ui_cli.get("detected"):
        marker_count = len(ui_cli.get("configs", [])) + sum(len(items) for items in ui_cli.get("browser_scripts", {}).values())
        rendered = "rendered" if ui_cli.get("rendered_target") else "not rendered"
        summary["findings"].append(f"ui-cli: browser/UI markers detected ({marker_count}); verify-ui-cli is {rendered}")
        if ui_cli.get("playwright_detected"):
            summary["findings"].append("ui-cli: Playwright detected; install repo-managed browsers with `npx playwright install chromium` when browser binaries are missing")
    if ui_cli.get("mode") == "xvfb" and not ui_cli.get("tools", {}).get("xvfb-run"):
        summary["findings"].append("unavailable: verify-ui-cli requires `xvfb-run`; install the optional UI/browser tooling pack")
    ui_review = repo.get("ui_review", {})
    if ui_review.get("enabled"):
        rendered_targets = ui_review.get("rendered_targets", [])
        summary_state = "available" if ui_review.get("artifact_summary_exists") else "missing"
        summary["findings"].append(
            "ui-review: "
            + f"{', '.join(rendered_targets) if rendered_targets else 'no rendered targets'}; "
            + f"summary {summary_state} at `{ui_review.get('artifact_summary')}`; "
            + f"screenshots={ui_review.get('screenshot_count', 0)} lighthouse_json={ui_review.get('lighthouse_report_count', 0)}"
        )
        if "ui-review-pack" in rendered_targets and not ui_review.get("artifact_summary_exists"):
            summary["findings"].append(
                "ui-review: run `make ui-review-pack` for visual changes when screenshot, accessibility, mobile, reduced-motion, large-text, or Lighthouse evidence is missing"
            )
    previous_summary = summary["analysis"].get("previous_summary")
    if previous_summary and previous_summary.get("state_fingerprint") == summary["git"].get("state_fingerprint"):
        summary["findings"].append(
            f"state unchanged since the previous `{summary['target']}` run; review {summary['artifacts']['latest_index']} before re-checking"
        )
    active_lane = summary["analysis"].get("active_lane", {})
    if active_lane.get("name"):
        lane_name = active_lane["name"]
        if active_lane.get("brief_fresh"):
            summary["findings"].append(
                f"active lane `{lane_name}` is fresh for the current repo state; prefer its latest artifact before raw status polling"
            )
        else:
            brief_target = active_lane.get("brief_target") or "repo-brief"
            summary["findings"].append(
                f"active lane `{lane_name}` has no fresh brief artifact; refresh with `make {brief_target}` before broader verification"
            )


def record_step(
    summary: dict[str, Any],
    *,
    name: str,
    status: str,
    command: str,
    duration_seconds: float,
    log_path: Path | None,
    required: bool,
    category: str,
    note: str,
    nested_summary: str | None = None,
    exit_code: int | None = None,
    bucket: str = "steps",
    evidence_categories: list[str] | None = None,
    gate: str = "",
) -> dict[str, Any]:
    step = {
        "name": name,
        "status": status,
        "command": command,
        "duration_seconds": duration_seconds,
        "required": required,
        "category": category,
        "note": note,
        "exit_code": exit_code,
        "log_path": str(log_path) if log_path else "",
        "summary_path": nested_summary or "",
    }
    step.update(log_stats(log_path))
    if evidence_categories:
        step["evidence_categories"] = evidence_categories
    if gate:
        step["gate"] = gate
    summary[bucket].append(step)
    if status == "fail":
        summary["blockers"].append(f"{name}: {note}")
    elif status == "blocked":
        summary["blockers"].append(f"{name}: {note}")
    elif status in {"warn", "unavailable"}:
        summary["findings"].append(f"{name}: {note}")
    elif status in {"skipped", "not_applicable"}:
        summary["findings"].append(f"{name}: {status}: {note}")
    summary["status"] = combine_status(summary["status"], status)
    return step


def run_step(
    root: Path,
    summary: dict[str, Any],
    artifact_dir: Path,
    step: dict[str, Any],
    index: int,
) -> None:
    name = step.get("name") or f"step-{index:02d}"
    required = bool(step.get("required", True))
    command = step.get("command", "")
    tool = step.get("tool")
    docker_args = step.get("docker_args")
    category = step.get("category", "command")
    raw_evidence_categories = step.get("evidence_categories", [])
    evidence_categories = [str(item) for item in raw_evidence_categories] if isinstance(raw_evidence_categories, list) else []
    gate = str(step.get("gate") or "").strip()
    resolved_command = format_command(command, artifact_dir, root) if command else ""
    launcher: str | None = None

    if step.get("mutates_branch") and not summary["environment"].get("tooling_allow_mutating_checks"):
        record_step(
            summary,
            name=name,
            status="warn",
            command=resolved_command or name,
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category=category,
            note="tool hazard: branch-mutating check skipped; set TOOLING_ALLOW_MUTATING_CHECKS=1 only for an explicit mutating run",
            evidence_categories=evidence_categories,
            gate=gate,
        )
        return

    if tool:
        launcher = resolve_tool(tool)
        if launcher is None:
            status = "fail" if required else "unavailable"
            record_step(
                summary,
                name=name,
                status=status,
                command=resolved_command or tool,
                duration_seconds=0.0,
                log_path=None,
                required=required,
                category=category,
                note=missing_tool_note(summary, str(tool)),
                evidence_categories=evidence_categories,
                gate=gate,
            )
            return
        resolved_command = rewrite_command(tool, launcher, resolved_command)

    if docker_args:
        docker_launcher = resolve_docker()
        if docker_launcher is None:
            status = "fail" if required else "unavailable"
            record_step(
                summary,
                name=name,
                status=status,
                command=f"docker {docker_args}",
                duration_seconds=0.0,
                log_path=None,
                required=required,
                category=category,
                note="docker bridge unavailable",
                evidence_categories=evidence_categories,
                gate=gate,
            )
            return
        resolved_command = f"{docker_launcher} {docker_args}"

    cache_metadata = _step_cache_metadata(
        root=root,
        summary=summary,
        name=name,
        required=required,
        category=category,
        resolved_command=resolved_command,
        tool=str(tool) if tool else None,
        launcher=launcher,
    )
    eligible, _ = _eligible_for_step_reuse(summary, required=required, category=category)
    if eligible:
        previous_step, refusal_reason = _previous_reusable_step(summary, cache_metadata["step_cache_key"])
        if previous_step:
            _record_reused_step(
                summary,
                previous_step=previous_step,
                name=name,
                resolved_command=resolved_command,
                required=required,
                category=category,
                cache_metadata=cache_metadata,
                evidence_categories=evidence_categories,
                gate=gate,
            )
            return
        if refusal_reason:
            summary["analysis"].setdefault("step_reuse_refusals", []).append(
                {
                    "name": name,
                    "category": category,
                    "step_cache_key": cache_metadata["step_cache_key"],
                    "reason": refusal_reason,
                }
            )

    log_path = artifact_dir / "logs" / f"{index:02d}-{name}.log"
    rc, duration = run_shell(resolved_command, cwd=root, log_path=log_path)
    if rc == 0:
        status = "pass"
    else:
        status = "fail" if required else "warn"
    note = log_excerpt(log_path, failed=rc != 0)
    recorded = record_step(
        summary,
        name=name,
        status=status,
        command=resolved_command,
        duration_seconds=duration,
        log_path=log_path,
        required=required,
        category=category,
        note=note,
        exit_code=rc,
        evidence_categories=evidence_categories,
        gate=gate,
    )
    recorded.update(cache_metadata)
    recorded["reused_previous_step_artifact"] = False


def write_summary(summary: dict[str, Any], artifact_dir: Path) -> None:
    summary_json = artifact_dir / "summary.json"
    summary_md = artifact_dir / "summary.md"
    target_latest_dir = artifact_dir / "latest"
    target_latest_json = target_latest_dir / "summary.json"
    target_latest_md = target_latest_dir / "summary.md"
    latest_json = Path(summary["artifacts"]["latest_index"])
    if isinstance(summary.get("release_gate"), dict) and summary["release_gate"]:
        summary["artifacts"]["pr_ready_md"] = str(artifact_dir / "pr-ready.md")
        summary["artifacts"]["latest_pr_ready_md"] = str(target_latest_dir / "pr-ready.md")
    output_format = os.environ.get("TOOLING_OUTPUT_FORMAT", "both")
    if output_format in {"both", "json"}:
        target_latest_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(summary, indent=2, sort_keys=False) + "\n"
        summary_json.write_text(payload, encoding="utf-8")
        target_latest_json.write_text(payload, encoding="utf-8")
        latest_json.write_text(payload, encoding="utf-8")

    md_lines = [
        f"# Tooling Summary: {summary['target']}",
        "",
        f"- status: `{summary['status']}`",
        f"- generated_at: `{summary['generated_at']}`",
        f"- repo_id: `{summary['repo']['repo_id']}`",
        f"- artifact_root: `{summary['artifacts']['artifact_root']}`",
        "",
        "## Repo",
        "",
        f"- root: `{summary['repo']['root']}`",
        f"- archetype: `{summary['repo']['archetype']}`",
        f"- git_policy_profile: `{summary['repo']['git_policy_profile']}`",
        f"- github_flow_profile: `{summary['repo']['github_flow_profile']}`",
        f"- repo_local_agents: `{summary['repo']['repo_local_agents']}`",
        f"- repo_local_agents_path: `{summary['repo']['repo_local_agents_path'] or 'none'}`",
        f"- deterministic_targets: `{', '.join(summary['targets']['available']) or 'none'}`",
        "",
        "## Git",
        "",
        f"- branch: `{summary['git']['branch']}`",
        f"- upstream: `{summary['git']['upstream']}`",
        f"- ahead: `{summary['git']['ahead']}`",
        f"- behind: `{summary['git']['behind']}`",
        f"- dirty: `{summary['git']['dirty']}`",
        f"- protected_branch: `{summary['git']['protected_branch']}`",
        f"- remotes: `{len(summary['git']['remotes'])}`",
        f"- stashes: `{summary['git']['stash_count']}`",
        f"- linked_worktrees: `{len(summary['git']['worktrees'])}`",
        "",
        "## Workflows",
        "",
        f"- workflow_dir: `{summary['workflows']['workflow_dir']}`",
        f"- tooling_workflows: `{', '.join(summary['workflows']['tooling_workflows']) or 'none'}`",
        f"- all_workflows: `{', '.join(summary['workflows']['all_workflows']) or 'none'}`",
        "",
        "## GitHub",
        "",
        f"- gh_available: `{summary['github']['available']}`",
        f"- gh_authenticated: `{summary['github']['authenticated']}`",
        f"- gh_error: `{summary['github']['error'] or 'none'}`",
        "",
        "## Analysis",
        "",
        f"- rerun_policy: `{summary['analysis']['rerun_policy']}`",
        f"- artifact_fresh_for_current_state: `{summary['analysis']['artifact_fresh_for_current_state']}`",
        f"- reused_previous_artifact: `{summary['analysis']['reused_previous_artifact']}`",
        f"- artifact_review_required: `{summary['analysis'].get('artifact_review_required', False)}`",
        f"- preferred_existing_artifact: `{summary['analysis'].get('preferred_existing_artifact') or 'none'}`",
        f"- loop_suppression_reason: `{summary['analysis'].get('loop_suppression_reason') or 'none'}`",
        f"- run_signature: `{summary['analysis']['run_signature']}`",
        f"- repo_state_fingerprint: `{summary['analysis']['repo_state_fingerprint']}`",
        f"- failure_fingerprint: `{summary['analysis']['failure_fingerprint'] or 'none'}`",
        f"- previous_artifact_fresh_for_current_state: `{summary['analysis']['previous_artifact_fresh_for_current_state']}`",
        f"- reused_step_artifacts: `{len(summary['analysis'].get('reused_step_artifacts') or [])}`",
        f"- step_reuse_saved_seconds: `{summary['analysis'].get('step_reuse_saved_seconds', 0.0)}`",
    ]
    python_runtime = summary["repo"].get("python_runtime", {})
    if python_runtime:
        insert_at = md_lines.index("## Git") - 1
        md_lines[insert_at:insert_at] = [
            f"- python_runtime_manager: `{python_runtime.get('manager', 'none')}`",
            f"- python_preferred_command: `{python_runtime.get('preferred_python_command') or 'none'}`",
            f"- python_notebook_command: `{python_runtime.get('notebook_inspection_command') or 'none'}`",
            f"- python_test_command: `{python_runtime.get('test_command') or 'none'}`",
            f"- raw_python_allowed: `{python_runtime.get('raw_python_allowed', False)}`",
        ]
    stale_reasons = summary["analysis"].get("artifact_stale_reasons") or []
    previous_stale_reasons = summary["analysis"].get("previous_artifact_stale_reasons") or []
    md_lines.append(f"- artifact_stale_reasons: `{'; '.join(stale_reasons) or 'none'}`")
    md_lines.append(f"- previous_artifact_stale_reasons: `{'; '.join(previous_stale_reasons) or 'none'}`")
    production_efficiency = summary["analysis"].get("production_efficiency", {})
    if isinstance(production_efficiency, dict):
        md_lines.append(f"- full_log_path_count: `{production_efficiency.get('full_log_path_count', 0)}`")
        md_lines.append(f"- raw_log_token_estimate: `{production_efficiency.get('raw_log_token_estimate', 0)}`")
        md_lines.append(f"- long_log_summary_required_count: `{production_efficiency.get('long_log_summary_required_count', 0)}`")
        md_lines.append(
            f"- same_failure_retry_without_diagnostic: `{production_efficiency.get('same_failure_retry_without_diagnostic', False)}`"
        )
    security_evidence = summary.get("security_evidence", {})
    if isinstance(security_evidence, dict) and security_evidence:
        md_lines.extend(["", "## Security Evidence", ""])
        md_lines.append(f"- profile: `{security_evidence.get('profile', 'unknown')}`")
        md_lines.append(f"- status: `{security_evidence.get('status', 'unknown')}`")
        md_lines.append(f"- paid_github_required: `{security_evidence.get('paid_github_required', False)}`")
        md_lines.append(f"- saas_required: `{security_evidence.get('saas_required', False)}`")
        md_lines.append(f"- certification_claimed: `{security_evidence.get('certification_claimed', False)}`")
        categories = security_evidence.get("categories", {})
        if isinstance(categories, dict):
            for category in SECURITY_EVIDENCE_CATEGORIES:
                item = categories.get(category, {})
                if not isinstance(item, dict):
                    continue
                md_lines.append(
                    f"- `{category}`: `{item.get('status', 'unknown')}` gate `{item.get('gate', 'advisory')}` steps `{len(item.get('steps', []))}`"
                )
    release_gate = summary.get("release_gate", {})
    if isinstance(release_gate, dict) and release_gate:
        md_lines.extend(["", "## Release Gate", ""])
        md_lines.append(f"- final_decision: `{release_gate.get('final_decision', 'unknown')}`")
        md_lines.append(f"- target_branch: `{release_gate.get('target_branch', 'unknown')}`")
        md_lines.append(f"- github_actions_mode: `{release_gate.get('github_actions_mode', summary['repo'].get('github_actions_mode', 'unknown'))}`")
        md_lines.append(f"- hosted_runner_minutes_policy: `{release_gate.get('hosted_runner_minutes_policy', 'unknown')}`")
        md_lines.append(f"- expected_remote_contexts: `{', '.join(release_gate.get('expected_remote_contexts', [])) or 'none'}`")
        md_lines.append(f"- remote_actions_authority: `{release_gate.get('remote_actions_authority', False)}`")
        md_lines.append(f"- manual_human_gate_required: `{release_gate.get('manual_human_gate_required', True)}`")
        md_lines.append(f"- pr_ready_md: `{summary['artifacts'].get('pr_ready_md', 'none')}`")
        md_lines.append(f"- stale_evidence: `{', '.join(release_gate.get('stale_evidence', [])) or 'none'}`")
        md_lines.append(f"- missing_evidence: `{', '.join(release_gate.get('missing_evidence', [])) or 'none'}`")
        md_lines.append(f"- failed_targets: `{', '.join(release_gate.get('failed_targets', [])) or 'none'}`")
        md_lines.append(f"- blocked_targets: `{', '.join(release_gate.get('blocked_targets', [])) or 'none'}`")
        md_lines.append(f"- security_waiver_required: `{release_gate.get('security_waiver_required', False)}`")
        md_lines.append(f"- security_waiver_targets: `{', '.join(release_gate.get('security_waiver_targets', [])) or 'none'}`")
    if summary["prep_steps"]:
        md_lines.extend(["", "## Prep Steps", ""])
        for step in summary["prep_steps"]:
            md_lines.append(
                f"- `{step['name']}`: `{step['status']}` in `{step['duration_seconds']}`s; `{step['command']}`"
            )
            md_lines.append(f"  note: {step['note']}")
            if step["log_path"]:
                md_lines.append(f"  log: `{step['log_path']}`")
    md_lines.extend(["", "## Steps", ""])
    if summary["steps"]:
        for step in summary["steps"]:
            md_lines.append(
                f"- `{step['name']}`: `{step['status']}` in `{step['duration_seconds']}`s; `{step['command']}`"
            )
            md_lines.append(f"  note: {step['note']}")
            if step.get("reused_previous_step_artifact"):
                md_lines.append(f"  reused_previous_step_artifact: `{step.get('previous_log_path') or 'unknown'}`")
            if step["log_path"]:
                md_lines.append(f"  log: `{step['log_path']}`")
            if step["summary_path"]:
                md_lines.append(f"  summary: `{step['summary_path']}`")
    slow_steps = summary["analysis"].get("slow_steps") or []
    if slow_steps:
        md_lines.extend(["", "## Runtime Hotspots", ""])
        for step in slow_steps:
            reused = " reused" if step.get("reused_previous_step_artifact") else ""
            md_lines.append(
                f"- `{step['name']}`: `{step['duration_seconds']}`s; status `{step['status']}`; category `{step['category']}`{reused}"
            )
    else:
        md_lines.append("- no executed steps")
    md_lines.extend(["", "## Blockers", ""])
    if summary["blockers"]:
        for item in summary["blockers"]:
            md_lines.append(f"- {item}")
    else:
        md_lines.append("- none")
    md_lines.extend(["", "## Findings", ""])
    if summary["findings"]:
        for item in summary["findings"]:
            md_lines.append(f"- {item}")
    else:
        md_lines.append("- none")
    md_lines.extend(["", "## Next Actions", ""])
    if summary["next_actions"]:
        for item in summary["next_actions"]:
            md_lines.append(f"- {item}")
    else:
        md_lines.append("- none")
    md_lines.append("")
    if output_format in {"both", "text"}:
        target_latest_dir.mkdir(parents=True, exist_ok=True)
        summary_md.write_text("\n".join(md_lines), encoding="utf-8")
        target_latest_md.write_text("\n".join(md_lines), encoding="utf-8")
        if isinstance(release_gate, dict) and release_gate:
            pr_ready = _release_gate_pr_ready_markdown(summary)
            (artifact_dir / "pr-ready.md").write_text(pr_ready, encoding="utf-8")
            (target_latest_dir / "pr-ready.md").write_text(pr_ready, encoding="utf-8")


def _release_gate_pr_ready_markdown(summary: dict[str, Any]) -> str:
    gate = summary.get("release_gate", {}) if isinstance(summary.get("release_gate"), dict) else {}
    lines = [
        f"Local promotion evidence for `{summary['repo'].get('repo_id', '')}`",
        f"- head: `{str(summary['git'].get('head_sha') or '')[:12]}`",
        f"- branch: `{summary['git'].get('branch', '')}`",
        f"- release_gate: `{gate.get('final_decision', summary.get('status', 'unknown'))}`",
        f"- summary: `{summary['artifacts'].get('summary_json', '')}`",
        f"- github_actions_mode: `{gate.get('github_actions_mode', summary['repo'].get('github_actions_mode', 'unknown'))}`",
        f"- hosted_runner_minutes_policy: `{gate.get('hosted_runner_minutes_policy', 'unknown')}`",
        f"- remote_actions_authority: `{gate.get('remote_actions_authority', False)}`",
        f"- manual_human_gate_required: `{gate.get('manual_human_gate_required', True)}`",
        f"- security_waiver_required: `{gate.get('security_waiver_required', False)}`",
        f"- security_waiver_targets: `{', '.join(gate.get('security_waiver_targets', [])) or 'none'}`",
    ]
    commands = gate.get("optional_dispatch_commands", [])
    lines.append("- optional_hosted_dispatch_commands:")
    if commands:
        for command in commands:
            lines.append(f"  - `{command}`")
    else:
        lines.append("  - none")
    return "\n".join(lines) + "\n"


def print_summary(summary: dict[str, Any], artifact_dir: Path) -> None:
    lines = [
        f"[tooling] target={summary['target']} status={summary['status']}",
        f"[tooling] summary-json={artifact_dir / 'summary.json'}",
        f"[tooling] summary-md={artifact_dir / 'summary.md'}",
        f"[tooling] latest-json={summary['artifacts']['latest_index']}",
    ]
    rerun_policy = str(summary["analysis"].get("rerun_policy") or "").strip()
    if rerun_policy:
        lines.append(f"[tooling] rerun_policy={rerun_policy}")
    lines.append(f"[tooling] artifact_fresh_for_current_state={summary['analysis'].get('artifact_fresh_for_current_state')}")
    if summary["analysis"].get("reused_previous_artifact"):
        lines.append("[tooling] reused_previous_artifact=true")
    reused_steps = summary["analysis"].get("reused_step_artifacts") or []
    if reused_steps:
        lines.append(
            f"[tooling] reused_step_artifacts={len(reused_steps)} saved_seconds={summary['analysis'].get('step_reuse_saved_seconds', 0.0)}"
        )
    slow_steps = summary["analysis"].get("slow_steps") or []
    if slow_steps:
        top = slow_steps[0]
        lines.append(
            f"[tooling] slowest_step={top.get('name')}:{top.get('duration_seconds')}s status={top.get('status')}"
        )
    stale_reasons = summary["analysis"].get("artifact_stale_reasons") or []
    if stale_reasons:
        lines.append(f"[tooling] artifact_stale_reason={stale_reasons[0]}")
    previous_stale_reasons = summary["analysis"].get("previous_artifact_stale_reasons") or []
    if previous_stale_reasons and not summary["analysis"].get("previous_artifact_fresh_for_current_state"):
        lines.append(f"[tooling] previous_artifact_stale_reason={previous_stale_reasons[0]}")
    git = summary["git"]
    if git["available"]:
        lines.append(
            f"[tooling] branch={git['branch']} upstream={git['upstream']} dirty={git['dirty']} protected={git['protected_branch']}"
        )
    if summary["target"] == "repo-brief":
        lines.append(f"[tooling] targets={', '.join(summary['targets']['available']) or 'none'}")
        lines.append(
            f"[tooling] workflows={', '.join(summary['workflows']['tooling_workflows'] or summary['workflows']['all_workflows']) or 'none'}"
        )
        lines.append(
            f"[tooling] repo_local_agents={summary['repo']['repo_local_agents_path'] or 'none'}"
        )
        python_runtime = summary["repo"].get("python_runtime", {})
        if python_runtime:
            lines.append(
                "[tooling] python_runtime="
                f"{python_runtime.get('manager', 'none')} preferred={python_runtime.get('preferred_python_command') or 'none'} "
                f"raw_python_allowed={python_runtime.get('raw_python_allowed', False)}"
            )
        github = summary["github"]
        gh_state = "authenticated" if github["authenticated"] else github["error"] or "unavailable"
        lines.append(f"[tooling] gh={gh_state}")
    active_lane = summary["analysis"].get("active_lane", {})
    if active_lane.get("name"):
        lane_state = "fresh" if active_lane.get("brief_fresh") else "stale"
        lines.append(
            f"[tooling] lane={active_lane['name']} brief={active_lane.get('brief_target') or 'none'} lane_state={lane_state}"
        )
        if active_lane.get("brief_artifact"):
            lines.append(f"[tooling] lane_artifact={active_lane['brief_artifact']}")
    previous_summary = summary["analysis"].get("previous_summary") or {}
    if summary["analysis"].get("same_signature_as_previous") and previous_summary.get("summary_json"):
        lines.append(f"[tooling] previous_same_signature={previous_summary['summary_json']}")
    if summary["analysis"].get("same_failure_as_previous") and previous_summary.get("summary_json"):
        lines.append(f"[tooling] previous_same_failure={previous_summary['summary_json']}")
    if summary["analysis"].get("artifact_path"):
        lines.append(f"[tooling] artifact_path={summary['analysis']['artifact_path']}")
    if summary["analysis"].get("preferred_existing_artifact"):
        lines.append(f"[tooling] preferred_existing_artifact={summary['analysis']['preferred_existing_artifact']}")
    if summary["analysis"].get("loop_suppression_reason"):
        lines.append(f"[tooling] loop_suppression_reason={summary['analysis']['loop_suppression_reason']}")
    for prep_step in summary.get("prep_steps", [])[:3]:
        lines.append(f"[tooling] prep={prep_step['name']}:{prep_step['status']}:{prep_step['note']}")
    for blocker in summary["blockers"][:3]:
        lines.append(f"[tooling] blocker={blocker}")
    for finding in summary["findings"][:3]:
        lines.append(f"[tooling] finding={finding}")
    for action in summary["next_actions"][:3]:
        lines.append(f"[tooling] next={action}")
    print("\n".join(lines))


def diagnostic_signal_text(summary: dict[str, Any]) -> str:
    previous_summary = summary["analysis"].get("previous_summary") or {}
    pieces: list[str] = []
    pieces.extend(str(item) for item in summary.get("blockers", []))
    pieces.extend(str(item) for item in summary.get("findings", []))
    for step in summary.get("prep_steps", []) + summary.get("steps", []):
        if step.get("status") in {"fail", "warn"}:
            pieces.append(str(step.get("note", "")))
            pieces.append(str(step.get("command", "")))
    pieces.append(str(previous_summary.get("failure_excerpt", "")))
    pieces.append(str(previous_summary.get("recommended_next_command", "")))
    return "\n".join(piece for piece in pieces if piece).lower()


def diagnostic_next_action(summary: dict[str, Any]) -> str:
    repeated_failure = bool(
        summary["analysis"].get("same_failure_as_previous")
        or str(summary["analysis"].get("rerun_policy") or "").startswith(("reused", "force-required"))
    )
    if not repeated_failure:
        return ""
    signal_text = diagnostic_signal_text(summary)
    repo_id = str(summary["repo"].get("repo_id") or "").strip()
    has_domain_signal = any(term in signal_text for term in DIAGNOSTIC_FAILURE_TERMS)
    if has_domain_signal and repo_id == "waifu-stack":
        return 'run `make checkpoint-diagnostic-brief SUBJECT="${SUBJECT:-vix}" CONTROL="${CONTROL:-Nova Anime}" SYMPTOM="${SYMPTOM:-black-frame}"` before another broad verify or review-ready rerun'
    broad_target = summary.get("target") in HEAVY_RERUN_TARGETS or summary.get("target") == "review-ready"
    if has_domain_signal or broad_target:
        artifact_hint = str(
            summary["analysis"].get("preferred_existing_artifact")
            or summary["analysis"].get("artifact_path")
            or summary["artifacts"].get("latest_index")
            or ""
        ).strip()
        control_hint = f" --control {shlex.quote(artifact_hint)}" if artifact_hint else " --control <known-good-control>"
        return (
            f"run `tpl-diagnostic-brief --repo {repo_id} --subject {summary.get('target') or '<failing-subject>'}"
            f"{control_hint} --symptom <same-failure>` before another broad verify or review-ready rerun"
        )
    return ""


def command_failure_advisories(summary: dict[str, Any]) -> list[str]:
    signal_text = diagnostic_signal_text(summary)
    actions: list[str] = []
    repo_root = Path(str(summary.get("repo", {}).get("root") or "."))
    for step in summary.get("prep_steps", []) + summary.get("steps", []):
        if step.get("status") not in {"fail", "warn"}:
            continue
        advice = python_route_advice(
            str(step.get("command") or ""),
            repo_root,
            repo_cfg=summary.get("repo", {}),
            targets=summary.get("targets", {}),
        )
        if advice and advice not in actions:
            actions.append(advice)
    for terms, action in COMMAND_FAILURE_ADVISORIES:
        if any(term in signal_text for term in terms):
            actions.append(action)
    return actions


def artifact_review_next_action(summary: dict[str, Any]) -> str:
    analysis = summary.get("analysis", {})
    artifact_hint = str(
        analysis.get("preferred_existing_artifact")
        or analysis.get("artifact_path")
        or summary.get("artifacts", {}).get("latest_index")
        or ""
    ).strip()
    if not artifact_hint:
        return ""
    if analysis.get("artifact_review_required") or analysis.get("same_signature_as_previous") or analysis.get("same_failure_as_previous"):
        reason = str(analysis.get("loop_suppression_reason") or "same signature or failure repeated").strip()
        return f"review `{artifact_hint}` first; {reason}"
    return ""


def default_next_actions(summary: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    git = summary["git"]
    local_only_git = repo_uses_local_only_git_policy(summary)
    if not git["available"]:
        actions.append("initialize or enter a git worktree before relying on branch or PR context")
        return actions
    previous_summary = summary["analysis"].get("previous_summary")
    rerun_policy = str(summary["analysis"].get("rerun_policy") or "").strip()
    active_lane = summary["analysis"].get("active_lane", {})
    lane_name = str(active_lane.get("name") or "").strip()
    artifact_action = artifact_review_next_action(summary)
    if artifact_action:
        actions.append(artifact_action)
    diagnostic_action = diagnostic_next_action(summary)
    if diagnostic_action:
        actions.append(diagnostic_action)
    actions.extend(command_failure_advisories(summary))
    if previous_summary and previous_summary.get("run_signature") == summary["analysis"]["run_signature"]:
        if not artifact_action:
            previous_artifact = previous_summary.get("summary_json") or previous_summary.get("artifact_path") or "the previous artifact"
            actions.append(f"review `{previous_artifact}` before rerunning unchanged `{summary['target']}` work")
        if summary["target"] in HEAVY_RERUN_TARGETS and not lane_name:
            if rerun_policy == "force-required-unchanged-state":
                actions.append(f"set FORCE_RERUN=1 make {summary['target']} only if the unchanged artifact is no longer sufficient")
            else:
                actions.append(f"set FORCE_RERUN=1 make {summary['target']} only after reviewing the unchanged artifact")
    if lane_name:
        brief_target = str(active_lane.get("brief_target") or "").strip()
        fast_target = str(active_lane.get("fast_target") or "").strip()
        repair_target = str(active_lane.get("repair_target") or "").strip()
        ci_target = str(active_lane.get("ci_target") or "").strip()
        heavy_targets = set(active_lane.get("heavy_targets", []))
        if summary["target"] == "repo-brief" and brief_target:
            actions.append(f"continue the active `{lane_name}` lane with `make {brief_target}`")
        if summary["target"] == brief_target and fast_target:
            actions.append(f"run make {fast_target} next for the active `{lane_name}` lane")
        if summary["target"] in heavy_targets and not active_lane.get("brief_fresh") and brief_target:
            actions.append(f"refresh the active `{lane_name}` lane with `make {brief_target}` before `{summary['target']}`")
        if summary["target"] == "verify-ci" and ci_target and ci_target != summary["target"]:
            actions.append(f"prefer `make {ci_target}` before the generic `make verify-ci` for `{lane_name}` work")
        if summary["analysis"].get("same_failure_as_previous") and repair_target:
            actions.append(f"use `make {repair_target}` to inspect or repair the unchanged `{lane_name}` failure")
        if summary["target"] not in {brief_target, fast_target, repair_target, ci_target} and fast_target:
            actions.append(f"prefer `make {fast_target}` over the generic verify ladder for active `{lane_name}` work")
    if git["protected_branch"] and git["dirty"]:
        actions.append("move local changes off the protected or integration branch before promotion or review")
    if git["upstream"] == "unavailable" and not local_only_git:
        actions.append("set an upstream or confirm that this repo is intentionally local-only")
    if summary["github"]["available"] and not summary["github"]["authenticated"]:
        actions.append("run gh auth status or gh auth login before depending on GitHub context")
    if "doctor" in summary["targets"]["available"]:
        actions.append("run make doctor when runtime readiness is uncertain")
    if summary["target"] in {"verify-ci", "verify"} and "bootstrap-ci" in summary["targets"]["available"]:
        actions.append("run make bootstrap-ci in a fresh environment before rerunning verification")
    if summary["target"] == "verify-security" and "bootstrap-security" in summary["targets"]["available"]:
        actions.append("run make bootstrap-security before rerunning security checks on a fresh runner")
        if summary["analysis"].get("reused_step_artifacts"):
            actions.append("review the reused security step artifacts before forcing another full scanner pass")
    if summary["target"] == "verify-container" and "bootstrap-container" in summary["targets"]["available"]:
        actions.append("run make bootstrap-container before rerunning container checks on a fresh runner")
    if not lane_name and "verify-fast" in summary["targets"]["available"]:
        actions.append("run make verify-fast before broader shell exploration")
    if not diagnostic_action and not lane_name and "review-ready" in summary["targets"]["available"] and summary["target"] != "review-ready":
        actions.append("run make review-ready before opening or updating a PR")
    review_scope = summary["environment"].get("review_ready_scope", "core")
    if summary["target"] == "review-ready" and review_scope == "core":
        actions.append("rerun REVIEW_READY_SCOPE=full make review-ready for container, SBOM, and CI-local detail")
    repo_hint = DOMAIN_LANE_HINTS.get(summary["repo"]["repo_id"])
    if repo_hint:
        actions.append(repo_hint)
    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped[:5]


def unchanged_rerun_policy(
    *,
    target_name: str,
    target_kind: str,
    force_rerun: bool,
    previous_summary: dict[str, Any] | None,
    current_state: str,
    current_run_signature: str = "",
) -> str:
    if force_rerun:
        return ""
    if target_name not in HEAVY_RERUN_TARGETS and target_kind != "review-ready":
        return ""
    previous_summary = previous_summary or {}
    previous_state = str(previous_summary.get("repo_state_fingerprint") or previous_summary.get("state_fingerprint") or "").strip()
    if not previous_summary or not previous_state or previous_state != current_state:
        return ""
    if current_run_signature:
        previous_signature = str(previous_summary.get("run_signature") or "").strip()
        if not previous_signature or previous_signature != current_run_signature:
            return ""
    previous_policy = str(previous_summary.get("rerun_policy") or "").strip()
    if previous_policy in {"reused-unchanged-state", "force-required-unchanged-state"}:
        return "force-required-unchanged-state"
    return "reused-unchanged-state"


def reuse_previous_run(summary: dict[str, Any], *, policy: str) -> None:
    previous_summary = summary["analysis"].get("previous_summary") or {}
    previous_status = str(previous_summary.get("status") or "warn").strip()
    if previous_status not in {"pass", "warn", "fail", "skipped", "not_applicable", "unavailable"}:
        previous_status = "warn"
    summary["status"] = previous_status
    summary["analysis"]["same_signature_as_previous"] = previous_summary.get("run_signature") == summary["analysis"]["run_signature"]
    summary["analysis"]["same_failure_as_previous"] = bool(previous_summary.get("failure_fingerprint"))
    summary["analysis"]["failure_fingerprint"] = str(previous_summary.get("failure_fingerprint") or "").strip()
    summary["analysis"]["artifact_path"] = str(
        previous_summary.get("artifact_path")
        or previous_summary.get("summary_json")
        or previous_summary.get("summary_md")
        or ""
    ).strip()
    artifact_hint = summary["analysis"].get("artifact_path") or summary["artifacts"]["latest_index"]
    summary["analysis"]["artifact_review_required"] = True
    summary["analysis"]["preferred_existing_artifact"] = str(artifact_hint)
    summary["analysis"]["loop_suppression_reason"] = policy
    summary["analysis"]["reused_previous_artifact"] = True
    summary["analysis"]["artifact_fresh_for_current_state"] = True
    summary["analysis"]["artifact_stale_reasons"] = []
    summary["analysis"]["rerun_policy"] = policy
    if policy == "force-required-unchanged-state":
        summary["status"] = combine_status(summary["status"], "warn")
        summary["findings"].append(
            f"repeated unchanged heavy target rerun suppressed again; review `{artifact_hint}` and set FORCE_RERUN=1 for a deliberate rerun"
        )
        return
    summary["findings"].append(f"unchanged heavy target rerun suppressed; reuse `{artifact_hint}` unless FORCE_RERUN=1 is required")


def apply_lane_advisories(summary: dict[str, Any]) -> None:
    active_lane = summary["analysis"].get("active_lane", {})
    lane_name = str(active_lane.get("name") or "").strip()
    if not lane_name:
        return
    brief_target = str(active_lane.get("brief_target") or "").strip()
    repair_target = str(active_lane.get("repair_target") or "").strip()
    ci_target = str(active_lane.get("ci_target") or "").strip()
    heavy_targets = set(active_lane.get("heavy_targets", []))
    if summary["target"] in heavy_targets and not active_lane.get("brief_fresh"):
        summary["status"] = combine_status(summary["status"], "warn")
        summary["findings"].append(
            f"active `{lane_name}` lane has no fresh `{brief_target}` artifact; prefer the lane brief before `{summary['target']}`"
        )
    if summary["target"] == "verify-ci" and ci_target and ci_target != "verify-ci":
        summary["status"] = combine_status(summary["status"], "warn")
        summary["findings"].append(
            f"active `{lane_name}` lane has a narrower CI surface: prefer `make {ci_target}` before the generic `make verify-ci`"
        )
    if summary["analysis"].get("same_failure_as_previous") and repair_target:
        summary["status"] = combine_status(summary["status"], "warn")
        summary["findings"].append(
            f"unchanged `{lane_name}` failure fingerprint detected; inspect `make {repair_target}` before rerunning the same target"
        )


def populate_step_runtime_analysis(summary: dict[str, Any]) -> None:
    ranked: list[dict[str, Any]] = []
    for step in summary.get("prep_steps", []) + summary.get("steps", []):
        duration = float(step.get("duration_seconds") or 0.0)
        if step.get("reused_previous_step_artifact"):
            duration = float(step.get("previous_duration_seconds") or duration)
        ranked.append(
            {
                "name": step.get("name", ""),
                "status": step.get("status", ""),
                "category": step.get("category", ""),
                "duration_seconds": round(duration, 3),
                "reused_previous_step_artifact": bool(step.get("reused_previous_step_artifact")),
            }
        )
    ranked.sort(key=lambda item: float(item.get("duration_seconds") or 0.0), reverse=True)
    summary["analysis"]["slow_steps"] = ranked[:5]
    if summary.get("target") != "verify-security":
        return
    reused = summary["analysis"].get("reused_step_artifacts") or []
    if reused:
        summary["findings"].append(
            "security step reuse saved approximately "
            f"{summary['analysis'].get('step_reuse_saved_seconds', 0.0)}s across {len(reused)} fresh step artifacts"
        )
    hotspots = [
        f"{item['name']}={item['duration_seconds']}s"
        for item in ranked[:3]
        if float(item.get("duration_seconds") or 0.0) > 0
    ]
    if hotspots:
        summary["findings"].append("security runtime hotspots: " + ", ".join(hotspots))


def populate_production_efficiency_analysis(summary: dict[str, Any]) -> None:
    steps = summary.get("prep_steps", []) + summary.get("steps", [])
    full_log_steps = [step for step in steps if step.get("full_log_path") or step.get("log_path")]
    long_log_steps = [step for step in steps if step.get("long_log_summary_required")]
    raw_log_tokens = sum(int(step.get("full_log_token_estimate") or 0) for step in steps)
    same_failure = bool(summary.get("analysis", {}).get("same_failure_as_previous"))
    next_actions_text = " ".join(str(item) for item in summary.get("next_actions", []))
    diagnostic_required = same_failure or "tpl-diagnostic-brief" in next_actions_text or "investigation-ledger" in next_actions_text
    diagnostic_followed = any(
        "tpl-diagnostic-brief" in str(step.get("command", ""))
        or "investigation-ledger" in str(step.get("command", ""))
        or "diagnostic" in str(step.get("summary_path", ""))
        for step in steps
    )
    summary["analysis"]["production_efficiency"] = {
        "full_log_path_count": len(full_log_steps),
        "raw_log_token_estimate": raw_log_tokens,
        "long_log_summary_required_count": len(long_log_steps),
        "summary_missing_full_log_path": any(step.get("status") in {"fail", "warn"} and not step.get("full_log_path") for step in steps),
        "same_failure_diagnostic_required": diagnostic_required,
        "same_failure_retry_without_diagnostic": bool(diagnostic_required and not diagnostic_followed),
        "diagnostic_followed": diagnostic_followed,
        "long_log_thresholds": {
            "line_count": LONG_LOG_LINE_THRESHOLD,
            "token_estimate": LONG_LOG_TOKEN_THRESHOLD,
        },
        "decision_policy": "advisory-report-fail; commands are not shell-blocked",
    }


def _evidence_status_for_steps(steps: list[dict[str, Any]]) -> str:
    statuses = {str(step.get("status") or "").strip() for step in steps}
    if "fail" in statuses:
        return "fail"
    if "unavailable" in statuses:
        return "unavailable"
    if "warn" in statuses:
        return "warn"
    if "pass" in statuses:
        return "pass"
    return "not_applicable"


def build_security_evidence(summary: dict[str, Any]) -> dict[str, Any]:
    profile = summary.get("repo", {}).get("security_profile", {})
    if not isinstance(profile, dict):
        profile = {}
    steps = summary.get("steps", [])
    evidence: dict[str, Any] = {
        "profile": profile.get("name", "local-free-enterprise"),
        "schema_version": 1,
        "generated_at": summary.get("generated_at", ""),
        "source_target": summary.get("target", ""),
        "summary_json": summary.get("artifacts", {}).get("summary_json", ""),
        "certification_claimed": False,
        "paid_github_required": bool(profile.get("paid_github_required", False)),
        "saas_required": bool(profile.get("saas_required", False)),
        "private_codeql": profile.get("private_codeql", "disabled_no_paid_github_plan"),
        "sonarqube": profile.get("sonarqube", {}),
        "vendor_boundaries": profile.get("vendor_boundaries", {}),
        "categories": {},
    }
    policy_exceptions = profile.get("policy_exceptions", [])
    if not isinstance(policy_exceptions, list):
        policy_exceptions = []
    for category in SECURITY_EVIDENCE_CATEGORIES:
        if category == "exceptions":
            if policy_exceptions:
                evidence["categories"][category] = {
                    "status": "waived_with_reason",
                    "gate": "advisory",
                    "steps": [],
                    "exceptions": policy_exceptions,
                    "note": "adapter-declared security exceptions require review before promotion",
                }
            else:
                evidence["categories"][category] = {
                    "status": "not_applicable",
                    "gate": "advisory",
                    "steps": [],
                    "exceptions": [],
                    "note": "no adapter-declared exceptions",
                }
            continue
        matched = [
            step
            for step in steps
            if category in [str(item) for item in step.get("evidence_categories", [])]
        ]
        if not matched:
            evidence["categories"][category] = {
                "status": "not_applicable",
                "gate": "advisory",
                "steps": [],
                "note": "no declared local evidence step for this repo profile",
            }
            continue
        gate = "required" if any(step.get("required", True) for step in matched) else "advisory"
        evidence["categories"][category] = {
            "status": _evidence_status_for_steps(matched),
            "gate": gate,
            "steps": [
                {
                    "name": step.get("name", ""),
                    "status": step.get("status", ""),
                    "required": bool(step.get("required", True)),
                    "gate": step.get("gate", ""),
                    "category": step.get("category", ""),
                    "log_path": step.get("log_path", ""),
                    "summary_path": step.get("summary_path", ""),
                }
                for step in matched
            ],
            "note": "observed local scanner/control evidence; not a certification claim",
        }
    category_statuses = [
        str(item.get("status") or "")
        for item in evidence["categories"].values()
        if isinstance(item, dict)
    ]
    if "fail" in category_statuses:
        evidence["status"] = "fail"
    elif any(status in {"warn", "unavailable"} for status in category_statuses):
        evidence["status"] = "warn"
    else:
        evidence["status"] = "pass"
    return evidence


def security_waiver_requirement(child_target: str, child_summary: dict[str, Any]) -> dict[str, Any]:
    if child_target != "verify-security" or child_summary.get("status") != "warn":
        return {"required": False, "categories": [], "steps": [], "reason": ""}

    categories: list[str] = []
    evidence = child_summary.get("security_evidence", {})
    if isinstance(evidence, dict):
        for name, item in (evidence.get("categories") or {}).items():
            if not isinstance(item, dict) or name == "exceptions":
                continue
            if item.get("status") in {"warn", "fail"}:
                categories.append(str(name))

    scanner_steps: list[str] = []
    for step in child_summary.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        if step.get("status") not in {"warn", "fail"}:
            continue
        step_name = str(step.get("name") or "")
        if step_name in {"osv-scanner", "grype", "trivy-fs", "pip-audit"} or step.get("evidence_categories"):
            scanner_steps.append(step_name)

    required = bool(categories or scanner_steps)
    reason = ""
    if required:
        parts = []
        if categories:
            parts.append("security evidence categories: " + ", ".join(sorted(set(categories))))
        if scanner_steps:
            parts.append("scanner steps: " + ", ".join(sorted(set(scanner_steps))))
        reason = "; ".join(parts)
    return {
        "required": required,
        "categories": sorted(set(categories)),
        "steps": sorted(set(scanner_steps)),
        "reason": reason,
    }


def attach_security_evidence(summary: dict[str, Any]) -> None:
    if summary.get("target") != "verify-security":
        return
    previous = summary.get("analysis", {}).get("previous_summary", {})
    if summary.get("analysis", {}).get("reused_previous_artifact") and isinstance(previous, dict) and previous.get("security_evidence"):
        summary["security_evidence"] = previous["security_evidence"]
        summary["findings"].append("security evidence map reused from the fresh previous verify-security artifact")
        return
    summary["security_evidence"] = build_security_evidence(summary)


def run_brief_checks(root: Path, summary: dict[str, Any], artifact_dir: Path, target_cfg: dict[str, Any]) -> None:
    populate_brief_findings(summary)
    for index, step in enumerate(target_cfg.get("steps", []), start=1):
        run_step(root, summary, artifact_dir, step, index)
    if summary["git"]["available"] and summary["git"]["protected_branch"] and summary["git"]["dirty"]:
        summary["status"] = combine_status(summary["status"], "warn")
        summary["findings"].append("current branch is protected or integration-like and has local modifications")


def run_commands_target(root: Path, summary: dict[str, Any], artifact_dir: Path, target_cfg: dict[str, Any]) -> None:
    for index, step in enumerate(target_cfg.get("steps", []), start=1):
        run_step(root, summary, artifact_dir, step, index)


def run_composite_target(
    root: Path,
    config: dict[str, Any],
    summary: dict[str, Any],
    artifact_dir: Path,
    target_cfg: dict[str, Any],
) -> None:
    for index, child_target in enumerate(target_cfg.get("targets", []), start=1):
        child_summary = execute_target(root, config, child_target, nested=True)
        record_step(
            summary,
            name=child_target,
            status=child_summary["status"],
            command=f"make {child_target}",
            duration_seconds=0.0,
            log_path=None,
            required=True,
            category="target",
            note=f"child target status: {child_summary['status']}",
            nested_summary=child_summary["artifacts"]["summary_json"],
        )


def _review_ready_child_targets(target_cfg: dict[str, Any]) -> tuple[str, list[str], set[str]]:
    requested_scope = os.environ.get("REVIEW_READY_SCOPE", "core").strip().lower() or "core"
    if requested_scope not in {"core", "full"}:
        requested_scope = "core"
    child_targets = list(target_cfg["full_targets"] if requested_scope == "full" else target_cfg["core_targets"])
    advisory_targets = set(target_cfg.get("advisory_targets", []))
    return requested_scope, child_targets, advisory_targets


def run_review_ready(
    root: Path,
    config: dict[str, Any],
    summary: dict[str, Any],
    artifact_dir: Path,
    target_cfg: dict[str, Any],
) -> None:
    tooling_root = artifact_dir.parent
    removed_markdown_summaries = 0
    for stale_summary in tooling_root.glob("*/summary.md"):
        try:
            stale_summary.unlink()
            removed_markdown_summaries += 1
        except FileNotFoundError:
            continue
    if removed_markdown_summaries:
        summary["findings"].append(
            f"cleared {removed_markdown_summaries} stale tooling markdown summaries before review checks"
        )

    scope, child_targets, advisory_targets = _review_ready_child_targets(target_cfg)
    summary["findings"].append(f"review-ready scope: {scope}")
    prep_failed = False
    for index, step in enumerate(target_cfg.get("prep_steps", []), start=1):
        name = step.get("name") or f"prep-{index:02d}"
        required = bool(step.get("required", True))
        command = step.get("command", "")
        tool = step.get("tool")
        docker_args = step.get("docker_args")
        category = step.get("category", "prep")
        resolved_command = format_command(command, artifact_dir, root) if command else ""

        if step.get("mutates_branch") and not summary["environment"].get("tooling_allow_mutating_checks"):
            record_step(
                summary,
                name=name,
                status="warn",
                command=resolved_command or name,
                duration_seconds=0.0,
                log_path=None,
                required=False,
                category=category,
                note="tool hazard: branch-mutating check skipped; set TOOLING_ALLOW_MUTATING_CHECKS=1 only for an explicit mutating run",
                bucket="prep_steps",
            )
            continue

        if tool:
            launcher = resolve_tool(tool)
            if launcher is None:
                status = "fail" if required else "unavailable"
                record_step(
                    summary,
                    name=name,
                    status=status,
                    command=resolved_command or tool,
                    duration_seconds=0.0,
                    log_path=None,
                    required=required,
                    category=category,
                    note=missing_tool_note(summary, str(tool)),
                    bucket="prep_steps",
                )
                prep_failed = prep_failed or status == "fail"
                continue
            resolved_command = rewrite_command(tool, launcher, resolved_command)

        if docker_args:
            docker_launcher = resolve_docker()
            if docker_launcher is None:
                status = "fail" if required else "unavailable"
                record_step(
                    summary,
                    name=name,
                    status=status,
                    command=f"docker {docker_args}",
                    duration_seconds=0.0,
                    log_path=None,
                    required=required,
                    category=category,
                    note="docker bridge unavailable",
                    bucket="prep_steps",
                )
                prep_failed = prep_failed or status == "fail"
                continue
            resolved_command = f"{docker_launcher} {docker_args}"

        log_path = artifact_dir / "logs" / f"prep-{index:02d}-{name}.log"
        rc, duration = run_shell(resolved_command, cwd=root, log_path=log_path)
        status = "pass" if rc == 0 else ("fail" if required else "warn")
        record_step(
            summary,
            name=name,
            status=status,
            command=resolved_command,
            duration_seconds=duration,
            log_path=log_path,
            required=required,
            category=category,
            note=log_excerpt(log_path, failed=rc != 0),
            exit_code=rc,
            bucket="prep_steps",
        )
        prep_failed = prep_failed or status == "fail"

    if prep_failed:
        for child_target in child_targets:
            record_step(
                summary,
                name=child_target,
                status="skipped",
                command=f"make {child_target}",
                duration_seconds=0.0,
                log_path=None,
                required=child_target not in advisory_targets,
                category="target",
                note="skipped because review-ready prep failed",
            )
        return

    for child_target in child_targets:
        child_summary = execute_target(root, config, child_target, nested=True)
        child_status = child_summary["status"]
        note_prefix = "child target status"
        if child_target in advisory_targets and child_status == "fail":
            child_status = "warn"
            note_prefix = "advisory child target status"
        record_step(
            summary,
            name=child_target,
            status=child_status,
            command=f"make {child_target}",
            duration_seconds=0.0,
            log_path=None,
            required=child_target not in advisory_targets,
            category="target",
            note=f"{note_prefix}: {child_summary['status']}",
            nested_summary=child_summary["artifacts"]["summary_json"],
        )
    if scope == "core":
        extra_targets = [target for target in target_cfg.get("full_targets", []) if target not in child_targets]
        if extra_targets:
            summary["findings"].append(
                "full review surfaces are available via REVIEW_READY_SCOPE=full: " + ", ".join(extra_targets)
            )


def workflow_trigger_text(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("on:"):
            continue
        if stripped != "on:":
            return stripped.partition(":")[2].strip().lower()
        block: list[str] = []
        for child in lines[index + 1 :]:
            if child and not child.startswith((" ", "\t")) and not child.startswith("#"):
                break
            block.append(child)
        return "\n".join(block).lower()
    return ""


def run_ci_local(root: Path, summary: dict[str, Any], artifact_dir: Path) -> None:
    mode = os.environ.get("CI_LOCAL_MODE", "lint")
    workflows = summary["workflows"]["tooling_workflows"] or summary["workflows"]["all_workflows"]
    summary["findings"].append(f"ci-local mode: {mode}")
    if not workflows:
        record_step(
            summary,
            name="ci-local-workflows",
            status="not_applicable",
            command="discover workflows",
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category="ci-local",
            note="no workflows detected for ci-local",
        )
        return

    workflow_paths = [Path(summary["workflows"]["workflow_dir"]) / workflow for workflow in workflows]
    if mode in {"lint", ""}:
        dispatch_only = 0
        automatic = 0
        for path in workflow_paths:
            text = (root / path).read_text(encoding="utf-8")
            trigger_text = workflow_trigger_text(text)
            has_dispatch = "workflow_dispatch" in trigger_text
            has_auto = "pull_request" in trigger_text or "push" in trigger_text
            if has_dispatch and not has_auto:
                dispatch_only += 1
            elif has_auto:
                automatic += 1
        record_step(
            summary,
            name="ci-local-trigger-audit",
            status="pass",
            command="inspect .github/workflows trigger modes",
            duration_seconds=0.0,
            log_path=None,
            required=True,
            category="ci-local",
            note=f"workflow_dispatch_only={dispatch_only}; automatic={automatic}; workflows={len(workflow_paths)}",
        )
        workflow_args = " ".join(shlex.quote(str(path)) for path in workflow_paths)
        lint_steps = [
            ("ci-local-actionlint", "actionlint", f"actionlint {workflow_args}"),
            ("ci-local-zizmor", "zizmor", f"zizmor {workflow_args}"),
        ]
        policy_dir = root / "tooling" / "policies" / "conftest" / "github-actions"
        if policy_dir.exists():
            lint_steps.append(
                (
                    "ci-local-conftest",
                    "conftest",
                    f"conftest test --all-namespaces -p {shlex.quote(str(policy_dir.relative_to(root)))} {workflow_args}",
                )
            )
        yamllint_cfg = root / "tooling" / "configs" / "yamllint" / "yamllint.yaml"
        yamllint_cmd = (
            f"yamllint -c {shlex.quote(str(yamllint_cfg.relative_to(root)))} {workflow_args}"
            if yamllint_cfg.exists()
            else f"yamllint {workflow_args}"
        )
        lint_steps.append(("ci-local-yamllint", "yamllint", yamllint_cmd))
        for index, (name, tool, command) in enumerate(lint_steps, start=2):
            if resolve_tool(tool) is None:
                record_step(
                    summary,
                    name=name,
                    status="unavailable",
                    command=command,
                    duration_seconds=0.0,
                    log_path=None,
                    required=False,
                    category="ci-local",
                    note=f"{tool} is unavailable",
                )
                continue
            rc, duration = run_shell(command, cwd=root, log_path=artifact_dir / "logs" / f"{index:02d}-{name}.log")
            record_step(
                summary,
                name=name,
                status="pass" if rc == 0 else "fail",
                command=command,
                duration_seconds=duration,
                log_path=artifact_dir / "logs" / f"{index:02d}-{name}.log",
                required=True,
                category="ci-local",
                note=log_excerpt(artifact_dir / "logs" / f"{index:02d}-{name}.log", failed=rc != 0),
                exit_code=rc,
            )
        return

    if mode == "info":
        record_step(
            summary,
            name="ci-local-info",
            status="skipped",
            command="act <event> -W .github/workflows/<workflow>",
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category="ci-local",
            note="ci-local info mode; default lint mode runs workflow lint without GitHub runner credits; set CI_LOCAL_MODE=run to execute act",
        )
        return

    if mode != "run":
        record_step(
            summary,
            name="ci-local-mode",
            status="warn",
            command="CI_LOCAL_MODE",
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category="ci-local",
            note=f"unknown CI_LOCAL_MODE={mode}; use lint, info, or run",
        )
        return

    act_ready = shutil.which("act") is not None
    docker_launcher = resolve_docker()
    if not act_ready:
        record_step(
            summary,
            name="ci-local-act",
            status="unavailable",
            command="act",
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category="ci-local",
            note="act is unavailable",
        )
    if docker_launcher is None:
        record_step(
            summary,
            name="ci-local-docker",
            status="unavailable",
            command="docker info",
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category="ci-local",
            note="docker bridge unavailable for act",
        )
    if not act_ready or docker_launcher is None:
        summary["blockers"].append("ci-local run mode requires both act and a docker bridge")
        summary["status"] = combine_status(summary["status"], "fail")
        return

    workflow = os.environ.get("CI_LOCAL_WORKFLOW", workflows[0])
    event = os.environ.get("CI_LOCAL_EVENT", "pull_request")
    command = f"act {event} -W .github/workflows/{workflow}"
    job = os.environ.get("CI_LOCAL_JOB", "").strip()
    if job:
        command += f" -j {shlex.quote(job)}"
    step = {
        "name": "ci-local-run",
        "command": command,
        "required": True,
        "category": "ci-local",
        "tool": "act",
    }
    run_step(root, summary, artifact_dir, step, 1)


def _release_gate_target_branch(summary: dict[str, Any]) -> str:
    override = os.environ.get("RELEASE_GATE_TARGET_BRANCH", "").strip()
    if override:
        return override
    pr = summary.get("github", {}).get("pull_request")
    if isinstance(pr, dict):
        base = str(pr.get("baseRefName") or "").strip()
        if base:
            return base
    repo = summary.get("repo", {})
    for key in ("production_branch", "integration_branch", "default_branch"):
        value = str(repo.get(key) or "").strip()
        if value:
            return value
    return "unknown"


def _release_gate_record_status(child_status: str, *, required: bool) -> str:
    if child_status == "pass":
        return "pass"
    if child_status == "fail":
        return "fail"
    return "blocked" if required else "warn"


def run_release_gate_local(root: Path, config: dict[str, Any], summary: dict[str, Any], artifact_dir: Path, target_cfg: dict[str, Any]) -> None:
    child_targets = [str(target) for target in target_cfg.get("targets", [])]
    advisory_targets = {str(target) for target in target_cfg.get("advisory_targets", [])}
    current_head = str(summary.get("git", {}).get("head_sha") or "").strip()
    target_branch = _release_gate_target_branch(summary)
    github_actions_mode = str(summary.get("repo", {}).get("github_actions_mode") or "standard")
    tooling_workflows = list(summary.get("workflows", {}).get("tooling_workflows", []))
    expected_contexts = [
        TOOLING_WORKFLOW_CONTEXTS.get(workflow, workflow)
        for workflow in tooling_workflows
        if workflow in TOOLING_WORKFLOW_CONTEXTS or workflow.startswith("tooling-")
    ]
    branch_ref = str(summary.get("git", {}).get("branch") or "HEAD").strip() or "HEAD"
    release_gate: dict[str, Any] = {
        "github_actions_mode": github_actions_mode,
        "hosted_runner_minutes_policy": "local_first" if github_actions_mode in {"local_artifacts", "manual_hosted"} else "standard_hosted",
        "expected_remote_contexts": expected_contexts,
        "optional_dispatch_commands": [
            f"gh workflow run {workflow} --ref {branch_ref}"
            for workflow in tooling_workflows
            if workflow in TOOLING_WORKFLOW_CONTEXTS
        ],
        "remote_actions_authority": False,
        "manual_human_gate_required": True,
        "target_branch": target_branch,
        "branch": summary.get("git", {}).get("branch", ""),
        "head_sha": current_head,
        "required_targets": [target for target in child_targets if target not in advisory_targets],
        "advisory_targets": sorted(advisory_targets),
        "evidence": [],
        "stale_evidence": [],
        "missing_evidence": [],
        "failed_targets": [],
        "blocked_targets": [],
        "security_waiver_required": False,
        "security_waiver_targets": [],
        "security_waiver_reasons": [],
        "final_decision": "pass",
        "reason": "Local deterministic artifacts are the release-gate evidence; GitHub Actions are advisory for private GitHub Free repos when hosted quota is blocked.",
    }
    summary["release_gate"] = release_gate
    summary["findings"].append("release-gate-local: GitHub Actions authority is advisory; a manual human gate is required before promotion")

    if not child_targets:
        release_gate["final_decision"] = "blocked"
        release_gate["missing_evidence"].append("no release-gate child targets configured")
        record_step(
            summary,
            name="release-gate-config",
            status="blocked",
            command="release-gate-local configuration",
            duration_seconds=0.0,
            log_path=None,
            required=True,
            category="release-gate",
            note="no release-gate child targets configured",
        )
        return

    previous_review_scope = os.environ.get("REVIEW_READY_SCOPE")
    try:
        for index, child_target in enumerate(child_targets, start=1):
            required = child_target not in advisory_targets
            if child_target == "review-ready":
                os.environ["REVIEW_READY_SCOPE"] = "full"
            child_summary = execute_target(root, config, child_target, nested=True)
            if child_target == "review-ready":
                if previous_review_scope is None:
                    os.environ.pop("REVIEW_READY_SCOPE", None)
                else:
                    os.environ["REVIEW_READY_SCOPE"] = previous_review_scope

            child_status = str(child_summary.get("status") or "unavailable")
            gate_status = _release_gate_record_status(child_status, required=required)
            waiver = security_waiver_requirement(child_target, child_summary)
            if waiver["required"]:
                gate_status = "blocked"
                release_gate["security_waiver_required"] = True
                release_gate["security_waiver_targets"].append(child_target)
                release_gate["security_waiver_reasons"].append(f"{child_target}: {waiver['reason']}")
                summary["findings"].append(
                    f"{child_target}: security waiver required before promotion: {waiver['reason']}"
                )
            child_head = str(child_summary.get("git", {}).get("head_sha") or "").strip()
            artifact_matches = bool(current_head and child_head and child_head == current_head)
            nested_summary = str(child_summary.get("artifacts", {}).get("summary_json") or "")
            evidence_row = {
                "target": child_target,
                "status": child_status,
                "gate_status": gate_status,
                "required": required,
                "summary_path": nested_summary,
                "artifact_head_sha": child_head,
                "artifact_head_matches_current": artifact_matches,
                "security_waiver_required": bool(waiver["required"]),
                "security_waiver_reason": waiver["reason"],
            }
            release_gate["evidence"].append(evidence_row)
            if not nested_summary:
                release_gate["missing_evidence"].append(child_target)
            if current_head and child_head and child_head != current_head:
                release_gate["stale_evidence"].append(child_target)
                if gate_status == "pass" and required:
                    gate_status = "blocked"
                    evidence_row["gate_status"] = gate_status
            if gate_status == "fail":
                release_gate["failed_targets"].append(child_target)
            elif gate_status == "blocked":
                release_gate["blocked_targets"].append(child_target)
            command = "REVIEW_READY_SCOPE=full make review-ready" if child_target == "review-ready" else f"make {child_target}"
            record_step(
                summary,
                name=child_target,
                status=gate_status,
                command=command,
                duration_seconds=0.0,
                log_path=None,
                required=required,
                category="release-gate",
                note=f"child target status: {child_status}; artifact head matches current: {artifact_matches}",
                nested_summary=nested_summary,
            )
    finally:
        if previous_review_scope is None:
            os.environ.pop("REVIEW_READY_SCOPE", None)
        else:
            os.environ["REVIEW_READY_SCOPE"] = previous_review_scope

    if release_gate["failed_targets"]:
        release_gate["final_decision"] = "fail"
    elif release_gate["blocked_targets"] or release_gate["missing_evidence"] or release_gate["stale_evidence"]:
        release_gate["final_decision"] = "blocked"
        summary["status"] = combine_status(summary["status"], "blocked")
    else:
        release_gate["final_decision"] = "pass"


def run_watch(root: Path, summary: dict[str, Any], artifact_dir: Path, target_cfg: dict[str, Any]) -> None:
    commands = target_cfg.get("commands", [])
    if not commands:
        record_step(
            summary,
            name="watch-config",
            status="not_applicable",
            command="watch configuration",
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category="watch",
            note="no watch commands declared",
        )
        return
    joined = " && ".join(commands)
    summary["findings"].append(f"watch command: {joined}")
    if os.environ.get("WATCH_MODE", "show") != "run":
        record_step(
            summary,
            name="watch-show",
            status="skipped",
            command=joined,
            duration_seconds=0.0,
            log_path=None,
            required=False,
            category="watch",
            note="watch mode is show",
        )
        return
    if shutil.which("watchexec") is None:
        summary["status"] = combine_status(summary["status"], "fail")
        summary["blockers"].append("watchexec is required for WATCH_MODE=run")
        return
    step = {
        "name": "watch",
        "command": f"watchexec --restart --clear --shell=bash -- {shlex.quote(joined)}",
        "required": True,
        "category": "watch",
    }
    run_step(root, summary, artifact_dir, step, 1)


def execute_target(root: Path, config: dict[str, Any], target: str, *, nested: bool = False) -> dict[str, Any]:
    target_cfg = config["targets"].get(target)
    if target_cfg is None:
        raise SystemExit(f"unknown tooling target: {target}")

    artifact_dir, log_root = make_artifact_dir(root, target)
    summary = collect_base_summary(root, config, target, artifact_dir, log_root)
    summary["artifacts"]["summary_json"] = str(artifact_dir / "summary.json")
    summary["artifacts"]["summary_md"] = str(artifact_dir / "summary.md")

    kind = target_cfg["kind"]
    rerun_policy = unchanged_rerun_policy(
        target_name=str(summary.get("target") or ""),
        target_kind=str(kind),
        force_rerun=bool(summary["environment"].get("force_rerun")),
        previous_summary=summary["analysis"].get("previous_summary"),
        current_state=str(summary["analysis"].get("repo_state_fingerprint") or summary["git"].get("state_fingerprint") or "").strip(),
        current_run_signature=str(summary["analysis"].get("run_signature") or ""),
    )
    if rerun_policy and not summary["analysis"].get("previous_artifact_fresh_for_current_state"):
        stale_reasons = summary["analysis"].get("previous_artifact_stale_reasons") or ["previous artifact is stale"]
        summary["findings"].append(
            "previous artifact was not reused because it is stale: " + "; ".join(str(reason) for reason in stale_reasons[:4])
        )
        rerun_policy = ""
    if rerun_policy:
        reuse_previous_run(summary, policy=rerun_policy)
    else:
        if summary["environment"].get("force_rerun"):
            summary["analysis"]["rerun_policy"] = "forced-rerun"
        if kind == "brief":
            run_brief_checks(root, summary, artifact_dir, target_cfg)
        elif kind == "commands":
            run_commands_target(root, summary, artifact_dir, target_cfg)
        elif kind == "composite":
            run_composite_target(root, config, summary, artifact_dir, target_cfg)
        elif kind == "review-ready":
            run_review_ready(root, config, summary, artifact_dir, target_cfg)
        elif kind == "ci-local":
            run_ci_local(root, summary, artifact_dir)
        elif kind == "release-gate-local":
            run_release_gate_local(root, config, summary, artifact_dir, target_cfg)
        elif kind == "watch":
            run_watch(root, summary, artifact_dir, target_cfg)
        else:
            raise SystemExit(f"unsupported tooling target kind: {kind}")
        summary["analysis"]["artifact_fresh_for_current_state"] = True
        summary["analysis"]["artifact_stale_reasons"] = []

    previous_summary = summary["analysis"].get("previous_summary")
    if previous_summary and previous_summary.get("run_signature") == summary["analysis"]["run_signature"]:
        summary["analysis"]["same_signature_as_previous"] = True
        previous_artifact = str(previous_summary.get("summary_json") or previous_summary.get("artifact_path") or "").strip()
        if previous_artifact:
            summary["analysis"]["preferred_existing_artifact"] = previous_artifact
        summary["analysis"]["artifact_review_required"] = True
        summary["analysis"]["loop_suppression_reason"] = "same target signature as previous run"
        summary["findings"].append("same target signature as the previous run; prefer the prior artifact when no new state changed")
    if not summary["analysis"].get("failure_fingerprint"):
        summary["analysis"]["failure_fingerprint"] = compute_failure_fingerprint(summary)
    if (
        previous_summary
        and previous_summary.get("failure_fingerprint")
        and previous_summary.get("failure_fingerprint") == summary["analysis"]["failure_fingerprint"]
    ):
        summary["analysis"]["same_failure_as_previous"] = True
        previous_artifact = str(previous_summary.get("summary_json") or previous_summary.get("artifact_path") or "").strip()
        if previous_artifact:
            summary["analysis"]["preferred_existing_artifact"] = previous_artifact
        summary["analysis"]["artifact_review_required"] = True
        existing_reason = str(summary["analysis"].get("loop_suppression_reason") or "").strip()
        failure_reason = "same failure fingerprint as previous run"
        summary["analysis"]["loop_suppression_reason"] = (
            f"{existing_reason}; {failure_reason}" if existing_reason and failure_reason not in existing_reason else failure_reason
        )
        summary["findings"].append("same failure fingerprint as the previous run; inspect the existing artifact before retrying")
    summary["analysis"]["active_lane"] = load_active_lane(root, config["repo"], summary["git"])
    apply_lane_advisories(summary)
    populate_step_runtime_analysis(summary)
    attach_security_evidence(summary)
    summary["next_actions"] = default_next_actions(summary)
    populate_production_efficiency_analysis(summary)
    summary["analysis"]["artifact_path"] = summary["analysis"].get("artifact_path") or summary["artifacts"]["summary_json"]
    summary["analysis"]["recommended_next_command"] = summary["next_actions"][0] if summary["next_actions"] else ""
    write_summary(summary, artifact_dir)
    if not nested:
        print_summary(summary, artifact_dir)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run generated repo-local tooling targets with structured summaries.")
    parser.add_argument("target", help="Target name such as repo-brief or verify-fast")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    config = read_json(root / "tooling" / "configs" / "tooling-targets.json")
    summary = execute_target(root, config, args.target, nested=False)
    raise SystemExit(0 if summary["status"] not in {"fail", "blocked"} else 2)


if __name__ == "__main__":
    main()
