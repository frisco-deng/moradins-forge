#!/usr/bin/env python3
"""Agent-first Moradin Forge integration helpers."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_MANIFEST_RELATIVE = Path("Harness/moradin_payload/manifest.yaml")
CONTROL_ROOT_RELATIVE = Path("Harness/artifacts/control")
DEFAULT_SIDECAR_DIR = ".moradins-harness"
AGENTS_MARKER_BEGIN = "<!-- moradin-forge:start -->"
AGENTS_MARKER_END = "<!-- moradin-forge:end -->"
INTERNAL_USER_TOKEN = "ru" + "ne"
HOME_PREFIX_TOKEN = "/" + "home" + "/"
MAC_HOME_PREFIX_TOKEN = "/" + "Users" + "/"
WORKSPACE_ROOT_TOKEN = "WORKSPACE" + "_ROOT"
SHARED_TEMPLATES_TOKEN = "." + "templates"
LEGACY_DRY_RUN_TOKEN = "_harness" + "_dry_runs"
TEMPLATE_REPO_ALIAS_TOKEN = "tpl repo " + "moradins-" + "harness"
BRANCH_WAIVER_TOKEN = "branch_hygiene" + "_waiver"
PR_HARDENING_TOKEN = "pr" + "_hardening"
MIGRATION_REPORTS_TOKEN = "migration" + "_reports"
RELEASE_REPORTS_TOKEN = "Harness/artifacts/reports" + "/release"
RELEASE_EVIDENCE_TOKEN = RELEASE_REPORTS_TOKEN + "/evidence"
PRIVATE_FORGE_ROOT_TOKEN = (
    HOME_PREFIX_TOKEN + INTERNAL_USER_TOKEN + "/code/projects/moradins-" + "harness"
)
PRIVATE_CODE_ROOT_TOKEN = HOME_PREFIX_TOKEN + INTERNAL_USER_TOKEN + "/code"
PRIVATE_HOME_ROOT_TOKEN = HOME_PREFIX_TOKEN + INTERNAL_USER_TOKEN

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vite",
    "__pycache__",
    "dist",
    "node_modules",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {
    ".gitignore",
    "Dockerfile",
    "Makefile",
    "AGENTS.md",
    "FORGE.md",
    "README.md",
}
LEGACY_DISCOVERY_DOC_RE = re.compile(
    r"^docs/(?:design_docs|product_specs)/discovery_disc_[^/]+\.md$"
)
FORGE_FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "internal_home_path",
        re.compile(re.escape(HOME_PREFIX_TOKEN) + r"[A-Za-z0-9_.-]+(?:/|$)"),
    ),
    (
        "mac_home_path",
        re.compile(re.escape(MAC_HOME_PREFIX_TOKEN) + r"[A-Za-z0-9_.-]+(?:/|$)"),
    ),
    (
        "windows_user_path",
        re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s`\"'<>)]*(?:[\\/][^\\/\s`\"'<>)]*)?"),
    ),
    (
        "wsl_unc_path",
        re.compile(r"\\\\wsl(?:\.localhost)?\\[^\s`\"'<>)]*"),
    ),
    (
        "codex_home_or_session_path",
        re.compile(r"(?:^|[\\/])\.codex(?:[\\/][^\s`\"'<>)]*)?|codex[\\/]sessions[\\/][^\s`\"'<>)]*", re.IGNORECASE),
    ),
    (
        "ssh_clone_url",
        re.compile(r"\b(?:git@[A-Za-z0-9_.-]+:[^\s`\"'<>)]*|ssh://git@[A-Za-z0-9_.-]+/[^\s`\"'<>)]*)"),
    ),
    ("internal_user", re.compile(rf"\b{re.escape(INTERNAL_USER_TOKEN)}\b", re.IGNORECASE)),
    (
        "internal_workspace_root",
        re.compile(rf"\b{WORKSPACE_ROOT_TOKEN}\b|\$\{{{WORKSPACE_ROOT_TOKEN}\}}"),
    ),
    ("shared_templates_ref", re.compile(re.escape(SHARED_TEMPLATES_TOKEN))),
    ("legacy_dry_run_root", re.compile(re.escape(LEGACY_DRY_RUN_TOKEN))),
    ("manager_release_reports", re.compile(re.escape(RELEASE_REPORTS_TOKEN))),
    (
        "migration_report_artifact",
        re.compile(rf"\b{re.escape(MIGRATION_REPORTS_TOKEN)}\b"),
    ),
    ("branch_waiver_token", re.compile(re.escape(BRANCH_WAIVER_TOKEN))),
    ("review_hardening_token", re.compile(re.escape(PR_HARDENING_TOKEN))),
    (
        "branch_waiver",
        re.compile(re.escape(f"Harness/artifacts/control/{BRANCH_WAIVER_TOKEN}")),
    ),
    (
        "review_hardening_artifact",
        re.compile(re.escape(f"Harness/artifacts/control/{PR_HARDENING_TOKEN}")),
    ),
    ("template_repo_alias", re.compile(re.escape(TEMPLATE_REPO_ALIAS_TOKEN))),
]
SIDECAR_ALWAYS_EXCLUDE_PREFIXES = {
    ".harness_devops",
    ".harness_template",
    "_archive",
    "artifacts",
    "build",
    "dev_tracker/ui/.review_evidence",
    "dev_tracker/ui/dist",
    "dev_tracker/ui/node_modules",
    "dev_tracker/ui/public/generated",
    "dev_tracker/ui/tests/__screenshots__",
    "docs/archive",
    "docs/exec_plans",
    "docs/exec_plans/implementation/completed",
    "docs/exec_plans/updates",
    "Harness/artifacts/openapi",
    "Harness/artifacts/reports",
    "Harness/generated",
    MIGRATION_REPORTS_TOKEN,
    "tooling/.cache",
}
SIDECAR_ALWAYS_EXCLUDE_EXACT = {
    f"Harness/artifacts/control/{BRANCH_WAIVER_TOKEN}.json",
    f"Harness/artifacts/control/{BRANCH_WAIVER_TOKEN}.md",
    "Harness/artifacts/control/archive_register.md",
    "Harness/artifacts/control/builder_operation_audit.md",
    "Harness/artifacts/control/capability_gap_register.md",
    "Harness/artifacts/control/documentation_review_status.md",
    "Harness/artifacts/control/human_gate_stats.md",
    "Harness/artifacts/control/loop_processes.md",
    "Harness/artifacts/control/loop_state.md",
    "Harness/artifacts/control/release_exit_tracker.md",
}
SIDECAR_ALWAYS_EXCLUDE_PREFIXES.update(
    {
        "Harness/artifacts/control/forge_runs",
        "Harness/artifacts/control/install_requests",
        "Harness/artifacts/control/migration_start",
        "Harness/artifacts/control/migration_waves",
        f"Harness/artifacts/control/{PR_HARDENING_TOKEN}",
        "Harness/artifacts/control/public_export",
        "Harness/artifacts/control/repo_registry",
        "Harness/artifacts/control/discovery_sessions",
    }
)
PORTABLE_TEXT_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(re.escape(PRIVATE_FORGE_ROOT_TOKEN)), "<forge-root>"),
    (re.compile(re.escape(PRIVATE_CODE_ROOT_TOKEN)), "<workspace-root>"),
    (re.compile(re.escape(PRIVATE_HOME_ROOT_TOKEN)), "<home>"),
    (
        re.compile(re.escape(HOME_PREFIX_TOKEN) + r"[A-Za-z0-9_.-]+(?:/[^\s`\"'<>)]*)?"),
        "<local-path>",
    ),
    (
        re.compile(re.escape(MAC_HOME_PREFIX_TOKEN) + r"[A-Za-z0-9_.-]+(?:/[^\s`\"'<>)]*)?"),
        "<local-path>",
    ),
    (
        re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s`\"'<>)]*(?:[\\/][^\s`\"'<>)]*)*"),
        "<local-path>",
    ),
    (re.compile(r"\\\\wsl(?:\.localhost)?\\[^\s`\"'<>)]*"), r"\\wsl$\\<distro>\\..."),
    (
        re.compile(r"(?:^|[\\/])\.codex(?:[\\/][^\s`\"'<>)]*)?|codex[\\/]sessions[\\/][^\s`\"'<>)]*", re.IGNORECASE),
        "<codex-session>",
    ),
    (
        re.compile(r"\b(?:git@[A-Za-z0-9_.-]+:[^\s`\"'<>)]*|ssh://git@[A-Za-z0-9_.-]+/[^\s`\"'<>)]*)"),
        "https://github.com/frisco-deng/moradins-forge.git",
    ),
    (
        re.compile(re.escape(HOME_PREFIX_TOKEN) + r"[A-Za-z0-9_.-]+(?:/[^\s`\"'<>)]*)?"),
        "<local-path>",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9_])/(?:tmp|var/tmp)/[^\s`\"'<>)]*"),
        "<temp-dir>",
    ),
    (re.compile(re.escape("${" + WORKSPACE_ROOT_TOKEN + "}")), "<workspace-root>"),
    (re.compile(rf"\b{WORKSPACE_ROOT_TOKEN}\b"), "WORKSPACE_PLACEHOLDER_ROOT"),
    (
        re.compile(re.escape("../" + LEGACY_DRY_RUN_TOKEN)),
        "<temp-dir>/moradin_tmp_runs",
    ),
    (re.compile(re.escape(LEGACY_DRY_RUN_TOKEN)), "moradin_tmp_runs"),
    (re.compile(re.escape(TEMPLATE_REPO_ALIAS_TOKEN)), "cd <forge-root>"),
    (re.compile(re.escape(SHARED_TEMPLATES_TOKEN)), "shared-tooling-source"),
    (
        re.compile(re.escape(RELEASE_EVIDENCE_TOKEN)),
        "public_audit/release_evidence_excluded",
    ),
    (
        re.compile(re.escape(RELEASE_REPORTS_TOKEN)),
        "public_audit/release_reports_excluded",
    ),
    (
        re.compile(re.escape(f"Harness/artifacts/control/{BRANCH_WAIVER_TOKEN}")),
        "Harness/artifacts/control/branch_hygiene_exception",
    ),
    (
        re.compile(re.escape(f"Harness/artifacts/control/{PR_HARDENING_TOKEN}")),
        "Harness/artifacts/control/review_hardening",
    ),
    (re.compile(re.escape(BRANCH_WAIVER_TOKEN)), "branch_hygiene_exception"),
    (re.compile(re.escape(PR_HARDENING_TOKEN)), "review_hardening"),
    (re.compile(rf"\b{re.escape(MIGRATION_REPORTS_TOKEN)}\b"), "public_audit"),
    (re.compile(rf"\b{re.escape(INTERNAL_USER_TOKEN)}\b", re.IGNORECASE), "operator"),
]

PORTABLE_SIDECAR_MAKEFILE_TEXT = """\
.PHONY: test payload-validate payload-smoke forge-explain forge-readiness forge-plan forge-adopt forge-verify forge-smoke

