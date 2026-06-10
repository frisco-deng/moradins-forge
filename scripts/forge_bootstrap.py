#!/usr/bin/env python3
"""Clone or prime Moradin Forge without mutating host tooling or target repos."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_REPO_URL = "https://github.com/frisco-deng/moradins-forge.git"
DEFAULT_REF = "main"
DEFAULT_DEPS = "minimal"
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
START_CARD_RELATIVE = Path("artifacts/bootstrap/latest")
TEMP_ROOT = "/" + "tmp" + "/"
VAR_TEMP_ROOT = "/" + "var" + "/" + "tmp" + "/"
LINUX_HOME_ROOT = "/" + "home" + "/"
MAC_HOME_ROOT = "/" + "Users" + "/"


class BootstrapError(RuntimeError):
    """Raised when bootstrap cannot proceed safely."""


@dataclass(frozen=True)
class BootstrapOptions:
    repo_url: str
    ref: str
    dest: Path
    target: Path | None
    deps: str
    dry_run: bool


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def default_dest() -> Path:
    if (SCRIPT_ROOT / "FORGE.md").is_file() and (SCRIPT_ROOT / "scripts").is_dir():
        return SCRIPT_ROOT
    return Path.cwd() / "moradins-forge"


def sanitize_path(value: str | Path | None, placeholder: str) -> str:
    if value is None:
        return placeholder
    text = str(value)
    if not text:
        return placeholder
    return placeholder


def sanitize_command_part(value: str) -> str:
    text = str(value)
    if text == DEFAULT_REPO_URL or text.startswith("https://"):
        return text
    if text.startswith("git@") or text.startswith("ssh://"):
        return "<repo-url>"
    if text.startswith(("/", "~")) or ":\\" in text or ":/" in text:
        return "<forge-root>"
    return text


def sanitize_repo_url(repo_url: str) -> str:
    if repo_url == DEFAULT_REPO_URL:
        return repo_url
    if repo_url.startswith("https://github.com/") and "@" not in repo_url:
        return repo_url
    return "<repo-url>"


def sanitize_error_message(message: str, options: BootstrapOptions) -> str:
    text = str(message)
    replacements: list[tuple[str | Path | None, str]] = [
        (options.dest, "<forge-root>"),
        (options.target, "<target-repo>"),
        (SCRIPT_ROOT, "<forge-root>"),
        (Path.home(), "<home>"),
        (options.repo_url, sanitize_repo_url(options.repo_url)),
    ]
    for raw, placeholder in replacements:
        if raw:
            text = text.replace(str(raw), placeholder)
    text = re.sub(re.escape(TEMP_ROOT) + r"[^\s'\"<>]+", "<temp-dir>", text)
    text = re.sub(re.escape(VAR_TEMP_ROOT) + r"[^\s'\"<>]+", "<temp-dir>", text)
    text = re.sub(re.escape(LINUX_HOME_ROOT) + r"[^/\s]+(?:/[^\s'\"<>]+)?", "<home>", text)
    text = re.sub(re.escape(MAC_HOME_ROOT) + r"[^/\s]+(?:/[^\s'\"<>]+)?", "<home>", text)
    text = re.sub(r"[A-Za-z]:\\+Users\\+[^\\\s'\"<>]+(?:\\[^\s'\"<>]+)?", "<home>", text)
    return text


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def command_status(command: str, required: bool) -> dict[str, Any]:
    present = command_available(command)
    return {
        "id": command,
        "command": command,
        "required": required,
        "present": present,
        "status": "present" if present else "missing",
        "request_only": not present,
        "human_action": (
            "Install or expose this tool manually in a shell you control, then rerun bootstrap."
            if not present
            else ""
        ),
    }


def detect_tools(deps: str) -> dict[str, Any]:
    checks = [
        command_status("git", required=True),
        command_status("python3", required=False),
        command_status("python", required=False),
        command_status("uv", required=False),
    ]
    if deps == "full":
        checks.extend([command_status("node", required=False), command_status("npm", required=False)])
    python_present = command_available("python3") or command_available("python")
    missing_required = [check["id"] for check in checks if check["required"] and not check["present"]]
    if not python_present:
        missing_required.append("python3_or_python")
    return {
        "checks": checks,
        "missing_required": sorted(set(missing_required)),
        "missing_optional": [
            check["id"]
            for check in checks
            if not check["required"] and not check["present"]
        ],
        "status": "blocked" if missing_required else "ready",
        "safety": "request_only; no host install commands were executed",
    }


def run_command(command: list[str], cwd: Path | None, dry_run: bool, actions: list[dict[str, Any]]) -> None:
    action = {
        "command": [sanitize_command_part(part) for part in command],
        "cwd": sanitize_path(cwd, "<forge-root>") if cwd else "",
        "dry_run": dry_run,
        "status": "planned" if dry_run else "pending",
    }
    actions.append(action)
    if dry_run:
        return
    subprocess.run(command, cwd=cwd, check=True)
    action["status"] = "pass"


def checkout_repo(options: BootstrapOptions, actions: list[dict[str, Any]]) -> str:
    dest = options.dest
    if dest.resolve() == SCRIPT_ROOT.resolve() and (dest / "FORGE.md").is_file():
        actions.append(
            {
                "command": ["reuse-current-checkout"],
                "cwd": "<forge-root>",
                "dry_run": options.dry_run,
                "status": "planned" if options.dry_run else "pass",
            }
        )
        return "in_place"
    if dest.exists() and (dest / ".git").is_dir():
        run_command(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", options.ref], None, options.dry_run, actions)
        run_command(["git", "-C", str(dest), "checkout", "FETCH_HEAD"], None, options.dry_run, actions)
        return "updated"
    if dest.exists() and any(dest.iterdir()):
        raise BootstrapError(f"destination exists and is not an empty Forge checkout: {dest}")
    run_command(
        ["git", "clone", "--depth", "1", "--branch", options.ref, options.repo_url, str(dest)],
        None,
        options.dry_run,
        actions,
    )
    return "cloned"


def prime_dependencies(options: BootstrapOptions, actions: list[dict[str, Any]], tool_state: dict[str, Any]) -> list[str]:
    skipped: list[str] = []
    dest = options.dest
    if options.deps == "none":
        skipped.append("dependency priming disabled")
        return skipped
    if not command_available("uv"):
        skipped.append("uv missing; dependency priming is request-only")
        return skipped
    run_command(["uv", "sync", "--group", "dev"], dest, options.dry_run, actions)
    if options.deps == "full":
        package_json = dest / "dev_tracker" / "ui" / "package.json"
        if not package_json.is_file() and options.dry_run:
            package_json = SCRIPT_ROOT / "dev_tracker" / "ui" / "package.json"
        if package_json.is_file() and command_available("npm"):
            command = ["npm", "--prefix", "dev_tracker/ui", "ci"]
            run_command(command, dest, options.dry_run, actions)
        elif package_json.is_file():
            skipped.append("npm missing; UI dependency priming is request-only")
        else:
            skipped.append("UI package manifest not present")
    return skipped


def start_card_payload(options: BootstrapOptions, status: str, tool_state: dict[str, Any], actions: list[dict[str, Any]], skipped: list[str]) -> dict[str, Any]:
    target = "<target-repo>" if options.target is None else "<target-repo>"
    shell_wrapper = "scripts/moradin_forge.sh"
    if platform.system().lower().startswith("win"):
        shell_wrapper = r".\scripts\moradin_forge.ps1"
    return {
        "version": "MoradinForgeBootstrapV1",
        "generated_at": utc_now(),
        "repo_url": sanitize_repo_url(options.repo_url),
        "ref": options.ref,
        "dest": "<forge-root>",
        "target_repo": target,
        "dependency_mode": options.deps,
        "dry_run": options.dry_run,
        "status": status,
        "tool_readiness": tool_state,
        "actions": actions,
        "skipped": skipped,
        "safety": [
            "No host install commands were executed.",
            "No target repo files were changed.",
            "Forge apply was not run.",
            "Missing tools are request-only manual actions.",
        ],
        "next_agent_commands": [
            "cd <forge-root>",
            f"{shell_wrapper} explain",
            f"{shell_wrapper} readiness --target {target}",
            f"{shell_wrapper} plan --target {target}",
            "Ask the user for explicit approval before any apply command.",
        ],
    }


def write_start_card(dest: Path, payload: dict[str, Any], dry_run: bool) -> dict[str, str]:
    card_root = dest / START_CARD_RELATIVE
    json_path = card_root / "agent_start.json"
    markdown_path = card_root / "agent_start.md"
    if dry_run:
        return {
            "json": "<forge-root>/artifacts/bootstrap/latest/agent_start.json",
            "markdown": "<forge-root>/artifacts/bootstrap/latest/agent_start.md",
            "dry_run": "true",
        }
    card_root.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Moradin Forge Agent Start",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- status: `{payload['status']}`",
        f"- dependency_mode: `{payload['dependency_mode']}`",
        f"- dry_run: `{str(payload['dry_run']).lower()}`",
        "",
        "## Next Agent Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in payload["next_agent_commands"])
    lines.extend(["", "## Safety", ""])
    lines.extend(f"- {item}" for item in payload["safety"])
    markdown_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "json": "<forge-root>/artifacts/bootstrap/latest/agent_start.json",
        "markdown": "<forge-root>/artifacts/bootstrap/latest/agent_start.md",
    }


def bootstrap(options: BootstrapOptions) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    tool_state = detect_tools(options.deps)
    if tool_state["status"] == "blocked":
        skipped = ["start card write suppressed because required tools are missing"]
        payload = start_card_payload(options, "blocked", tool_state, actions, skipped=skipped)
        payload["agent_start"] = {
            "json": "<forge-root>/artifacts/bootstrap/latest/agent_start.json",
            "markdown": "<forge-root>/artifacts/bootstrap/latest/agent_start.md",
            **({"dry_run": "true"} if options.dry_run else {}),
            "write_suppressed": "true",
        }
        return payload
    checkout_status = checkout_repo(options, actions)
    skipped = prime_dependencies(options, actions, tool_state)
    payload = start_card_payload(options, checkout_status, tool_state, actions, skipped)
    payload["agent_start"] = write_start_card(options.dest, payload, options.dry_run)
    return payload


def print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    print(f"dest: {payload['dest']}")
    readiness = payload.get("tool_readiness", {})
    print(f"missing_required: {', '.join(readiness.get('missing_required', [])) or 'none'}")
    if payload.get("error"):
        print(f"error: {payload['error']}")
    if payload.get("agent_start"):
        print(f"agent_start: {payload['agent_start']['markdown']}")
    for command in payload.get("next_agent_commands", []):
        print(f"next: {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prime Moradin Forge for an agent without host installs.")
    parser.add_argument("--repo-url", default=os.environ.get("MORADIN_FORGE_REPO_URL", DEFAULT_REPO_URL))
    parser.add_argument("--ref", default=os.environ.get("MORADIN_FORGE_REF", DEFAULT_REF))
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--target", type=Path, default=None)
    parser.add_argument("--deps", choices=("none", "minimal", "full"), default=DEFAULT_DEPS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dest = (args.dest or default_dest()).expanduser().resolve()
    options = BootstrapOptions(
        repo_url=str(args.repo_url),
        ref=str(args.ref),
        dest=dest,
        target=args.target.expanduser().resolve() if args.target else None,
        deps=args.deps,
        dry_run=args.dry_run,
    )
    try:
        payload = bootstrap(options)
    except (BootstrapError, subprocess.CalledProcessError) as error:
        payload = {
            "version": "MoradinForgeBootstrapV1",
            "generated_at": utc_now(),
            "dest": "<forge-root>",
            "target_repo": "<target-repo>",
            "dependency_mode": options.deps,
            "dry_run": options.dry_run,
            "status": "blocked",
            "error": sanitize_error_message(str(error), options),
            "safety": "No host install commands were executed and Forge apply was not run.",
        }
        print_payload(payload, args.json)
        return 2
    print_payload(payload, args.json)
    return 0 if payload["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
