from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path
from typing import Any


_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _normalize_command(command: str) -> str:
    return " ".join(str(command or "").strip().split())


def command_body(command: str) -> str:
    normalized = _normalize_command(command)
    if not normalized:
        return ""
    try:
        parts = shlex.split(normalized)
    except ValueError:
        return normalized
    index = 0
    while index < len(parts) and _ENV_ASSIGNMENT.match(parts[index]):
        index += 1
    if index >= len(parts):
        return ""
    return shlex.join(parts[index:])


def python_command_class(command: str) -> str:
    body = command_body(command)
    if body.startswith("uv run python "):
        return "uv_python"
    if body == "uv run python":
        return "uv_python"
    if body.startswith("uv run pytest") or body == "uv run pytest":
        return "uv_pytest"
    if body.startswith("./.venv/bin/python ") or body == "./.venv/bin/python":
        return "venv_python"
    if body.startswith(".venv/bin/python ") or body == ".venv/bin/python":
        return "venv_python"
    if body.startswith("python3 ") or body == "python3":
        return "python3"
    if body.startswith("python ") or body == "python":
        return "raw_python"
    return "other"


def command_uses_uv_python(command: str) -> bool:
    return python_command_class(command) in {"uv_python", "uv_pytest"} or command_body(command).startswith("uv sync")


def _target_commands(targets: dict[str, Any] | None) -> list[str]:
    commands: list[str] = []
    if not isinstance(targets, dict):
        return commands
    for cfg in targets.values():
        if not isinstance(cfg, dict):
            continue
        for step_key in ("prep_steps", "steps"):
            for step in cfg.get(step_key, []):
                if isinstance(step, dict) and isinstance(step.get("command"), str):
                    commands.append(step["command"])
        for command in cfg.get("commands", []):
            if isinstance(command, str):
                commands.append(command)
    return commands


def runtime_info(root: Path, repo_cfg: dict[str, Any] | None = None, targets: dict[str, Any] | None = None) -> dict[str, Any]:
    repo_cfg = repo_cfg if isinstance(repo_cfg, dict) else {}
    declared = repo_cfg.get("python_runtime") if isinstance(repo_cfg.get("python_runtime"), dict) else {}
    commands = _target_commands(targets)
    markers: list[str] = []

    uv_lock = root / "uv.lock"
    pyproject = root / "pyproject.toml"
    venv_python = root / ".venv" / "bin" / "python"
    if uv_lock.exists():
        markers.append("uv.lock")
    if pyproject.exists():
        markers.append("pyproject.toml")
    if venv_python.exists():
        markers.append(".venv/bin/python")
    if any(command_uses_uv_python(command) for command in commands):
        markers.append("uv_command")
    if any(python_command_class(command) == "venv_python" for command in commands):
        markers.append("venv_command")

    manager = str(declared.get("manager") or "").strip()
    if not manager:
        if "uv.lock" in markers or "uv_command" in markers:
            manager = "uv"
        elif ".venv/bin/python" in markers or "venv_command" in markers:
            manager = "venv"
        elif "pyproject.toml" in markers:
            manager = "python3"
        else:
            manager = "none"

    preferred = str(declared.get("preferred_python_command") or "").strip()
    notebook = str(declared.get("notebook_inspection_command") or "").strip()
    test_command = str(declared.get("test_command") or "").strip()
    fallback = str(declared.get("fallback_python_command") or "python3").strip()

    if manager == "uv":
        preferred = preferred or "uv run python"
        notebook = notebook or preferred
        test_command = test_command or "uv run pytest"
        raw_allowed = False
        python3_valid = False
        route_note = "uv project detected; use uv so dependencies and project settings are active"
    elif manager == "venv":
        preferred = preferred or "./.venv/bin/python"
        notebook = notebook or preferred
        test_command = test_command or "./.venv/bin/python -m pytest"
        raw_allowed = False
        python3_valid = False
        route_note = "virtualenv detected; use the repo virtualenv Python"
    elif manager == "python3":
        preferred = preferred or "python3"
        notebook = notebook or preferred
        test_command = test_command or "python3 -m pytest"
        raw_allowed = False
        python3_valid = True
        route_note = "Python project detected without a uv/venv contract; use python3 or repo-local make targets"
    else:
        preferred = preferred or ""
        notebook = notebook or preferred
        test_command = test_command or ""
        raw_allowed = False
        python3_valid = True
        route_note = "no repo Python runtime contract detected"

    if "raw_python_allowed" in declared:
        raw_allowed = bool(declared.get("raw_python_allowed"))
    if "python3_valid_for_repo" in declared:
        python3_valid = bool(declared.get("python3_valid_for_repo"))

    preferred_available = False
    if manager == "uv":
        preferred_available = shutil.which("uv") is not None
    elif manager == "venv":
        preferred_available = venv_python.exists()
    elif manager == "python3":
        preferred_available = shutil.which("python3") is not None
    elif preferred:
        try:
            first = shlex.split(preferred)[0]
        except (ValueError, IndexError):
            first = preferred.split(" ", 1)[0]
        preferred_available = shutil.which(first) is not None or (root / first).exists()

    return {
        "detected": manager != "none",
        "manager": manager,
        "source": str(declared.get("source") or ("declared_config" if declared else "repo_files_or_commands")),
        "markers": sorted(set(markers)),
        "preferred_python_command": preferred,
        "notebook_inspection_command": notebook,
        "test_command": test_command,
        "fallback_python_command": fallback,
        "raw_python_allowed": raw_allowed,
        "python3_valid_for_repo": python3_valid,
        "preferred_available": preferred_available,
        "uv_available": shutil.which("uv") is not None,
        "python3_available": shutil.which("python3") is not None,
        "raw_python_available": shutil.which("python") is not None,
        "route_note": str(declared.get("route_note") or route_note),
    }


def route_advice(command: str, root: Path, repo_cfg: dict[str, Any] | None = None, targets: dict[str, Any] | None = None) -> str:
    info = runtime_info(root, repo_cfg=repo_cfg, targets=targets)
    cls = python_command_class(command)
    preferred = str(info.get("preferred_python_command") or "").strip()
    if cls == "raw_python" and preferred:
        return f"use repo Python route `{preferred}`; do not retry raw `python` in this repo"
    if cls == "python3" and preferred and not bool(info.get("python3_valid_for_repo")):
        return f"use repo Python route `{preferred}` instead of `python3` for this repo"
    return ""