TARGET ?=
APPROVE ?=
OVERWRITE ?=
PATCH_AGENTS ?=

test:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run pytest

payload-validate:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py validate

payload-smoke:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py smoke-test

forge-explain:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py explain

forge-readiness:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py readiness

forge-plan:
\t@if [ -z "$(TARGET)" ]; then echo "Usage: make forge-plan TARGET=<repo-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py plan --target "$(TARGET)" --write-install-request

forge-adopt:
\t@if [ -z "$(TARGET)" ] || [ "$(APPROVE)" != "1" ]; then echo "Usage: make forge-adopt TARGET=<repo-path> APPROVE=1"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py apply --target "$(TARGET)" --approve $(if $(OVERWRITE),--overwrite-sidecar,) $(if $(PATCH_AGENTS),--patch-agents,) --write-install-request

forge-verify:
\t@if [ -z "$(TARGET)" ]; then echo "Usage: make forge-verify TARGET=<repo-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py verify --target "$(TARGET)"

forge-smoke:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py sidecar-smoke --output /tmp/moradin-forge-sidecar-smoke-check --force
"""

PAYLOAD_FILE_OVERRIDES: dict[str, str] = {
    "Makefile": PORTABLE_SIDECAR_MAKEFILE_TEXT,
    "Harness/artifacts/control/current_guidance.md": """\
---
title: "Moradin Forge Public Guidance"
status: public-contract
owner: moradin-forge
---

# Moradin Forge Public Guidance

| guidance_id | rule | enforcement_anchor | operator_action | status |
| --- | --- | --- | --- | --- |
| FORGE-001 | inspect Forge and the target repo before proposing changes | FORGE.md | explain the plan before apply | active |
| FORGE-002 | require explicit user approval before writing target repo files | Harness/entrypoints/forge.md | run apply only with `--approve` | active |
| FORGE-003 | keep host tool installation request-only | docs/references/tooling_readiness_install_request_contract_v1.md | write install-request artifacts instead of installing tools | active |
| FORGE-004 | preserve root workflows by default | docs/references/moradin_forge_agent_integration_contract_v1.md | write sidecar adapters before root patches | active |
| FORGE-005 | verify sidecars for portability before handoff | scripts/moradin_forge.py | run `forge verify` or `make forge-verify` | active |
| FORGE-006 | keep bootstrap separate from adoption | docs/references/moradin_forge_installer_bootstrap_contract_v1.md | run platform bootstrap only to prime Forge and write a start card | active |
| FORGE-007 | keep beta release visuals portable and local | README.md | scan SVG assets before public release | active |
""",
    "Harness/artifacts/control/current_features.md": """\
