"""Read-only name diagnostics and narrowly reviewed, nonrecursive directory removal."""
from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Any

from worktree_hygiene import _process_cwds, consumer_in_use


def suspicious_root_names(names: list[str]) -> list[dict[str, str]]:
    """Names are investigation signals, never authority to delete."""
    commands = {"python", "python3", "bash", "mkdir", "unlock"}
    cluster = len(commands.intersection(names)) >= 2
    return [
        {"path": name, "code": "argument_shaped_root" if name.lstrip().startswith("--") else "command_token_cluster",
         "severity": "warn", "disposition": "investigate_only"}
        for name in sorted(names)
        if name.lstrip().startswith("--") or (cluster and name in commands)
    ]


def directory_identity(info: os.stat_result) -> dict[str, int]:
    return {key: getattr(info, "st_" + key) for key in ("dev", "ino", "uid", "mode", "mtime_ns", "ctime_ns")}


def empty_directory_action(path: Path, workspace: Path, *, provenance: str) -> dict[str, Any]:
    workspace = workspace.resolve(strict=True)
    if path.parent != workspace or path.is_symlink() or not provenance.strip():
        raise ValueError("exact direct workspace path and accidental provenance required")
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or any(path.iterdir()):
        raise ValueError("not an owned empty directory")
    return {"id": f"empty-directory:{path.name}", "type": "remove_empty_accidental_directory",
            "source_path": str(path), "expected_parent": directory_identity(workspace.stat()),
            "expected_identity": directory_identity(info), "provenance": provenance,
            "safety": "reviewed_empty_directory_only"}


def apply_empty_directory_removal(action: dict[str, Any], workspace: Path, *, process_evidence: dict | None = None) -> dict:
    """Pin the parent and child with descriptors; rmdir never gets a recursive fallback."""
    result = {"id": action.get("id"), "status": "refused"}
    try:
        workspace = workspace.resolve(strict=True)
        path = Path(str(action["source_path"]))
        if path.parent != workspace or path.name in {".", "..", ".git", ".codex"}:
            raise ValueError("not_an_eligible_direct_child")
        if action.get("safety") != "reviewed_empty_directory_only" or not action.get("provenance", "").strip():
            raise ValueError("accidental_provenance_required")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        parent_fd = os.open(workspace, flags)
        try:
            parent = directory_identity(os.fstat(parent_fd))
            # Adding/removing siblings changes parent timestamps, not its identity.
            if any(parent[key] != action["expected_parent"][key] for key in ("dev", "ino", "uid", "mode")):
                raise ValueError("parent_identity_changed")
            child_fd = os.open(path.name, flags, dir_fd=parent_fd)
            try:
                identity = directory_identity(os.fstat(child_fd))
                if identity != action["expected_identity"] or identity["uid"] != os.getuid():
                    raise ValueError("directory_identity_or_owner_changed")
                if os.listdir(child_fd):
                    raise ValueError("directory_not_empty")
                evidence = {"known": True, "paths": _process_cwds()} if process_evidence is None else process_evidence
                if not evidence.get("known") or consumer_in_use(path, evidence):
                    raise ValueError("directory_process_in_use_or_unknown")
                if directory_identity(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != identity:
                    raise ValueError("directory_identity_changed")
                os.rmdir(path.name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            finally:
                os.close(child_fd)
        finally:
            os.close(parent_fd)
        return {**result, "status": "applied", "path": str(path)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {**result, "reason": str(error)}