---
title: "Moradin Forge Public Features"
status: public-contract
owner: moradin-forge
---

# Moradin Forge Public Features

| feature_id | capability | status | evidence |
| --- | --- | --- | --- |
| FORGE-FEAT-001 | consent-gated local sidecar adoption | implemented | scripts/moradin_forge.py |
| FORGE-FEAT-002 | payload-manifest-driven copy contract | implemented | Harness/moradin_payload/manifest.yaml |
| FORGE-FEAT-003 | adaptive adapter snippets for common repo tooling | implemented | .moradins-harness/adapters/ |
| FORGE-FEAT-004 | request-only tooling readiness artifacts | implemented | docs/references/tooling_readiness_install_request_contract_v1.md |
| FORGE-FEAT-005 | public export and sidecar portability scans | implemented | scripts/public_export.py |
| FORGE-FEAT-006 | low-token clone-and-prime bootstrap entrypoints | implemented | docs/references/moradin_forge_installer_bootstrap_contract_v1.md |
| FORGE-FEAT-007 | README visual overview for adoption and safety boundaries | implemented | docs/assets/readme/ |
""",
    "Harness/artifacts/control/compatibility_window_status.md": """\
---
title: "Moradin Forge Compatibility Window"
status: public-contract
owner: moradin-forge
---

# Moradin Forge Compatibility Window

- `canonical_payload`: `Harness/moradin_payload/manifest.yaml`
- `sidecar_default_dir`: `.moradins-harness`
- `legacy_aliases_enabled`: true
- `compatibility_scope`: legacy aliases are sanitizer-only compatibility
  history; first-read docs use Moradin payload names.
- `removal_gate`: one public compatibility window after downstream users have
  moved to Moradin payload commands.
""",
    "Harness/artifacts/control/changelog.md": """\
---
title: "Moradin Forge Public Changelog"
status: public-contract
owner: moradin-forge
---

# Moradin Forge Public Changelog

| entry_id | date | change_type | summary | status |
| --- | --- | --- | --- | --- |
| PUBLIC-001 | 2026-05-11 | public-alpha | Published Moradin's Forge as an agent-first local integration kit with consent-gated sidecar adoption. | ready |
| PUBLIC-002 | 2026-06-09 | tooling-inheritance | Adopted current shared-tooling adapter improvements, hardened portability scans, and added request-only bootstrap entrypoints. | ready |
| PUBLIC-003 | 2026-06-10 | beta-release | Prepared v0.2.0-beta.1 with version normalization, CI fixes, and README visual overview assets. | ready |
""",
}


class ForgeError(RuntimeError):
    """Raised when a Forge operation cannot proceed safely."""


@dataclass(frozen=True)
class ForgeApplyOptions:
    approve: bool = False
    overwrite_sidecar: bool = False
    patch_agents: bool = False
    create_agents: bool = False
    write_install_request: bool = False
    sidecar_dir: str = DEFAULT_SIDECAR_DIR


@dataclass(frozen=True)
class ForgeVerifyIssue:
    code: str
    path: str
    message: str


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def utc_run_id(prefix: str = "forge") -> str:
    return f"{prefix}_{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S%fZ')}"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- ") and current_list_key:
            data.setdefault(current_list_key, [])
            if isinstance(data[current_list_key], list):
                data[current_list_key].append(line[2:].strip().strip("'\""))
            continue
        current_list_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = []
            current_list_key = key
        elif value.isdigit():
            data[key] = int(value)
        else:
            data[key] = value.strip("'\"")
    return data


def normalize_payload_relative_path(value: object) -> str:
    raw = str(value).strip().replace("\\", "/")
    if not raw or raw.startswith("/") or raw.startswith("../") or "/../" in raw:
        return ""
    normalized = os.path.normpath(raw).replace("\\", "/").lstrip("./")
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        return ""
    return normalized


def load_payload_manifest(forge_root: Path = REPO_ROOT) -> dict[str, Any]:
    manifest_path = forge_root / PAYLOAD_MANIFEST_RELATIVE
    if not manifest_path.is_file():
        raise ForgeError(f"missing Moradin payload manifest: {manifest_path}")
    raw = parse_simple_yaml(manifest_path)
    include_paths = [
        path
        for path in (normalize_payload_relative_path(item) for item in raw.get("include_paths", []))
        if path
    ]
    exclude_paths = [
        path
        for path in (normalize_payload_relative_path(item) for item in raw.get("exclude_paths", []))
        if path
    ]
    missing = []
    if raw.get("manifest_version") != 1:
        missing.append("manifest_version=1")
    if raw.get("kind") != "moradin_payload":
        missing.append("kind=moradin_payload")
    if raw.get("payload_id") != "moradin_harness_payload":
        missing.append("payload_id=moradin_harness_payload")
    if not include_paths:
        missing.append("include_paths")
    if missing:
        raise ForgeError(f"invalid Moradin payload manifest: {', '.join(missing)}")
    return {
        **raw,
        "include_paths": include_paths,
        "exclude_paths": exclude_paths,
        "sidecar_default_dir": str(raw.get("sidecar_default_dir") or DEFAULT_SIDECAR_DIR),
    }


def normalize_sidecar_dir(value: str) -> str:
    sidecar_dir = str(value or DEFAULT_SIDECAR_DIR).strip()
    if (
        not sidecar_dir
        or sidecar_dir in {".", ".."}
        or "/" in sidecar_dir
        or "\\" in sidecar_dir
    ):
        raise ForgeError("sidecar_dir must be one directory name without traversal")
    return sidecar_dir


def is_payload_path_excluded(relative_path: str, manifest: dict[str, Any]) -> bool:
    normalized = normalize_payload_relative_path(relative_path)
    if LEGACY_DISCOVERY_DOC_RE.match(normalized):
        return True
    if normalized in SIDECAR_ALWAYS_EXCLUDE_EXACT:
        return True
    for exclude_path in SIDECAR_ALWAYS_EXCLUDE_PREFIXES:
        if normalized == exclude_path or normalized.startswith(f"{exclude_path}/"):
            return True
    for exclude_path in manifest["exclude_paths"]:
        if normalized == exclude_path or normalized.startswith(f"{exclude_path}/"):
            return True
    return False


def is_text_payload_file(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in TEXT_FILENAMES


def is_binary_payload_file(path: Path) -> bool:
    if not is_text_payload_file(path):
        return True
    try:
        return b"\x00" in path.read_bytes()[:2048]
    except OSError:
        return True


def sanitize_portable_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in PORTABLE_TEXT_REPLACEMENTS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_portable_payload(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_portable_text(value)
    if isinstance(value, list):
        return [sanitize_portable_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            str(sanitize_portable_text(str(key))): sanitize_portable_payload(item)
            for key, item in value.items()
        }
    return value


def origin_marker_patterns() -> list[tuple[str, re.Pattern[str]]]:
    markers: set[str] = set()
    for key in ("USER", "USERNAME", "LOGNAME"):
        marker = os.environ.get(key, "").strip()
        if marker:
            markers.add(marker)
    host = platform.node().strip()
    if host:
        markers.add(host)
        markers.add(host.split(".", 1)[0])
    ignored = {"", "root", "user", "runner", "localhost", "host", "admin", "administrator"}
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for marker in sorted(markers):
        if len(marker) < 4 or marker.lower() in ignored:
            continue
        patterns.append(
            (
                "local_origin_marker",
                re.compile(rf"(?<![A-Za-z0-9_]){re.escape(marker)}(?![A-Za-z0-9_])", re.IGNORECASE),
            )
        )
    return patterns


def forbidden_patterns() -> list[tuple[str, re.Pattern[str]]]:
    return [*FORGE_FORBIDDEN_PATTERNS, *origin_marker_patterns()]


def copy_payload_file(relative_path: str, source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    override = PAYLOAD_FILE_OVERRIDES.get(relative_path)
    if override is not None:
        destination.write_text(override, encoding="utf-8")
        return
    if is_binary_payload_file(source):
        shutil.copy2(source, destination)
        return
    destination.write_text(
        sanitize_portable_text(source.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    shutil.copystat(source, destination)


def copy_payload_path(
    source: Path,
    destination: Path,
    relative_path: str,
    manifest: dict[str, Any],
    copied_files: list[str],
) -> None:
    if is_payload_path_excluded(relative_path, manifest):
        return
    stat = source.lstat()
    if stat and source.is_symlink():
        raise ForgeError(f"payload source symlink is not allowed: {relative_path}")
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            if child.name in SKIP_DIR_NAMES or child.name.endswith(".tsbuildinfo"):
                continue
            child_relative = normalize_payload_relative_path(f"{relative_path}/{child.name}")
            copy_payload_path(child, destination / child.name, child_relative, manifest, copied_files)
        return
    if not source.is_file():
        return
    copy_payload_file(relative_path, source, destination)
    copied_files.append(relative_path)


def copy_payload_to_sidecar(forge_root: Path, sidecar_root: Path) -> list[str]:
    manifest = load_payload_manifest(forge_root)
    copied_files: list[str] = []
    for relative_path in manifest["include_paths"]:
        if is_payload_path_excluded(relative_path, manifest):
            continue
        source = forge_root / relative_path
        if not source.exists():
            raise ForgeError(f"payload include path is missing: {relative_path}")
        copy_payload_path(source, sidecar_root / relative_path, relative_path, manifest, copied_files)
    return copied_files


def relative_to_root(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_sidecar_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames[:] = [
            dirname
            for dirname in sorted(dirnames)
            if dirname not in SKIP_DIR_NAMES and dirname != "public_audit"
        ]
        for filename in sorted(filenames):
            path = current_path / filename
            if not is_text_payload_file(path):
                continue
            if is_binary_payload_file(path):
                continue
            files.append(path)
    return files


def scan_forbidden_sidecar_references(sidecar_root: Path) -> list[ForgeVerifyIssue]:
    issues: list[ForgeVerifyIssue] = []
    for path in iter_sidecar_text_files(sidecar_root):
        relative = relative_to_root(path, sidecar_root)
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for code, pattern in forbidden_patterns():
                if pattern.search(line):
                    issues.append(
                        ForgeVerifyIssue(
                            code=code,
                            path=f"{relative}:{line_number}",
                            message=line.strip()[:180],
                        )
                    )
    return issues


def scan_local_only_artifact_paths(sidecar_root: Path) -> list[ForgeVerifyIssue]:
    issues: list[ForgeVerifyIssue] = []
    for current_root, dirnames, filenames in os.walk(sidecar_root):
        current_path = Path(current_root)
        dirnames[:] = [dirname for dirname in sorted(dirnames) if dirname not in SKIP_DIR_NAMES]
        for filename in sorted(filenames):
            path = current_path / filename
            relative = relative_to_root(path, sidecar_root)
            if relative in SIDECAR_ALWAYS_EXCLUDE_EXACT:
                issues.append(
                    ForgeVerifyIssue(
                        code="local_only_artifact_copied",
                        path=relative,
                        message="local-only exact path is present in sidecar",
                    )
                )
            for prefix in SIDECAR_ALWAYS_EXCLUDE_PREFIXES:
                if relative == prefix or relative.startswith(f"{prefix}/"):
                    issues.append(
                        ForgeVerifyIssue(
                            code="local_only_artifact_copied",
                            path=relative,
                            message=f"local-only prefix is present: {prefix}",
                        )
                    )
                    break
    return issues


def detect_tool(command: str) -> bool:
    return shutil.which(command) is not None


def detect_any_tool(commands: list[str]) -> bool:
    return any(detect_tool(command) for command in commands)


def detect_readiness() -> dict[str, Any]:
    tool_specs = [
        {
            "id": "git",
            "label": "Git",
            "command": "git",
            "required": True,
            "human_run_commands": [
                "sudo apt-get update && sudo apt-get install -y git",
                "brew install git",
                "winget install --id Git.Git -e",
            ],
        },
        {
            "id": "python",
            "label": "Python",
            "command": "python3",
            "commands": ["python3", "python", "py"],
            "required": True,
            "human_run_commands": [
                "sudo apt-get update && sudo apt-get install -y python3",
                "brew install python",
                "winget install --id Python.Python.3.12 -e",
            ],
        },
        {
            "id": "uv",
            "label": "uv",
            "command": "uv",
            "required": False,
            "human_run_commands": [
                "curl -LsSf https://astral.sh/uv/install.sh | sh",
                "powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"",
            ],
        },
        {
            "id": "node",
            "label": "Node.js",
            "command": "node",
            "required": False,
            "human_run_commands": [],
        },
        {
            "id": "npm",
            "label": "npm",
            "command": "npm",
            "required": False,
            "human_run_commands": [],
        },
        {
            "id": "codex_cli",
            "label": "Codex CLI",
            "command": "codex",
            "required": False,
            "human_run_commands": [],
        },
        {
            "id": "claude_code",
            "label": "Claude Code",
            "command": "claude",
            "required": False,
            "human_run_commands": [],
        },
        {
            "id": "tpldeck",
            "label": "tpldeck shell helper",
            "command": "tpldeck",
            "required": False,
            "human_run_commands": [],
        },
        {
            "id": "uvbootstrap",
            "label": "uvbootstrap shell helper",
            "command": "uvbootstrap",
            "required": False,
            "human_run_commands": [],
        },
        {
            "id": "codex_run",
            "label": "codex-run bridge helper",
            "command": "codex-run",
            "required": False,
            "human_run_commands": [],
        },
    ]
    checks = []
    for spec in tool_specs:
        commands = [str(item) for item in spec.get("commands", [spec["command"]])]
        present = detect_any_tool(commands)
        checks.append(
            {
                **spec,
                "status": "present" if present else "missing",
                "present": present,
                "verification_command": f"{spec['command']} --version",
            }
        )
    checks.append(
        {
            "id": "codex_app_manual_handoff",
            "label": "Codex App manual handoff",
            "command": "",
            "required": False,
            "human_run_commands": [],
            "status": "manual",
            "present": True,
            "verification_command": "Manual paste flow; no host command required.",
        }
    )
    missing_required = [check for check in checks if check["required"] and not check["present"]]
    missing_optional = [
        check
        for check in checks
        if not check["required"] and check["status"] == "missing"
    ]
    return {
        "version": "MoradinForgeReadinessV1",
        "generated_at": utc_now(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "checks": checks,
        "missing_required": [check["id"] for check in missing_required],
        "missing_optional": [check["id"] for check in missing_optional],
        "status": "blocked" if missing_required else "ready",
        "safety": "request_only; no host install commands were executed",
    }


def list_matching_files(root: Path, relative_dir: str, suffixes: tuple[str, ...]) -> list[str]:
    directory = root / relative_dir
    if not directory.is_dir():
        return []
    return sorted(
        (directory / item.name).relative_to(root).as_posix()
        for item in directory.iterdir()
        if item.is_file() and item.name.endswith(suffixes)
    )


def detect_target_tooling(target_root: Path) -> dict[str, Any]:
    compose_names = [
        "compose.yaml",
        "compose.yml",
        "docker-compose.yaml",
        "docker-compose.yml",
    ]
    ci_files = list_matching_files(target_root, ".github/workflows", (".yml", ".yaml"))
    package_scripts: list[str] = []
    package_json = target_root / "package.json"
    if package_json.is_file():
        try:
            package_payload = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = package_payload.get("scripts", {})
            if isinstance(scripts, dict):
                package_scripts = sorted(str(key) for key in scripts)
        except json.JSONDecodeError:
            package_scripts = []
    return {
        "makefile_present": (target_root / "Makefile").is_file(),
        "package_json_present": package_json.is_file(),
        "package_scripts": package_scripts,
        "pyproject_toml_present": (target_root / "pyproject.toml").is_file(),
        "cargo_toml_present": (target_root / "Cargo.toml").is_file(),
        "go_mod_present": (target_root / "go.mod").is_file(),
        "dockerfile_present": (target_root / "Dockerfile").is_file(),
        "compose_files": [name for name in compose_names if (target_root / name).is_file()],
        "ci_files": ci_files,
    }


def target_repo_snapshot(target_root: Path, sidecar_dir: str = DEFAULT_SIDECAR_DIR) -> dict[str, Any]:
    return {
        "path": target_root.as_posix(),
        "exists": target_root.exists(),
        "is_dir": target_root.is_dir(),
        "git_present": (target_root / ".git").exists(),
        "agents_present": (target_root / "AGENTS.md").is_file(),
        "makefile_present": (target_root / "Makefile").is_file(),
        "tooling": detect_target_tooling(target_root),
        "sidecar_dir": sidecar_dir,
        "sidecar_present": (target_root / sidecar_dir).exists(),
    }


def proposed_writes_for_target(target_root: Path, sidecar_dir: str) -> list[str]:
    tooling = detect_target_tooling(target_root)
    writes = [
        f"{sidecar_dir}/**",
        f"{sidecar_dir}/adapters/AGENTS.snippet.md",
        f"{sidecar_dir}/adapters/Makefile.snippet",
        f"{sidecar_dir}/adapters/README.md",
        f"{sidecar_dir}/Harness/artifacts/control/forge_integration/integration.json",
        f"{sidecar_dir}/Harness/artifacts/control/forge_integration/integration.md",
    ]
    if tooling["package_json_present"]:
        writes.append(f"{sidecar_dir}/adapters/package.json.scripts.snippet.json")
    if tooling["pyproject_toml_present"]:
        writes.append(f"{sidecar_dir}/adapters/python.commands.md")
    if tooling["cargo_toml_present"]:
        writes.append(f"{sidecar_dir}/adapters/rust.commands.md")
    if tooling["go_mod_present"]:
        writes.append(f"{sidecar_dir}/adapters/go.commands.md")
    if tooling["dockerfile_present"] or tooling["compose_files"]:
        writes.append(f"{sidecar_dir}/adapters/docker.commands.md")
    if tooling["ci_files"]:
        writes.append(f"{sidecar_dir}/adapters/ci.commands.md")
    return writes


def optional_writes_for_target(target_root: Path) -> list[str]:
    if (target_root / "AGENTS.md").is_file():
        return ["AGENTS.md when apply is run with --patch-agents"]
    return ["AGENTS.md when apply is run with --patch-agents --create-agents"]


def build_integration_plan(
    forge_root: Path,
    target_root: Path,
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
) -> dict[str, Any]:
    sidecar_dir = normalize_sidecar_dir(sidecar_dir)
    target_root = target_root.resolve()
    if not target_root.is_dir():
        raise ForgeError(f"target repo must be an existing directory: {target_root}")
    manifest = load_payload_manifest(forge_root)
    snapshot = target_repo_snapshot(target_root, sidecar_dir)
    readiness = detect_readiness()
    return {
        "version": "MoradinForgePlanV1",
        "generated_at": utc_now(),
        "forge_root": forge_root.resolve().as_posix(),
        "target_repo": snapshot,
        "payload": {
            "manifest": PAYLOAD_MANIFEST_RELATIVE.as_posix(),
            "payload_id": manifest.get("payload_id"),
            "payload_version": manifest.get("payload_version", ""),
            "include_count": len(manifest["include_paths"]),
            "exclude_count": len(manifest["exclude_paths"]),
            "sidecar_default_dir": manifest.get("sidecar_default_dir", DEFAULT_SIDECAR_DIR),
        },
        "readiness": readiness,
        "proposed_writes": proposed_writes_for_target(target_root, sidecar_dir),
        "optional_writes": optional_writes_for_target(target_root),
        "consent_required": True,
        "apply_command": (
            f"scripts/moradin_forge.sh apply --target {target_root.as_posix()} --approve"
        ),
        "safety": [
            "Plan mode does not write to the target repo.",
            "Apply requires --approve.",
            "Host tool installs are request-only artifacts.",
            "Existing sidecars require --overwrite-sidecar.",
        ],
        "status": "needs_overwrite" if snapshot["sidecar_present"] else readiness["status"],
    }


def markdown_plan(plan: dict[str, Any]) -> str:
    target = plan["target_repo"]
    lines = [
        "# Moradin Forge Integration Plan",
        "",
        f"- generated_at: `{plan['generated_at']}`",
        f"- target_repo: `{target['path']}`",
        f"- sidecar_dir: `{target['sidecar_dir']}`",
        f"- status: `{plan['status']}`",
        f"- consent_required: `{plan['consent_required']}`",
        f"- readiness: `{plan['readiness']['status']}`",
        "",
        "## Proposed Writes",
        "",
    ]
    lines.extend(f"- `{item}`" for item in plan["proposed_writes"])
    lines.extend(["", "## Optional Writes", ""])
    lines.extend(f"- `{item}`" for item in plan.get("optional_writes", []))
    lines.extend(["", "## Safety", ""])
    lines.extend(f"- {item}" for item in plan["safety"])
    return "\n".join(lines) + "\n"


def write_forge_run_artifacts(
    forge_root: Path,
    payload: dict[str, Any],
    markdown: str,
    run_id: str | None = None,
) -> dict[str, str]:
    run_id = run_id or utc_run_id()
    output_root = forge_root / CONTROL_ROOT_RELATIVE / "forge_runs" / run_id
    write_json(output_root / "plan.json", payload)
    (output_root / "plan.md").write_text(markdown, encoding="utf-8")
    return {
        "run_id": run_id,
        "json": (output_root / "plan.json").as_posix(),
        "markdown": (output_root / "plan.md").as_posix(),
    }


def write_install_request_artifacts(
    forge_root: Path,
    readiness: dict[str, Any],
    target_root: Path | None = None,
    request_id: str | None = None,
) -> dict[str, str]:
    request_id = request_id or utc_run_id("forge_install_request")
    output_root = forge_root / CONTROL_ROOT_RELATIVE / "install_requests" / request_id
    selected = [
        check
        for check in readiness["checks"]
        if check["status"] == "missing"
    ]
    payload = {
        "version": "MoradinForgeInstallRequestV1",
        "request_id": request_id,
        "generated_at": utc_now(),
        "target_repo": target_root.as_posix() if target_root else "",
        "status": "request_only",
        "selected_tool_ids": [check["id"] for check in selected],
        "checks": selected,
        "safety": "Moradin wrote this request only. It did not execute host install commands.",
    }
    write_json(output_root / "install_request.json", payload)
    lines = [
        "# Moradin Forge Install Request",
        "",
        f"- request_id: `{request_id}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- target_repo: `{payload['target_repo'] or 'not set'}`",
        "- safety: Moradin did not execute these commands.",
        "",
        "## Missing Tools",
        "",
    ]
    if not selected:
        lines.append("- none")
    for check in selected:
        lines.append(f"- `{check['id']}` ({check['label']}): {check['status']}")
        commands = check.get("human_run_commands", [])
        if commands:
            lines.extend(f"  - `{command}`" for command in commands)
    (output_root / "install_request.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "request_id": request_id,
        "json": (output_root / "install_request.json").as_posix(),
        "markdown": (output_root / "install_request.md").as_posix(),
    }


def agents_adapter_section(sidecar_dir: str) -> str:
    return "\n".join(
        [
            AGENTS_MARKER_BEGIN,
            "## Moradin's Forge",
            "",
            f"- Local sidecar: `{sidecar_dir}/`",
            f"- Agent entrypoint: `{sidecar_dir}/FORGE.md`",
            f"- Harness entrypoint: `{sidecar_dir}/Harness/entrypoints/forge.md`",
            "- Keep Moradin local unless the user explicitly requests external tooling.",
            "- Treat host tool installation as request-only: write install requests, do not run installs.",
            "- Preserve existing repo workflows and prefer repo-local deterministic commands.",
            AGENTS_MARKER_END,
            "",
        ]
    )


def write_adapter_snippets(sidecar_root: Path, sidecar_dir: str, target_root: Path) -> list[str]:
    tooling = detect_target_tooling(target_root)
    adapters_root = sidecar_root / "adapters"
    adapters_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    readme = adapters_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Moradin Forge Adapter Snippets",
                "",
                "These files are local snippets for the target repo. Moradin does not",
                "overwrite root Makefiles, package scripts, CI, or language configuration",
                "by default.",
                "",
                "## Detected Tooling",
                "",
                f"- Makefile: `{tooling['makefile_present']}`",
                f"- package.json: `{tooling['package_json_present']}`",
                f"- pyproject.toml: `{tooling['pyproject_toml_present']}`",
                f"- Cargo.toml: `{tooling['cargo_toml_present']}`",
                f"- go.mod: `{tooling['go_mod_present']}`",
                f"- Docker: `{tooling['dockerfile_present'] or bool(tooling['compose_files'])}`",
                f"- CI workflows: `{len(tooling['ci_files'])}`",
                "",
                "Apply any root-level adapter manually after reviewing it with the user.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    written.append(readme.as_posix())
    agents_snippet = adapters_root / "AGENTS.snippet.md"
    agents_snippet.write_text(agents_adapter_section(sidecar_dir), encoding="utf-8")
    written.append(agents_snippet.as_posix())
    makefile_snippet = adapters_root / "Makefile.snippet"
    makefile_snippet.write_text(
        "\n".join(
            [
                "# Optional Moradin Forge targets. Review before copying into a root Makefile.",
                "moradin-forge-plan:",
                f"\t{sidecar_dir}/scripts/moradin_forge.sh plan --target \"$$(pwd)\"",
                "",
                "moradin-forge-readiness:",
                f"\t{sidecar_dir}/scripts/moradin_forge.sh readiness --target \"$$(pwd)\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    written.append(makefile_snippet.as_posix())
    if tooling["package_json_present"]:
        package_snippet = adapters_root / "package.json.scripts.snippet.json"
        package_snippet.write_text(
            json.dumps(
                {
                    "scripts": {
                        "moradin:plan": f"{sidecar_dir}/scripts/moradin_forge.sh plan --target .",
                        "moradin:readiness": (
                            f"{sidecar_dir}/scripts/moradin_forge.sh readiness --target ."
                        ),
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(package_snippet.as_posix())
    if tooling["pyproject_toml_present"]:
        python_commands = adapters_root / "python.commands.md"
        python_commands.write_text(
            "\n".join(
                [
                    "# Python Commands",
                    "",
                    "- `python -m pytest`",
                    "- `python -m compileall .`",
                    "- `uv run pytest` when this repo already uses uv.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        written.append(python_commands.as_posix())
    if tooling["cargo_toml_present"]:
        rust_commands = adapters_root / "rust.commands.md"
        rust_commands.write_text("# Rust Commands\n\n- `cargo test`\n- `cargo fmt --check`\n\n", encoding="utf-8")
        written.append(rust_commands.as_posix())
    if tooling["go_mod_present"]:
        go_commands = adapters_root / "go.commands.md"
        go_commands.write_text("# Go Commands\n\n- `go test ./...`\n- `gofmt -w .`\n\n", encoding="utf-8")
        written.append(go_commands.as_posix())
    if tooling["dockerfile_present"] or tooling["compose_files"]:
        docker_commands = adapters_root / "docker.commands.md"
        docker_commands.write_text(
            "# Docker Commands\n\n- `docker build .`\n- `docker compose config` when compose files exist.\n\n",
            encoding="utf-8",
        )
        written.append(docker_commands.as_posix())
    if tooling["ci_files"]:
        ci_commands = adapters_root / "ci.commands.md"
        ci_commands.write_text(
            "\n".join(["# CI Workflows", "", *[f"- `{path}`" for path in tooling["ci_files"]], ""]),
            encoding="utf-8",
        )
        written.append(ci_commands.as_posix())
    return written


def patch_agents_adapter(target_root: Path, sidecar_dir: str, create_agents: bool) -> str:
    agents_path = target_root / "AGENTS.md"
    section = agents_adapter_section(sidecar_dir)
    if agents_path.is_file():
        existing = agents_path.read_text(encoding="utf-8")
        if AGENTS_MARKER_BEGIN in existing:
            return "already_present"
        agents_path.write_text(existing.rstrip() + "\n\n" + section, encoding="utf-8")
        return "patched"
    if create_agents:
        agents_path.write_text("# AGENTS.md\n\n" + section, encoding="utf-8")
        return "created"
    return "snippet_only"


def write_integration_record(
    sidecar_root: Path,
    plan: dict[str, Any],
    copied_files: list[str],
    adapter_status: str,
    install_request: dict[str, str] | None,
) -> dict[str, str]:
    output_root = sidecar_root / "Harness" / "artifacts" / "control" / "forge_integration"
    portable_plan = sanitize_portable_payload(plan)
    payload = {
        "version": "MoradinForgeIntegrationV1",
        "generated_at": utc_now(),
        "plan": portable_plan,
        "copied_file_count": len(copied_files),
        "copied_files": copied_files,
        "changed_paths": [
            f"{portable_plan['target_repo']['sidecar_dir']}/",
            *(
                ["AGENTS.md"]
                if adapter_status in {"patched", "created"}
                else []
            ),
        ],
        "adapter_status": adapter_status,
        "install_request": install_request or {},
        "validation_commands": [
            (
                f"{portable_plan['target_repo']['sidecar_dir']}/scripts/"
                "moradin_forge.sh verify --target ."
            ),
            "Run the target repo's existing deterministic test or verify command.",
        ],
        "rollback": [
            f"Remove `{portable_plan['target_repo']['sidecar_dir']}/` to remove the sidecar.",
            "Remove the Moradin's Forge marked block from root AGENTS.md if it was patched.",
            "No host install commands were executed by Moradin.",
        ],
    }
    portable_payload = sanitize_portable_payload(payload)
    write_json(output_root / "integration.json", portable_payload)
    lines = [
        "# Moradin Forge Integration",
        "",
        f"- generated_at: `{portable_payload['generated_at']}`",
        f"- target_repo: `{portable_plan['target_repo']['path']}`",
        f"- copied_file_count: `{len(copied_files)}`",
        f"- adapter_status: `{adapter_status}`",
        f"- install_request: `{(install_request or {}).get('markdown', 'none')}`",
        "",
        "## Changed Paths",
        "",
    ]
    lines.extend(f"- `{item}`" for item in portable_payload["changed_paths"])
    lines.extend(
        [
            "",
            "## Validation",
            "",
        ]
    )
    lines.extend(f"- `{item}`" for item in portable_payload["validation_commands"])
    lines.extend([
        "",
        "## Rollback",
        "",
    ])
    lines.extend(f"- {item}" for item in portable_payload["rollback"])
    (output_root / "integration.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": (output_root / "integration.json").as_posix(),
        "markdown": (output_root / "integration.md").as_posix(),
    }


def load_integration_record(sidecar_root: Path) -> dict[str, Any]:
    record_path = sidecar_root / "Harness/artifacts/control/forge_integration/integration.json"
    if not record_path.is_file():
        return {}
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def verify_integration(
    target_root: Path,
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
) -> dict[str, Any]:
    sidecar_dir = normalize_sidecar_dir(sidecar_dir)
    target_root = target_root.resolve()
    sidecar_root = target_root / sidecar_dir
    issues: list[ForgeVerifyIssue] = []
    required_paths = [
        "FORGE.md",
        "Harness/entrypoints/forge.md",
        "scripts/moradin_forge.py",
        "adapters/README.md",
        "adapters/AGENTS.snippet.md",
        "adapters/Makefile.snippet",
        "Harness/artifacts/control/forge_integration/integration.json",
        "Harness/artifacts/control/forge_integration/integration.md",
    ]
    if not target_root.is_dir():
        issues.append(
            ForgeVerifyIssue(
                code="target_missing",
                path=target_root.as_posix(),
                message="target repo directory does not exist",
            )
        )
    if not sidecar_root.is_dir():
        issues.append(
            ForgeVerifyIssue(
                code="sidecar_missing",
                path=sidecar_root.as_posix(),
                message="Moradin sidecar directory does not exist",
            )
        )
    else:
        for relative in required_paths:
            if not (sidecar_root / relative).is_file():
                issues.append(
                    ForgeVerifyIssue(
                        code="required_path_missing",
                        path=f"{sidecar_dir}/{relative}",
                        message="expected Forge sidecar file is missing",
                    )
                )
        issues.extend(scan_forbidden_sidecar_references(sidecar_root))
    issues.extend(scan_local_only_artifact_paths(sidecar_root))

    integration_record = load_integration_record(sidecar_root)
    adapter_status = str(integration_record.get("adapter_status", "unknown"))
    agents_text = ""
    agents_path = target_root / "AGENTS.md"
    if agents_path.is_file():
        agents_text = agents_path.read_text(encoding="utf-8", errors="replace")
    if adapter_status in {"patched", "created", "already_present"} and AGENTS_MARKER_BEGIN not in agents_text:
        issues.append(
            ForgeVerifyIssue(
                code="agents_marker_missing",
                path="AGENTS.md",
                message="integration record says AGENTS.md was patched, but marker is absent",
            )
        )
    if adapter_status in {"disabled", "snippet_only"} and AGENTS_MARKER_BEGIN in agents_text:
        issues.append(
            ForgeVerifyIssue(
                code="unexpected_agents_marker",
                path="AGENTS.md",
                message="AGENTS.md contains a Forge marker although default apply should preserve root files",
            )
        )

    return {
        "version": "MoradinForgeVerifyResultV1",
        "generated_at": utc_now(),
        "target_repo": target_root.as_posix(),
        "sidecar_path": sidecar_root.as_posix(),
        "sidecar_dir": sidecar_dir,
        "adapter_status": adapter_status,
        "issue_count": len(issues),
        "issues": [issue.__dict__ for issue in issues],
        "status": "pass" if not issues else "fail",
        "validation_commands": [
            f"{sidecar_dir}/scripts/moradin_forge.sh verify --target .",
            "Run the target repo's existing deterministic test or verify command.",
        ],
        "rollback": [
            f"Remove `{sidecar_dir}/` to remove the sidecar.",
            "Remove the Moradin's Forge marked block from root AGENTS.md if it was patched.",
            "No host install commands were executed by Moradin.",
        ],
    }


def apply_integration(
    forge_root: Path,
    target_root: Path,
    options: ForgeApplyOptions,
) -> dict[str, Any]:
    if not options.approve:
        raise ForgeError("apply requires --approve after the user has consented")
    sidecar_dir = normalize_sidecar_dir(options.sidecar_dir)
    target_root = target_root.resolve()
    if not target_root.is_dir():
        raise ForgeError(f"target repo must be an existing directory: {target_root}")
    sidecar_root = target_root / sidecar_dir
    if sidecar_root.exists():
        if not options.overwrite_sidecar:
            raise ForgeError(f"sidecar already exists: {sidecar_root}")
        shutil.rmtree(sidecar_root)
    plan = build_integration_plan(forge_root, target_root, sidecar_dir)
    sidecar_root.mkdir(parents=True, exist_ok=True)
    copied_files = copy_payload_to_sidecar(forge_root, sidecar_root)
    snippet_paths = write_adapter_snippets(sidecar_root, sidecar_dir, target_root)
    adapter_status = "disabled"
    if options.patch_agents:
        adapter_status = patch_agents_adapter(target_root, sidecar_dir, options.create_agents)
    install_request = None
    if options.write_install_request:
        install_request = write_install_request_artifacts(
            forge_root,
            plan["readiness"],
            target_root=target_root,
        )
    integration_record = write_integration_record(
        sidecar_root,
        plan,
        copied_files,
        adapter_status,
        install_request,
    )
    return {
        "version": "MoradinForgeApplyResultV1",
        "generated_at": utc_now(),
        "target_repo": target_root.as_posix(),
        "sidecar_path": sidecar_root.as_posix(),
        "copied_file_count": len(copied_files),
        "adapter_status": adapter_status,
        "adapter_snippets": snippet_paths,
        "install_request": install_request or {},
        "integration_record": integration_record,
    }


def forge_explainer() -> str:
    return """Moradin's Forge is an agent-first local integration kit.

When a user sends an agent here, the agent should inspect this repo and the
target repo, explain the proposed local sidecar and thin adapters, then ask for
explicit consent before changing the target. Forge keeps host tooling installs
request-only and preserves the user's existing repo workflows.

The deterministic path is:
1. `scripts/moradin_forge.sh explain`
2. `scripts/moradin_forge.sh plan --target <repo>`
3. review proposed writes and readiness gaps
4. `scripts/moradin_forge.sh apply --target <repo> --approve`
"""


def print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if payload.get("version") == "MoradinForgeReadinessV1":
        print(f"readiness: {payload['status']}")
        print(f"missing_required: {', '.join(payload['missing_required']) or 'none'}")
        print(f"missing_optional: {', '.join(payload['missing_optional']) or 'none'}")
        return
    if payload.get("version") == "MoradinForgeApplyResultV1":
        print(f"sidecar_path: {payload['sidecar_path']}")
        print(f"copied_file_count: {payload['copied_file_count']}")
        print(f"adapter_status: {payload['adapter_status']}")
        return
    if payload.get("version") == "MoradinForgeVerifyResultV1":
        print(f"verify: {payload['status']}")
        print(f"sidecar_path: {payload['sidecar_path']}")
        print(f"issue_count: {payload['issue_count']}")
        for issue in payload["issues"][:20]:
            print(f"- {issue['code']}: {issue['path']} {issue['message']}")
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moradin's Forge agent-first integration helper.")
    parser.add_argument("--forge-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("explain", help="Print the agent-first Forge explainer.")

    readiness = subparsers.add_parser("readiness", help="Check local Forge readiness.")
    readiness.add_argument("--json", action="store_true", help="Print JSON output.")
    readiness.add_argument("--target", type=Path, default=None)
    readiness.add_argument("--write-install-request", action="store_true")

    plan = subparsers.add_parser("plan", help="Write and print a dry-run integration plan.")
    plan.add_argument("--json", action="store_true", help="Print JSON output.")
    plan.add_argument("--target", type=Path, required=True)
    plan.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)
    plan.add_argument("--write-install-request", action="store_true")

    apply = subparsers.add_parser("apply", help="Apply Forge to a target repo after consent.")
    apply.add_argument("--json", action="store_true", help="Print JSON output.")
    apply.add_argument("--target", type=Path, required=True)
    apply.add_argument("--approve", action="store_true")
    apply.add_argument("--overwrite-sidecar", action="store_true")
    apply.add_argument("--patch-agents", action="store_true")
    apply.add_argument("--create-agents", action="store_true")
    apply.add_argument("--no-patch-agents", action="store_true")
    apply.add_argument("--write-install-request", action="store_true")
    apply.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)

    verify = subparsers.add_parser("verify", help="Verify an adopted Moradin sidecar.")
    verify.add_argument("--json", action="store_true", help="Print JSON output.")
    verify.add_argument("--target", type=Path, required=True)
    verify.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    forge_root = args.forge_root.resolve()
    try:
        if args.command == "explain":
            print(forge_explainer())
            return 0
        if args.command == "readiness":
            readiness = detect_readiness()
            if args.write_install_request:
                target_root = args.target.resolve() if args.target else None
                readiness["install_request"] = write_install_request_artifacts(
                    forge_root,
                    readiness,
                    target_root=target_root,
                )
            print_payload(readiness, args.json)
            return 0 if readiness["status"] == "ready" else 1
        if args.command == "plan":
            plan = build_integration_plan(forge_root, args.target, args.sidecar_dir)
            plan["artifacts"] = write_forge_run_artifacts(
                forge_root,
                plan,
                markdown_plan(plan),
            )
            if args.write_install_request:
                plan["install_request"] = write_install_request_artifacts(
                    forge_root,
                    plan["readiness"],
                    target_root=args.target.resolve(),
                )
            if args.json:
                print_payload(plan, True)
            else:
                print(markdown_plan(plan).rstrip())
                print(f"plan_artifact: {plan['artifacts']['markdown']}")
            return 0 if plan["readiness"]["status"] == "ready" else 1
        if args.command == "apply":
            result = apply_integration(
                forge_root,
                args.target,
                ForgeApplyOptions(
                    approve=args.approve,
                    overwrite_sidecar=args.overwrite_sidecar,
                    patch_agents=args.patch_agents and not args.no_patch_agents,
                    create_agents=args.create_agents,
                    write_install_request=args.write_install_request,
                    sidecar_dir=args.sidecar_dir,
                ),
            )
            print_payload(result, args.json)
            return 0
        if args.command == "verify":
            result = verify_integration(args.target, args.sidecar_dir)
            print_payload(result, args.json)
            return 0 if result["status"] == "pass" else 1
    except ForgeError as error:
        print(f"moradin-forge: {error}")
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
