#!/usr/bin/env python3
"""Agent-first Moradin Forge integration helpers."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.moradin_workstation import (
        ONBOARD_PLAN_VERSION,
        WORKSTATION_PLAN_VERSION,
        WorkstationError,
        agent_file_proposal,
        apply_tooling_plan,
        build_agent_adapter_section,
        build_offline_bundle,
        build_onboard_plan,
        build_tooling_plan,
        compact_repo_state,
        context_primer,
        diagnostic_brief,
        inspect_repository_capabilities,
        plan_digest,
        recommended_tool_specs,
        repo_brief,
        rerun_advice,
        rollback_tooling_receipt,
        session_checkpoint,
        tooling_plan_markdown,
        write_tooling_plan_artifacts,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from moradin_workstation import (  # type: ignore[no-redef]
        ONBOARD_PLAN_VERSION,
        WORKSTATION_PLAN_VERSION,
        WorkstationError,
        agent_file_proposal,
        apply_tooling_plan,
        build_agent_adapter_section,
        build_offline_bundle,
        build_onboard_plan,
        build_tooling_plan,
        compact_repo_state,
        context_primer,
        diagnostic_brief,
        inspect_repository_capabilities,
        plan_digest,
        recommended_tool_specs,
        repo_brief,
        rerun_advice,
        rollback_tooling_receipt,
        session_checkpoint,
        tooling_plan_markdown,
        write_tooling_plan_artifacts,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_MANIFEST_RELATIVE = Path("Harness/moradin_payload/manifest.yaml")
CONTROL_ROOT_RELATIVE = Path("Harness/artifacts/control")
DEFAULT_SIDECAR_DIR = ".moradins-harness"
OWNERSHIP_RECORD_RELATIVE = Path(
    "Harness/artifacts/control/forge_integration/ownership.json"
)
AGENTS_MARKER_BEGIN = "<!-- moradin-forge:start -->"
AGENTS_MARKER_END = "<!-- moradin-forge:end -->"
SUPPORTED_AGENT_FILES = ("AGENTS.md", "CLAUDE.md")
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
        "Harness/artifacts/control/efficiency",
        "Harness/artifacts/control/install_requests",
        "Harness/artifacts/control/migration_start",
        "Harness/artifacts/control/migration_waves",
        "Harness/artifacts/control/onboard_runs",
        f"Harness/artifacts/control/{PR_HARDENING_TOKEN}",
        "Harness/artifacts/control/public_export",
        "Harness/artifacts/control/repo_registry",
        "Harness/artifacts/control/discovery_sessions",
        "Harness/artifacts/control/tooling_plans",
        "Harness/artifacts/control/tooling_receipts",
        "Harness/artifacts/control/upgrade_runs",
    }
)
RUNTIME_ARTIFACT_PREFIXES = {
    "Harness/artifacts/control/efficiency",
    "Harness/artifacts/control/forge_runs",
    "Harness/artifacts/control/install_requests",
    "Harness/artifacts/control/onboard_runs",
    "Harness/artifacts/control/tooling_plans",
    "Harness/artifacts/control/tooling_receipts",
    "Harness/artifacts/control/upgrade_runs",
    "Harness/artifacts/control/forge_integration/upgrade_backups",
}
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
.PHONY: test payload-validate payload-smoke forge-explain forge-readiness forge-onboard forge-tooling-suite forge-tooling-suite-plan forge-tooling-suite-apply forge-tooling-suite-bundle forge-tooling-suite-verify forge-tooling-suite-rollback forge-tooling-plan forge-tooling-update-plan forge-tooling-apply forge-tooling-bundle forge-tooling-rollback forge-plan forge-adopt forge-verify forge-upgrade-plan forge-upgrade forge-upgrade-rollback forge-rollback forge-smoke

TARGET ?=
APPROVE ?=
OVERWRITE ?=
PATCH_AGENTS ?=
WORKSPACE ?=
PLAN ?=
PLAN_SHA256 ?=
OUTPUT ?=
RECEIPT ?=
APPROVE_RECEIPT_SHA256 ?=
AGENT_FILES ?=
CREATE_AGENT_FILES ?=
UPGRADE_ID ?=
PROFILE ?=
SELECT ?=
EXCLUDE ?=
CONTAINER_ENGINE ?=

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

forge-onboard:
\t@if [ -z "$(WORKSPACE)" ]; then echo "Usage: make forge-onboard WORKSPACE=<workspace-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py onboard --workspace "$(WORKSPACE)"

forge-tooling-suite:
\tinstall/tooling-suite.sh

forge-tooling-suite-plan:
\t@if [ -z "$(OUTPUT)" ]; then echo "Usage: make forge-tooling-suite-plan OUTPUT=<plan.json> [PROFILE=practical|extended] [SELECT='tool ...']"; exit 1; fi
\t@if [ -z "$(PROFILE)" ] && [ -z "$(SELECT)" ]; then echo "Set PROFILE=practical|extended or SELECT='tool ...'"; exit 1; fi
\tinstall/tooling-suite.sh plan $(if $(PROFILE),--profile "$(PROFILE)",--custom) $(foreach tool,$(SELECT),--select "$(tool)") $(foreach tool,$(EXCLUDE),--exclude "$(tool)") $(if $(CONTAINER_ENGINE),--container-engine "$(CONTAINER_ENGINE)",) --output "$(OUTPUT)"

forge-tooling-suite-apply:
\t@if [ -z "$(PLAN)" ] || [ -z "$(PLAN_SHA256)" ]; then echo "Usage: make forge-tooling-suite-apply PLAN=<plan.json> PLAN_SHA256=<digest>"; exit 1; fi
\tinstall/tooling-suite.sh apply --plan "$(PLAN)" --approve-plan-sha256 "$(PLAN_SHA256)"

forge-tooling-suite-bundle:
\t@if [ -z "$(PLAN)" ] || [ -z "$(OUTPUT)" ]; then echo "Usage: make forge-tooling-suite-bundle PLAN=<plan.json> OUTPUT=<bundle-path>"; exit 1; fi
\tinstall/tooling-suite.sh bundle --plan "$(PLAN)" --output "$(OUTPUT)"

forge-tooling-suite-verify:
\tinstall/tooling-suite.sh verify --receipt "$(if $(RECEIPT),$(RECEIPT),latest)"

forge-tooling-suite-rollback:
\t@if [ -z "$(RECEIPT)" ] || [ -z "$(APPROVE_RECEIPT_SHA256)" ]; then echo "Usage: make forge-tooling-suite-rollback RECEIPT=<receipt.json> APPROVE_RECEIPT_SHA256=<digest>"; exit 1; fi
\tinstall/tooling-suite.sh rollback --receipt "$(RECEIPT)" --approve-receipt-sha256 "$(APPROVE_RECEIPT_SHA256)"

forge-tooling-plan:
\t@if [ -z "$(WORKSPACE)" ]; then echo "Usage: make forge-tooling-plan WORKSPACE=<workspace-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-plan --workspace "$(WORKSPACE)"

forge-tooling-update-plan:
\t@if [ -z "$(WORKSPACE)" ]; then echo "Usage: make forge-tooling-update-plan WORKSPACE=<workspace-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-update-plan --workspace "$(WORKSPACE)"

forge-tooling-apply:
\t@if [ -z "$(PLAN)" ] || [ -z "$(PLAN_SHA256)" ]; then echo "Usage: make forge-tooling-apply PLAN=<plan.json> PLAN_SHA256=<digest>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-apply --plan "$(PLAN)" --approve-plan-sha256 "$(PLAN_SHA256)"

forge-tooling-bundle:
\t@if [ -z "$(PLAN)" ] || [ -z "$(OUTPUT)" ]; then echo "Usage: make forge-tooling-bundle PLAN=<plan.json> OUTPUT=<bundle-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-bundle --plan "$(PLAN)" --output "$(OUTPUT)"

forge-tooling-rollback:
\t@if [ -z "$(RECEIPT)" ] || [ "$(APPROVE)" != "1" ]; then echo "Usage: make forge-tooling-rollback RECEIPT=<receipt.json> APPROVE=1"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py tooling-rollback --receipt "$(RECEIPT)" --approve

forge-plan:
\t@if [ -z "$(TARGET)" ]; then echo "Usage: make forge-plan TARGET=<repo-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py plan --target "$(TARGET)" --write-install-request

forge-adopt:
\t@if [ -z "$(TARGET)" ] || [ "$(APPROVE)" != "1" ]; then echo "Usage: make forge-adopt TARGET=<repo-path> APPROVE=1"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py apply --target "$(TARGET)" --approve $(if $(OVERWRITE),--overwrite-sidecar,) $(if $(PATCH_AGENTS),--patch-agents,) $(foreach file,$(AGENT_FILES),--approve-agent-file $(file)) $(foreach file,$(CREATE_AGENT_FILES),--create-agent-file $(file)) --write-install-request

forge-verify:
\t@if [ -z "$(TARGET)" ]; then echo "Usage: make forge-verify TARGET=<repo-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py verify --target "$(TARGET)"

forge-upgrade-plan:
\t@if [ -z "$(TARGET)" ]; then echo "Usage: make forge-upgrade-plan TARGET=<repo-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py upgrade-plan --target "$(TARGET)"

forge-upgrade:
\t@if [ -z "$(TARGET)" ] || [ -z "$(PLAN)" ] || [ -z "$(PLAN_SHA256)" ]; then echo "Usage: make forge-upgrade TARGET=<repo-path> PLAN=<plan.json> PLAN_SHA256=<digest>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py upgrade --target "$(TARGET)" --plan "$(PLAN)" --approve-plan-sha256 "$(PLAN_SHA256)"

forge-upgrade-rollback:
\t@if [ -z "$(TARGET)" ] || [ -z "$(UPGRADE_ID)" ] || [ "$(APPROVE)" != "1" ]; then echo "Usage: make forge-upgrade-rollback TARGET=<repo-path> UPGRADE_ID=<id> APPROVE=1"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py upgrade-rollback --target "$(TARGET)" --upgrade-id "$(UPGRADE_ID)" --approve

forge-rollback:
\t@if [ -z "$(TARGET)" ] || [ "$(APPROVE)" != "1" ]; then echo "Usage: make forge-rollback TARGET=<repo-path> APPROVE=1"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py rollback --target "$(TARGET)" --approve

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
| FORGE-003 | execute only digest-approved, verified user-level tooling actions | docs/references/tooling_readiness_install_execution_contract_v2.md | review the exact plan digest before `tooling-apply` | active |
| FORGE-004 | preserve root workflows by default | docs/references/moradin_forge_agent_integration_contract_v1.md | write sidecar adapters before root patches | active |
| FORGE-005 | verify sidecars for portability before handoff | scripts/moradin_forge.py | run `forge verify` or `make forge-verify` | active |
| FORGE-006 | keep bootstrap separate from adoption | docs/references/moradin_forge_installer_bootstrap_contract_v1.md | run platform bootstrap only to prime Forge and write a start card | active |
| FORGE-007 | keep beta release visuals portable and local | README.md | scan SVG assets before public release | active |
| FORGE-008 | inspect only explicitly approved workspace roots | docs/references/tooling_readiness_install_execution_contract_v2.md | show discovered repositories before capability inspection | active |
| FORGE-009 | require independent approval for each agent file and user configuration change | docs/references/moradin_forge_agent_integration_contract_v1.md | show the owned block and request each consent separately | active |
| FORGE-010 | never invoke elevation automatically | docs/references/tooling_readiness_install_execution_contract_v2.md | generate a reviewable script for the user to run | active |
| FORGE-011 | bind upgrades to an exact plan and retain one predecessor | docs/references/moradin_forge_upgrade_contract_v1.md | stage, validate, switch, or restore byte-for-byte | active |
| FORGE-012 | store sanitized efficiency counters only | docs/references/moradin_agent_efficiency_contract_v1.md | omit prompts, source, commands, paths, and logs | active |
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
| FORGE-FEAT-004 | digest-bound workstation plans and verified user-level execution | implemented | docs/references/tooling_readiness_install_execution_contract_v2.md |
| FORGE-FEAT-005 | public export and sidecar portability scans | implemented | scripts/public_export.py |
| FORGE-FEAT-006 | low-token clone-and-prime bootstrap entrypoints | implemented | docs/references/moradin_forge_installer_bootstrap_contract_v1.md |
| FORGE-FEAT-007 | README visual overview for adoption and safety boundaries | implemented | docs/assets/readme/ |
| FORGE-FEAT-008 | bounded multi-workspace repository discovery | implemented | scripts/moradin_workstation.py |
| FORGE-FEAT-009 | independent AGENTS.md and CLAUDE.md owned blocks | implemented | scripts/moradin_forge.py |
| FORGE-FEAT-010 | checksummed offline tooling bundles and privileged user-run scripts | implemented | scripts/moradin_workstation.py |
| FORGE-FEAT-011 | transactional V1/V2 sidecar upgrades and immediate rollback | implemented | docs/references/moradin_forge_upgrade_contract_v1.md |
| FORGE-FEAT-012 | portable context primer, briefs, rerun advice, and sanitized counters | implemented | docs/references/moradin_agent_efficiency_contract_v1.md |
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
| PUBLIC-004 | 2026-07-28 | universal-agent-baseline | Prepared v0.2.0-beta.3 with bounded onboarding, approved user-level tooling, offline bundles, independent agent blocks, compact context helpers, and transactional upgrades. | candidate |
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
    agent_files: tuple[str, ...] = ()
    create_agent_files: tuple[str, ...] = ()
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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_manifest(
    root: Path,
    *,
    excluded_relative_paths: set[str] | None = None,
    excluded_top_level_names: set[str] | None = None,
    reject_symlinks: bool = True,
) -> dict[str, str]:
    """Return a deterministic path-to-digest map without following symlinks."""

    excluded_relative_paths = excluded_relative_paths or set()
    excluded_top_level_names = excluded_top_level_names or set()
    entries: dict[str, str] = {}
    if not root.exists():
        return entries
    for current_root, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current_root)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            path = current_path / dirname
            relative = path.relative_to(root).as_posix()
            if relative.split("/", 1)[0] in excluded_top_level_names:
                continue
            if path.is_symlink():
                if reject_symlinks:
                    raise ForgeError(f"managed tree symlink is not allowed: {relative}")
                entries[relative] = f"symlink:{os.readlink(path)}"
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in sorted(filenames):
            path = current_path / filename
            relative = path.relative_to(root).as_posix()
            if relative.split("/", 1)[0] in excluded_top_level_names:
                continue
            if relative in excluded_relative_paths:
                continue
            if path.is_symlink():
                if reject_symlinks:
                    raise ForgeError(f"managed tree symlink is not allowed: {relative}")
                entries[relative] = f"symlink:{os.readlink(path)}"
                continue
            if path.is_file():
                entries[relative] = sha256_file(path)
    return dict(sorted(entries.items()))


def manifest_digest(manifest: dict[str, str]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def target_root_digest(target_root: Path, sidecar_dir: str) -> str:
    manifest = file_manifest(
        target_root,
        excluded_top_level_names={".git", sidecar_dir},
        reject_symlinks=False,
    )
    return manifest_digest(manifest)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_bytes(payload)
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def install_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically install a staged directory without replacing any destination."""

    if platform.system() == "Linux":
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is not None:
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            result = renameat2(
                -100,
                os.fsencode(source),
                -100,
                os.fsencode(destination),
                1,
            )
            if result == 0:
                return
            error_number = ctypes.get_errno()
            if error_number == errno.EEXIST:
                raise ForgeError(f"sidecar appeared during staged apply: {destination}")
            if error_number not in {errno.ENOSYS, errno.EINVAL}:
                raise OSError(error_number, os.strerror(error_number), destination)
    if destination.exists() or destination.is_symlink():
        raise ForgeError(f"sidecar appeared during staged apply: {destination}")
    os.rename(source, destination)


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
            if is_runtime_artifact_path(relative):
                continue
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


def detect_readiness(target_root: Path | None = None) -> dict[str, Any]:
    capabilities = (
        set(inspect_repository_capabilities(target_root)["capabilities"])
        if target_root and target_root.is_dir()
        else set()
    )
    tool_specs = [
        {
            "id": catalog_spec.id,
            "label": catalog_spec.label,
            "command": catalog_spec.command,
            "commands": (
                ["python3", "python", "py"]
                if catalog_spec.id == "python"
                else ["fd", "fdfind"]
                if catalog_spec.id == "fd"
                else [catalog_spec.command]
            ),
            "required": catalog_spec.required,
            "human_run_commands": [],
            "category": catalog_spec.category,
        }
        for catalog_spec in recommended_tool_specs(capabilities)
        if catalog_spec.command
    ]
    checks = []
    for spec in tool_specs:
        commands = [str(item) for item in spec["commands"]]
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
        "detected_capabilities": sorted(capabilities),
        "missing_required": [check["id"] for check in missing_required],
        "missing_optional": [check["id"] for check in missing_optional],
        "status": "blocked" if missing_required else "ready",
        "safety": (
            "readiness did not install tools; user-level installation requires "
            "a digest-approved tooling plan and privileged actions require a user-run script"
        ),
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
    lowercase_agent_files = sorted(
        name
        for name in ("agents.md", "agent.md", "claude.md", "claud.md")
        if (target_root / name).is_file()
    )
    return {
        "path": target_root.as_posix(),
        "exists": target_root.exists(),
        "is_dir": target_root.is_dir(),
        "git_present": (target_root / ".git").exists(),
        "agents_present": (target_root / "AGENTS.md").is_file(),
        "claude_present": (target_root / "CLAUDE.md").is_file(),
        "lowercase_agent_file_warnings": lowercase_agent_files,
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
    writes = []
    for agent_file in SUPPORTED_AGENT_FILES:
        if (target_root / agent_file).is_file():
            writes.append(
                f"{agent_file} when apply is run with --approve-agent-file {agent_file}"
            )
        else:
            writes.append(
                f"{agent_file} when apply is run with --approve-agent-file "
                f"{agent_file} --create-agent-file {agent_file}"
            )
    return writes


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
    readiness = detect_readiness(target_root)
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
            "Tool execution requires a separate digest-approved tooling plan.",
            "Privileged actions are generated for the user and are never elevated automatically.",
            "Existing sidecars are preserved; use the transactional upgrade-plan and upgrade commands.",
        ],
        "status": "blocked_existing_sidecar" if snapshot["sidecar_present"] else readiness["status"],
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


def write_gap_tooling_plan(
    forge_root: Path,
    readiness: dict[str, Any],
    *,
    target_root: Path | None,
) -> dict[str, str]:
    if not readiness["missing_required"] and not readiness["missing_optional"]:
        return {}
    workspace = target_root.resolve() if target_root else forge_root.resolve()
    plan = build_tooling_plan(
        [workspace],
        forge_root=forge_root,
        profile="practical-full",
    )
    artifacts = write_tooling_plan_artifacts(forge_root, plan)
    return {
        **artifacts,
        "plan_sha256": str(plan["plan_sha256"]),
        "status": str(plan["status"]),
    }


def agents_adapter_section(sidecar_dir: str) -> str:
    """Compatibility wrapper for the original AGENTS.md adapter."""

    return build_agent_adapter_section(sidecar_dir, "AGENTS.md")


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
    claude_snippet = adapters_root / "CLAUDE.snippet.md"
    claude_snippet.write_text(
        build_agent_adapter_section(sidecar_dir, "CLAUDE.md"),
        encoding="utf-8",
    )
    written.append(claude_snippet.as_posix())
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
    """Compatibility wrapper for the original AGENTS.md-only option."""

    return patch_agent_file_adapter(
        target_root,
        sidecar_dir,
        "AGENTS.md",
        create_agent_file=create_agents,
    )


def patch_agent_file_adapter(
    target_root: Path,
    sidecar_dir: str,
    agent_file: str,
    *,
    create_agent_file: bool,
) -> str:
    if agent_file not in SUPPORTED_AGENT_FILES:
        raise ForgeError(f"unsupported agent guidance file: {agent_file}")
    path = target_root / agent_file
    if path.is_symlink():
        raise ForgeError(f"refusing to patch agent guidance symlink: {agent_file}")
    if not path.exists() and not create_agent_file:
        return "snippet_only"
    try:
        proposal = agent_file_proposal(
            target_root,
            agent_file,
            sidecar_dir=sidecar_dir,
        )
    except WorkstationError as error:
        raise ForgeError(str(error)) from error
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    section = str(proposal["owned_block"])
    if AGENTS_MARKER_BEGIN in existing:
        start = existing.index(AGENTS_MARKER_BEGIN)
        end = existing.index(AGENTS_MARKER_END, start) + len(AGENTS_MARKER_END)
        if end < len(existing) and existing[end] == "\n":
            end += 1
        rendered = existing[:start] + section + existing[end:]
        status = "already_present" if rendered == existing else "updated"
    elif not existing:
        rendered = f"# {agent_file}\n\n{section}"
        status = "created"
    else:
        separator = "" if existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n"
        rendered = existing + separator + section
        status = "patched"
    atomic_write_bytes(path, rendered.encode("utf-8"))
    return status


def agents_ownership_snapshot(
    agents_path: Path,
    *,
    adapter_status: str,
    before_payload: bytes | None,
) -> dict[str, Any]:
    """Compatibility wrapper for V1 callers and records."""

    return agent_file_ownership_snapshot(
        agents_path,
        agent_file="AGENTS.md",
        adapter_status=adapter_status,
        before_payload=before_payload,
    )


def extract_agent_marker_block(text: str) -> str:
    begin_count = text.count(AGENTS_MARKER_BEGIN)
    end_count = text.count(AGENTS_MARKER_END)
    if begin_count == 0 and end_count == 0:
        return ""
    if begin_count != 1 or end_count != 1:
        raise ForgeError("agent guidance contains ambiguous Moradin marker blocks")
    start = text.index(AGENTS_MARKER_BEGIN)
    end = text.index(AGENTS_MARKER_END, start) + len(AGENTS_MARKER_END)
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[start:end]


def agent_file_ownership_snapshot(
    path: Path,
    *,
    agent_file: str,
    adapter_status: str,
    before_payload: bytes | None,
) -> dict[str, Any]:
    after_payload = path.read_bytes() if path.is_file() else None
    before_text = (before_payload or b"").decode("utf-8", errors="strict")
    after_text = (after_payload or b"").decode("utf-8", errors="strict")
    before_block = extract_agent_marker_block(before_text)
    after_block = extract_agent_marker_block(after_text)
    owned = adapter_status in {"patched", "created", "updated"}
    return {
        "path": agent_file,
        "adapter_status": adapter_status,
        "existed_before": before_payload is not None,
        "before_size": len(before_payload or b""),
        "before_sha256": sha256_bytes(before_payload) if before_payload is not None else "",
        "after_sha256": sha256_bytes(after_payload) if after_payload is not None else "",
        "before_owned_block": before_block,
        "before_owned_block_sha256": (
            sha256_bytes(before_block.encode("utf-8")) if before_block else ""
        ),
        "owned_block_sha256": (
            sha256_bytes(after_block.encode("utf-8")) if after_block else ""
        ),
        "owned": owned,
    }


def write_ownership_record(
    sidecar_root: Path,
    *,
    sidecar_dir: str,
    target_root_hash_before: str,
    target_root_hash_after: str,
    agents: dict[str, Any] | None = None,
    agent_files: dict[str, dict[str, Any]] | None = None,
    upgrade_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    managed_files = file_manifest(
        sidecar_root,
        excluded_relative_paths={OWNERSHIP_RECORD_RELATIVE.as_posix()},
    )
    managed_files = {
        path: digest
        for path, digest in managed_files.items()
        if not is_runtime_artifact_path(path)
    }
    payload_manifest_path = sidecar_root / PAYLOAD_MANIFEST_RELATIVE
    payload_manifest = (
        load_payload_manifest(sidecar_root)
        if payload_manifest_path.is_file()
        else {"payload_version": ""}
    )
    normalized_agent_files = agent_files or (
        {"AGENTS.md": agents} if isinstance(agents, dict) else {}
    )
    payload: dict[str, Any] = {
        "version": "MoradinForgeOwnershipV2",
        "generated_at": utc_now(),
        "sidecar_dir": sidecar_dir,
        "payload_version": str(payload_manifest.get("payload_version", "")),
        "payload_manifest_sha256": (
            sha256_file(payload_manifest_path)
            if payload_manifest_path.is_file()
            else ""
        ),
        "compatibility": {
            "readable_ownership_versions": [
                "MoradinForgeOwnershipV1",
                "MoradinForgeOwnershipV2",
            ],
            "upgrade_contract": "plan-digest-bound-transactional-v1",
        },
        "managed_file_count": len(managed_files),
        "managed_files": managed_files,
        "managed_tree_sha256": manifest_digest(managed_files),
        "target_root_hash_before": target_root_hash_before,
        "target_root_hash_after": target_root_hash_after,
        "agents": normalized_agent_files.get("AGENTS.md", {}),
        "agent_files": normalized_agent_files,
        "upgrade_history": upgrade_history or [],
        "rollback_anchor": "v0.1.0-public-alpha",
    }
    write_json(sidecar_root / OWNERSHIP_RECORD_RELATIVE, payload)
    return payload


def load_ownership_record(sidecar_root: Path) -> dict[str, Any]:
    record_path = sidecar_root / OWNERSHIP_RECORD_RELATIVE
    if record_path.is_symlink() or not record_path.is_file():
        return {}
    try:
        payload = json.loads(record_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict) or payload.get("version") not in {
        "MoradinForgeOwnershipV1",
        "MoradinForgeOwnershipV2",
    }:
        return {}
    return payload


def ownership_issues(sidecar_root: Path) -> list[ForgeVerifyIssue]:
    ownership = load_ownership_record(sidecar_root)
    if not ownership:
        return [
            ForgeVerifyIssue(
                code="ownership_record_missing",
                path=OWNERSHIP_RECORD_RELATIVE.as_posix(),
                message="transactional ownership record is missing or invalid",
            )
        ]
    expected = ownership.get("managed_files")
    if not isinstance(expected, dict) or not all(
        isinstance(path, str) and isinstance(digest, str) for path, digest in expected.items()
    ):
        return [
            ForgeVerifyIssue(
                code="ownership_record_invalid",
                path=OWNERSHIP_RECORD_RELATIVE.as_posix(),
                message="managed_files must be a path-to-sha256 mapping",
            )
        ]
    try:
        actual = file_manifest(
            sidecar_root,
            excluded_relative_paths={OWNERSHIP_RECORD_RELATIVE.as_posix()},
        )
    except ForgeError as error:
        return [
            ForgeVerifyIssue(
                code="managed_content_unsafe",
                path=sidecar_root.as_posix(),
                message=str(error),
            )
        ]
    actual = {
        path: digest
        for path, digest in actual.items()
        if not is_runtime_artifact_path(path)
    }
    issues: list[ForgeVerifyIssue] = []
    for relative in sorted(set(expected) - set(actual)):
        issues.append(
            ForgeVerifyIssue(
                code="managed_file_missing",
                path=relative,
                message="managed sidecar file is missing",
            )
        )
    for relative in sorted(set(actual) - set(expected)):
        issues.append(
            ForgeVerifyIssue(
                code="unowned_sidecar_content",
                path=relative,
                message="sidecar contains content absent from the ownership record",
            )
        )
    for relative in sorted(set(expected) & set(actual)):
        if expected[relative] != actual[relative]:
            issues.append(
                ForgeVerifyIssue(
                    code="managed_file_modified",
                    path=relative,
                    message="managed sidecar file digest does not match the adoption record",
                )
            )
    if ownership.get("managed_tree_sha256") != manifest_digest(expected):
        issues.append(
            ForgeVerifyIssue(
                code="ownership_tree_digest_mismatch",
                path=OWNERSHIP_RECORD_RELATIVE.as_posix(),
                message="ownership record tree digest does not match its file manifest",
            )
        )
    return issues


def is_runtime_artifact_path(relative: str) -> bool:
    normalized = normalize_payload_relative_path(relative)
    return any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in RUNTIME_ARTIFACT_PREFIXES
    )


def write_integration_record(
    sidecar_root: Path,
    plan: dict[str, Any],
    copied_files: list[str],
    adapter_status: str,
    install_request: dict[str, str] | None,
    agent_file_statuses: dict[str, str] | None = None,
) -> dict[str, str]:
    output_root = sidecar_root / "Harness" / "artifacts" / "control" / "forge_integration"
    portable_plan = sanitize_portable_payload(plan)
    agent_file_statuses = agent_file_statuses or {}
    payload = {
        "version": "MoradinForgeIntegrationV2",
        "generated_at": utc_now(),
        "plan": portable_plan,
        "copied_file_count": len(copied_files),
        "copied_files": copied_files,
        "changed_paths": [
            f"{portable_plan['target_repo']['sidecar_dir']}/",
            *sorted(
                path
                for path, status in agent_file_statuses.items()
                if status in {"patched", "created", "updated"}
            ),
        ],
        "adapter_status": adapter_status,
        "agent_file_statuses": agent_file_statuses,
        "install_request": install_request or {},
        "validation_commands": [
            (
                f"{portable_plan['target_repo']['sidecar_dir']}/scripts/"
                "moradin_forge.sh verify --target ."
            ),
            "Run the target repo's existing deterministic test or verify command.",
        ],
        "rollback": [
            (
                f"Run `{portable_plan['target_repo']['sidecar_dir']}/scripts/"
                "moradin_forge.sh rollback --target . --approve`."
            ),
            "Rollback refuses modified or unowned managed content.",
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
        f"- install_request: `{portable_payload['install_request'].get('markdown', 'none')}`",
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
        "adapters/CLAUDE.snippet.md",
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
        issues.extend(ownership_issues(sidecar_root))
    issues.extend(scan_local_only_artifact_paths(sidecar_root))

    integration_record = load_integration_record(sidecar_root)
    adapter_status = str(integration_record.get("adapter_status", "unknown"))
    agent_file_statuses = integration_record.get("agent_file_statuses", {})
    if not isinstance(agent_file_statuses, dict):
        agent_file_statuses = {}
    if not agent_file_statuses and adapter_status not in {"disabled", "unknown"}:
        agent_file_statuses = {"AGENTS.md": adapter_status}
    for agent_file in SUPPORTED_AGENT_FILES:
        path = target_root / agent_file
        text = (
            path.read_text(encoding="utf-8", errors="replace")
            if path.is_file()
            else ""
        )
        status = str(agent_file_statuses.get(agent_file, "disabled"))
        if status in {"patched", "created", "updated", "already_present"}:
            if AGENTS_MARKER_BEGIN not in text:
                issues.append(
                    ForgeVerifyIssue(
                        code="agent_marker_missing",
                        path=agent_file,
                        message=(
                            f"integration record says {agent_file} was managed, "
                            "but its marker is absent"
                        ),
                    )
                )
        elif status in {"disabled", "snippet_only"} and AGENTS_MARKER_BEGIN in text:
            issues.append(
                ForgeVerifyIssue(
                    code="unexpected_agent_marker",
                    path=agent_file,
                    message=(
                        f"{agent_file} contains a Forge marker although the "
                        "integration record does not own it"
                    ),
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
            f"Run `{sidecar_dir}/scripts/moradin_forge.sh rollback --target . --approve`.",
            "Rollback refuses modified or unowned managed content.",
            "No host install commands were executed by Moradin.",
        ],
    }


def rollback_integration(
    target_root: Path,
    *,
    approve: bool,
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
) -> dict[str, Any]:
    if not approve:
        raise ForgeError("rollback requires --approve after the user has confirmed removal")
    sidecar_dir = normalize_sidecar_dir(sidecar_dir)
    target_root = target_root.resolve()
    if not target_root.is_dir():
        raise ForgeError(f"target repo must be an existing directory: {target_root}")
    sidecar_root = target_root / sidecar_dir
    if not sidecar_root.is_dir() or sidecar_root.is_symlink():
        raise ForgeError(f"managed sidecar does not exist: {sidecar_root}")
    issues = ownership_issues(sidecar_root)
    if issues:
        summary = "; ".join(f"{issue.code}:{issue.path}" for issue in issues[:5])
        raise ForgeError(f"rollback refused because managed content changed: {summary}")
    ownership = load_ownership_record(sidecar_root)
    ownership_version = str(ownership.get("version", ""))
    raw_agent_files = ownership.get("agent_files")
    if ownership_version == "MoradinForgeOwnershipV2":
        if not isinstance(raw_agent_files, dict):
            raise ForgeError("rollback refused because agent-file ownership metadata is invalid")
        agent_files = {
            str(path): metadata
            for path, metadata in raw_agent_files.items()
            if isinstance(path, str) and isinstance(metadata, dict)
        }
    else:
        agents = ownership.get("agents", {})
        if not isinstance(agents, dict):
            raise ForgeError("rollback refused because AGENTS.md ownership metadata is invalid")
        agent_files = {"AGENTS.md": agents}

    agent_bytes_before: dict[str, bytes | None] = {}
    agent_bytes_restored: dict[str, bytes | None] = {}
    owned_agent_files: list[str] = []
    for agent_file, metadata in sorted(agent_files.items()):
        if agent_file not in SUPPORTED_AGENT_FILES or not metadata.get("owned"):
            continue
        path = target_root / agent_file
        before = path.read_bytes() if path.is_file() else None
        if before is None:
            raise ForgeError(
                f"rollback refused because managed {agent_file} is missing"
            )
        agent_bytes_before[agent_file] = before
        if ownership_version == "MoradinForgeOwnershipV1":
            if sha256_bytes(before) != str(metadata.get("after_sha256", "")):
                raise ForgeError(
                    f"rollback refused because managed {agent_file} was modified"
                )
            status = str(metadata.get("adapter_status", ""))
            if status == "created":
                restored = None
            elif status == "patched":
                before_size = metadata.get("before_size")
                if not isinstance(before_size, int) or before_size < 0:
                    raise ForgeError(
                        f"rollback refused because {agent_file} size metadata is invalid"
                    )
                restored = before[:before_size]
                if sha256_bytes(restored) != str(metadata.get("before_sha256", "")):
                    raise ForgeError(
                        f"rollback refused because {agent_file} cannot be restored exactly"
                    )
            else:
                raise ForgeError(
                    f"rollback refused because {agent_file} ownership state is invalid"
                )
        else:
            restored = restore_agent_file_from_ownership(
                before,
                metadata,
                agent_file=agent_file,
            )
        agent_bytes_restored[agent_file] = restored
        owned_agent_files.append(agent_file)

    root_hash_before_rollback = target_root_digest(target_root, sidecar_dir)
    quarantine = target_root / f".{sidecar_dir.lstrip('.')}.rollback-{uuid.uuid4().hex}"
    os.replace(sidecar_root, quarantine)
    try:
        for agent_file in owned_agent_files:
            path = target_root / agent_file
            restored = agent_bytes_restored[agent_file]
            if restored is None:
                path.unlink()
            else:
                atomic_write_bytes(path, restored)
        shutil.rmtree(quarantine)
    except Exception:
        for agent_file in owned_agent_files:
            path = target_root / agent_file
            before = agent_bytes_before[agent_file]
            if before is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write_bytes(path, before)
        if quarantine.exists() and not sidecar_root.exists():
            os.replace(quarantine, sidecar_root)
        raise
    root_hash_after_rollback = target_root_digest(target_root, sidecar_dir)
    expected_root_hash = str(ownership.get("target_root_hash_before", ""))
    return {
        "version": "MoradinForgeRollbackResultV1",
        "generated_at": utc_now(),
        "target_repo": target_root.as_posix(),
        "sidecar_dir": sidecar_dir,
        "removed": True,
        "agents_restored": "AGENTS.md" in owned_agent_files,
        "agent_files_restored": owned_agent_files,
        "target_root_hash_before_rollback": root_hash_before_rollback,
        "target_root_hash_after_rollback": root_hash_after_rollback,
        "target_root_hash_expected": expected_root_hash,
        "target_root_hash_restored": root_hash_after_rollback == expected_root_hash,
        "status": "pass",
    }


def restore_agent_file_from_ownership(
    current_payload: bytes,
    metadata: dict[str, Any],
    *,
    agent_file: str,
) -> bytes | None:
    try:
        current = current_payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ForgeError(
            f"rollback refused because managed {agent_file} is not UTF-8"
        ) from error
    current_block = extract_agent_marker_block(current)
    expected_block_sha = str(metadata.get("owned_block_sha256", ""))
    if (
        not current_block
        or not expected_block_sha
        or sha256_bytes(current_block.encode("utf-8")) != expected_block_sha
    ):
        raise ForgeError(
            f"rollback refused because managed {agent_file} marker was modified"
        )
    start = current.index(AGENTS_MARKER_BEGIN)
    end = start + len(current_block)
    before_block = str(metadata.get("before_owned_block", ""))
    if before_block:
        restored_text = current[:start] + before_block + current[end:]
    else:
        prefix = current[:start]
        suffix = current[end:]
        candidates = [prefix + suffix]
        if prefix.endswith("\n"):
            candidates.append(prefix[:-1] + suffix)
        if prefix.endswith("\n\n"):
            candidates.append(prefix[:-2] + suffix)
        expected_before = str(metadata.get("before_sha256", ""))
        exact = next(
            (
                candidate
                for candidate in candidates
                if expected_before
                and sha256_bytes(candidate.encode("utf-8")) == expected_before
            ),
            None,
        )
        restored_text = exact if exact is not None else candidates[0]
    if (
        str(metadata.get("adapter_status", "")) == "created"
        and restored_text.strip() in {f"# {agent_file}", ""}
    ):
        return None
    return restored_text.encode("utf-8")


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
        if options.overwrite_sidecar:
            raise ForgeError(
                "existing sidecar preserved: --overwrite-sidecar is disabled; "
                "use upgrade-plan and upgrade with an exact approved digest"
            )
        raise ForgeError(f"sidecar already exists: {sidecar_root}")
    plan = build_integration_plan(forge_root, target_root, sidecar_dir)
    if plan["readiness"]["missing_required"]:
        write_install_request_artifacts(
            forge_root,
            plan["readiness"],
            target_root=target_root,
        )
        raise ForgeError(
            "apply blocked because required tooling is missing: "
            + ", ".join(plan["readiness"]["missing_required"])
        )
    target_root_hash_before = target_root_digest(target_root, sidecar_dir)
    approved_agent_files = set(options.agent_files)
    if options.patch_agents:
        approved_agent_files.add("AGENTS.md")
    invalid_agent_files = sorted(approved_agent_files - set(SUPPORTED_AGENT_FILES))
    if invalid_agent_files:
        raise ForgeError(
            "unsupported approved agent guidance files: "
            + ", ".join(invalid_agent_files)
        )
    create_agent_files = set(options.create_agent_files)
    if options.create_agents:
        create_agent_files.add("AGENTS.md")
    if not create_agent_files.issubset(approved_agent_files):
        raise ForgeError("--create-agent-file also requires --approve-agent-file")
    agent_paths = {
        name: target_root / name
        for name in sorted(approved_agent_files)
    }
    for name, path in agent_paths.items():
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ForgeError(
                f"approved agent guidance must be a regular root file: {name}"
            )
    agent_files_before = {
        name: path.read_bytes() if path.is_file() else None
        for name, path in agent_paths.items()
    }
    staging_root = target_root / f".{sidecar_dir.lstrip('.')}.staging-{uuid.uuid4().hex}"
    adapter_status = "disabled"
    agent_file_statuses: dict[str, str] = {}
    install_request = None
    copied_files: list[str] = []
    snippet_paths: list[str] = []
    try:
        staging_root.mkdir(parents=False)
        copied_files = copy_payload_to_sidecar(forge_root, staging_root)
        snippet_paths = write_adapter_snippets(staging_root, sidecar_dir, target_root)
        if options.write_install_request or plan["readiness"]["missing_optional"]:
            install_request = write_install_request_artifacts(
                forge_root,
                plan["readiness"],
                target_root=target_root,
            )
        write_integration_record(
            staging_root,
            plan,
            copied_files,
            "pending" if approved_agent_files else adapter_status,
            install_request,
            {
                name: "pending"
                for name in sorted(approved_agent_files)
            },
        )
        install_directory_no_replace(staging_root, sidecar_root)
        for agent_file in sorted(approved_agent_files):
            agent_file_statuses[agent_file] = patch_agent_file_adapter(
                target_root,
                sidecar_dir,
                agent_file,
                create_agent_file=agent_file in create_agent_files,
            )
        if agent_file_statuses:
            statuses = sorted(set(agent_file_statuses.values()))
            adapter_status = statuses[0] if len(statuses) == 1 else "multiple"
            write_integration_record(
                sidecar_root,
                plan,
                copied_files,
                adapter_status,
                install_request,
                agent_file_statuses,
            )
        target_root_hash_after = target_root_digest(target_root, sidecar_dir)
        ownership_agent_files = {
            name: agent_file_ownership_snapshot(
                agent_paths[name],
                agent_file=name,
                adapter_status=agent_file_statuses.get(name, "snippet_only"),
                before_payload=agent_files_before[name],
            )
            for name in sorted(approved_agent_files)
        }
        ownership = write_ownership_record(
            sidecar_root,
            sidecar_dir=sidecar_dir,
            target_root_hash_before=target_root_hash_before,
            target_root_hash_after=target_root_hash_after,
            agent_files=ownership_agent_files,
        )
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        if sidecar_root.exists():
            shutil.rmtree(sidecar_root)
        for name, path in agent_paths.items():
            before = agent_files_before[name]
            if before is None:
                if path.exists():
                    path.unlink()
            elif not path.is_file() or path.read_bytes() != before:
                atomic_write_bytes(path, before)
        raise
    integration_record = {
        "json": (sidecar_root / "Harness/artifacts/control/forge_integration/integration.json").as_posix(),
        "markdown": (sidecar_root / "Harness/artifacts/control/forge_integration/integration.md").as_posix(),
    }
    return {
        "version": "MoradinForgeApplyResultV1",
        "generated_at": utc_now(),
        "target_repo": target_root.as_posix(),
        "sidecar_path": sidecar_root.as_posix(),
        "copied_file_count": len(copied_files),
        "adapter_status": adapter_status,
        "agent_file_statuses": agent_file_statuses,
        "adapter_snippets": [
            (sidecar_root / Path(path).relative_to(staging_root)).as_posix()
            if Path(path).is_relative_to(staging_root)
            else path
            for path in snippet_paths
        ],
        "install_request": install_request or {},
        "integration_record": integration_record,
        "ownership_record": (sidecar_root / OWNERSHIP_RECORD_RELATIVE).as_posix(),
        "managed_tree_sha256": ownership["managed_tree_sha256"],
        "target_root_hash_before": target_root_hash_before,
        "target_root_hash_after": target_root_hash_after,
    }


UPGRADE_PLAN_VERSION = "MoradinForgeUpgradePlanV1"
UPGRADE_RESULT_VERSION = "MoradinForgeUpgradeResultV1"
UPGRADE_ROLLBACK_RESULT_VERSION = "MoradinForgeUpgradeRollbackResultV1"
UPGRADE_BACKUPS_RELATIVE = Path(
    "Harness/artifacts/control/forge_integration/upgrade_backups"
)


def candidate_sidecar_manifest(
    forge_root: Path,
    target_root: Path,
    sidecar_dir: str,
) -> tuple[dict[str, str], str]:
    with tempfile.TemporaryDirectory(prefix="moradin-upgrade-plan-") as temporary:
        candidate = Path(temporary) / "candidate"
        copy_payload_to_sidecar(forge_root, candidate)
        write_adapter_snippets(candidate, sidecar_dir, target_root)
        manifest = file_manifest(candidate)
        return manifest, manifest_digest(manifest)


def build_upgrade_plan(
    forge_root: Path,
    target_root: Path,
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
) -> dict[str, Any]:
    sidecar_dir = normalize_sidecar_dir(sidecar_dir)
    target_root = target_root.resolve()
    sidecar_root = target_root / sidecar_dir
    if not target_root.is_dir():
        raise ForgeError(f"target repo must be an existing directory: {target_root}")
    if not sidecar_root.is_dir() or sidecar_root.is_symlink():
        raise ForgeError(f"managed sidecar does not exist: {sidecar_root}")
    issues = ownership_issues(sidecar_root)
    if issues:
        summary = "; ".join(f"{item.code}:{item.path}" for item in issues[:5])
        raise ForgeError(
            "upgrade plan refused because managed content changed: " + summary
        )
    ownership = load_ownership_record(sidecar_root)
    source_manifest = load_payload_manifest(forge_root)
    candidate_files, candidate_digest = candidate_sidecar_manifest(
        forge_root,
        target_root,
        sidecar_dir,
    )
    current_files = ownership.get("managed_files", {})
    if not isinstance(current_files, dict):
        raise ForgeError("installed ownership record has invalid managed files")
    ignored_dynamic = {
        "Harness/artifacts/control/forge_integration/integration.json",
        "Harness/artifacts/control/forge_integration/integration.md",
    }
    current_comparable = {
        path: digest
        for path, digest in current_files.items()
        if path not in ignored_dynamic
        and not path.startswith(f"{UPGRADE_BACKUPS_RELATIVE.as_posix()}/")
    }
    candidate_comparable = {
        path: digest
        for path, digest in candidate_files.items()
        if path not in ignored_dynamic
    }
    added = sorted(set(candidate_comparable) - set(current_comparable))
    removed = sorted(set(current_comparable) - set(candidate_comparable))
    modified = sorted(
        path
        for path in set(current_comparable) & set(candidate_comparable)
        if current_comparable[path] != candidate_comparable[path]
    )
    raw_agent_files = ownership.get("agent_files")
    if not isinstance(raw_agent_files, dict):
        raw_agents = ownership.get("agents")
        raw_agent_files = (
            {"AGENTS.md": raw_agents} if isinstance(raw_agents, dict) else {}
        )
    agent_proposals = []
    for agent_file, metadata in sorted(raw_agent_files.items()):
        if (
            agent_file in SUPPORTED_AGENT_FILES
            and isinstance(metadata, dict)
            and metadata.get("owned")
        ):
            try:
                proposal = agent_file_proposal(
                    target_root,
                    agent_file,
                    sidecar_dir=sidecar_dir,
                )
            except WorkstationError as error:
                raise ForgeError(str(error)) from error
            agent_proposals.append(proposal)
    payload: dict[str, Any] = {
        "version": UPGRADE_PLAN_VERSION,
        "generated_at": utc_now(),
        "forge_root": forge_root.resolve().as_posix(),
        "target_repo": target_root.as_posix(),
        "sidecar_dir": sidecar_dir,
        "current": {
            "ownership_version": ownership.get("version", ""),
            "payload_version": ownership.get("payload_version", ""),
            "managed_tree_sha256": ownership.get("managed_tree_sha256", ""),
        },
        "proposed": {
            "payload_version": source_manifest.get("payload_version", ""),
            "payload_manifest_sha256": sha256_file(
                forge_root / PAYLOAD_MANIFEST_RELATIVE
            ),
            "candidate_tree_sha256": candidate_digest,
            "candidate_file_count": len(candidate_files),
        },
        "changes": {
            "added": added,
            "modified": modified,
            "removed": removed,
        },
        "agent_file_proposals": agent_proposals,
        "preconditions": [
            "The installed ownership record remains unchanged.",
            "All managed sidecar files remain owned and unmodified.",
            "Every managed agent marker remains byte-identical.",
            "The source payload manifest remains unchanged.",
            "The approved plan digest matches this document.",
        ],
        "rollback": (
            "The upgrade retains one Forge-owned prior sidecar and supports "
            "upgrade-rollback for the immediate predecessor."
        ),
        "status": "ready",
    }
    payload["plan_sha256"] = plan_digest(payload)
    return payload


def upgrade_plan_markdown(plan: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Moradin Forge Upgrade Plan",
            "",
            f"- generated_at: `{plan['generated_at']}`",
            f"- target_repo: `{plan['target_repo']}`",
            f"- sidecar_dir: `{plan['sidecar_dir']}`",
            f"- current_payload: `{plan['current']['payload_version'] or 'legacy-v1'}`",
            f"- proposed_payload: `{plan['proposed']['payload_version']}`",
            f"- added_paths: `{len(plan['changes']['added'])}`",
            f"- modified_paths: `{len(plan['changes']['modified'])}`",
            f"- removed_paths: `{len(plan['changes']['removed'])}`",
            f"- agent_file_proposals: `{len(plan['agent_file_proposals'])}`",
            f"- plan_sha256: `{plan['plan_sha256']}`",
            "",
            "## Preconditions",
            "",
            *[f"- {item}" for item in plan["preconditions"]],
            "",
            "## Rollback",
            "",
            f"- {plan['rollback']}",
            "",
        ]
    )


def write_upgrade_plan_artifacts(
    forge_root: Path,
    plan: dict[str, Any],
) -> dict[str, str]:
    run_id = datetime.now(tz=UTC).strftime("upgrade_%Y%m%dT%H%M%S%fZ")
    root = forge_root / CONTROL_ROOT_RELATIVE / "upgrade_runs" / run_id
    json_path = root / "upgrade_plan.json"
    markdown_path = root / "upgrade_plan.md"
    write_json(json_path, plan)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(upgrade_plan_markdown(plan), encoding="utf-8")
    return {
        "run_id": run_id,
        "json": json_path.as_posix(),
        "markdown": markdown_path.as_posix(),
    }


def load_upgrade_plan(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ForgeError(f"upgrade plan must be a regular file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ForgeError(f"upgrade plan is not valid JSON: {path}") from error
    if not isinstance(payload, dict) or payload.get("version") != UPGRADE_PLAN_VERSION:
        raise ForgeError(f"upgrade plan version must be {UPGRADE_PLAN_VERSION}")
    if payload.get("plan_sha256") != plan_digest(payload):
        raise ForgeError("upgrade plan digest is missing or does not match its contents")
    return payload


def _copy_sidecar_without_prior_backups(source: Path, destination: Path) -> None:
    def ignore(path: str, names: list[str]) -> set[str]:
        current = Path(path)
        if current.name == "forge_integration" and "upgrade_backups" in names:
            return {"upgrade_backups"}
        return set()

    shutil.copytree(source, destination, symlinks=False, ignore=ignore)


def _copy_runtime_artifacts(source: Path, destination: Path) -> None:
    for relative in sorted(RUNTIME_ARTIFACT_PREFIXES):
        if relative == UPGRADE_BACKUPS_RELATIVE.as_posix():
            continue
        source_path = source / relative
        if not source_path.exists():
            continue
        destination_path = destination / relative
        if source_path.is_dir() and not source_path.is_symlink():
            shutil.copytree(
                source_path,
                destination_path,
                dirs_exist_ok=True,
                symlinks=False,
            )
        elif source_path.is_file() and not source_path.is_symlink():
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)


def _agent_metadata_map(ownership: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = ownership.get("agent_files")
    if isinstance(raw, dict):
        return {
            str(path): metadata
            for path, metadata in raw.items()
            if isinstance(path, str) and isinstance(metadata, dict)
        }
    agents = ownership.get("agents")
    return {"AGENTS.md": agents} if isinstance(agents, dict) else {}


def _agent_block_for_upgrade(path: Path, metadata: dict[str, Any]) -> str:
    if not metadata.get("owned"):
        return ""
    if not path.is_file() or path.is_symlink():
        raise ForgeError(f"managed agent guidance is missing or unsafe: {path.name}")
    text = path.read_text(encoding="utf-8")
    block = extract_agent_marker_block(text)
    expected = str(metadata.get("owned_block_sha256", ""))
    if expected:
        if not block or sha256_bytes(block.encode("utf-8")) != expected:
            raise ForgeError(f"managed {path.name} marker was modified")
    else:
        after_sha = str(metadata.get("after_sha256", ""))
        if not after_sha or sha256_file(path) != after_sha:
            raise ForgeError(f"legacy managed {path.name} was modified")
    return block


def _carry_agent_origin(
    snapshot: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    carried = dict(snapshot)
    for key in (
        "adapter_status",
        "existed_before",
        "before_size",
        "before_sha256",
        "before_owned_block",
        "before_owned_block_sha256",
    ):
        if key in previous:
            carried[key] = previous[key]
    if "before_owned_block" not in previous and previous.get("adapter_status") in {
        "patched",
        "created",
    }:
        carried["before_owned_block"] = ""
        carried["before_owned_block_sha256"] = ""
    carried["owned"] = bool(previous.get("owned", snapshot.get("owned")))
    return carried


def upgrade_integration(
    forge_root: Path,
    target_root: Path,
    *,
    plan_path: Path,
    approved_sha256: str,
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
) -> dict[str, Any]:
    plan = load_upgrade_plan(plan_path)
    if approved_sha256 != plan["plan_sha256"]:
        raise ForgeError("approved plan digest does not match the upgrade plan")
    sidecar_dir = normalize_sidecar_dir(sidecar_dir)
    target_root = target_root.resolve()
    if plan["target_repo"] != target_root.as_posix() or plan["sidecar_dir"] != sidecar_dir:
        raise ForgeError("upgrade plan target does not match the requested target")
    sidecar_root = target_root / sidecar_dir
    issues = ownership_issues(sidecar_root)
    if issues:
        summary = "; ".join(f"{item.code}:{item.path}" for item in issues[:5])
        raise ForgeError("upgrade refused because managed content changed: " + summary)
    ownership = load_ownership_record(sidecar_root)
    if ownership.get("managed_tree_sha256") != plan["current"]["managed_tree_sha256"]:
        raise ForgeError("upgrade plan is stale: installed managed tree changed")
    source_manifest_sha = sha256_file(forge_root / PAYLOAD_MANIFEST_RELATIVE)
    if source_manifest_sha != plan["proposed"]["payload_manifest_sha256"]:
        raise ForgeError("upgrade plan is stale: source payload manifest changed")
    _candidate, candidate_digest = candidate_sidecar_manifest(
        forge_root,
        target_root,
        sidecar_dir,
    )
    if candidate_digest != plan["proposed"]["candidate_tree_sha256"]:
        raise ForgeError("upgrade plan is stale: source payload contents changed")

    previous_agent_metadata = _agent_metadata_map(ownership)
    agent_bytes_before: dict[str, bytes] = {}
    previous_agent_blocks: dict[str, dict[str, str]] = {}
    for agent_file, metadata in sorted(previous_agent_metadata.items()):
        if agent_file not in SUPPORTED_AGENT_FILES or not metadata.get("owned"):
            continue
        path = target_root / agent_file
        block = _agent_block_for_upgrade(path, metadata)
        agent_bytes_before[agent_file] = path.read_bytes()
        previous_agent_blocks[agent_file] = {
            "owned_block": block,
            "owned_block_sha256": (
                sha256_bytes(block.encode("utf-8")) if block else ""
            ),
        }

    upgrade_id = datetime.now(tz=UTC).strftime("upgrade_%Y%m%dT%H%M%S%fZ")
    staging_root = target_root / f".{sidecar_dir.lstrip('.')}.upgrade-{uuid.uuid4().hex}"
    quarantine = target_root / f".{sidecar_dir.lstrip('.')}.previous-{uuid.uuid4().hex}"
    copied_files: list[str] = []
    quarantined = False
    swapped = False
    try:
        staging_root.mkdir()
        copied_files = copy_payload_to_sidecar(forge_root, staging_root)
        write_adapter_snippets(staging_root, sidecar_dir, target_root)
        staged_manifest = file_manifest(staging_root)
        staged_digest = manifest_digest(staged_manifest)
        if staged_digest != plan["proposed"]["candidate_tree_sha256"]:
            raise ForgeError(
                "staged upgrade payload does not match the approved candidate"
            )
        staged_issues = scan_forbidden_sidecar_references(staging_root)
        if staged_issues:
            raise ForgeError(
                "staged upgrade payload failed portability validation: "
                + "; ".join(
                    f"{item.code}:{item.path}" for item in staged_issues[:5]
                )
            )
        _copy_runtime_artifacts(sidecar_root, staging_root)
        backup_root = staging_root / UPGRADE_BACKUPS_RELATIVE / upgrade_id
        _copy_sidecar_without_prior_backups(sidecar_root, backup_root / "sidecar")
        write_json(
            backup_root / "upgrade_backup.json",
            {
                "version": "MoradinForgeUpgradeBackupV1",
                "upgrade_id": upgrade_id,
                "created_at": utc_now(),
                "previous_payload_version": ownership.get("payload_version", ""),
                "previous_managed_tree_sha256": ownership.get(
                    "managed_tree_sha256",
                    "",
                ),
                "agent_files": previous_agent_blocks,
            },
        )
        write_integration_record(
            staging_root,
            {
                "target_repo": {
                    "path": target_root.as_posix(),
                    "sidecar_dir": sidecar_dir,
                },
                "upgrade_plan": plan,
            },
            copied_files,
            "pending",
            None,
            {path: "pending" for path in previous_agent_blocks},
        )
        os.replace(sidecar_root, quarantine)
        quarantined = True
        os.replace(staging_root, sidecar_root)
        swapped = True

        statuses: dict[str, str] = {}
        new_agent_metadata: dict[str, dict[str, Any]] = {}
        for agent_file, previous in sorted(previous_agent_metadata.items()):
            if agent_file not in previous_agent_blocks:
                continue
            path = target_root / agent_file
            statuses[agent_file] = patch_agent_file_adapter(
                target_root,
                sidecar_dir,
                agent_file,
                create_agent_file=False,
            )
            snapshot = agent_file_ownership_snapshot(
                path,
                agent_file=agent_file,
                adapter_status=statuses[agent_file],
                before_payload=agent_bytes_before[agent_file],
            )
            new_agent_metadata[agent_file] = _carry_agent_origin(snapshot, previous)
        adapter_status = (
            next(iter(statuses.values()))
            if len(statuses) == 1
            else "multiple" if statuses else "disabled"
        )
        write_integration_record(
            sidecar_root,
            {
                "target_repo": {
                    "path": target_root.as_posix(),
                    "sidecar_dir": sidecar_dir,
                },
                "upgrade_plan": plan,
            },
            copied_files,
            adapter_status,
            None,
            statuses,
        )
        history = ownership.get("upgrade_history", [])
        if not isinstance(history, list):
            history = []
        history = [
            *history,
            {
                "upgrade_id": upgrade_id,
                "from_payload_version": ownership.get("payload_version", ""),
                "to_payload_version": plan["proposed"]["payload_version"],
                "plan_sha256": plan["plan_sha256"],
                "completed_at": utc_now(),
            },
        ][-20:]
        target_hash = target_root_digest(target_root, sidecar_dir)
        new_ownership = write_ownership_record(
            sidecar_root,
            sidecar_dir=sidecar_dir,
            target_root_hash_before=str(
                ownership.get("target_root_hash_before", target_hash)
            ),
            target_root_hash_after=target_hash,
            agent_files=new_agent_metadata,
            upgrade_history=history,
        )
        verification = verify_integration(target_root, sidecar_dir)
        if verification["status"] != "pass":
            raise ForgeError(
                "upgraded sidecar failed verification: "
                + "; ".join(
                    f"{item['code']}:{item['path']}"
                    for item in verification["issues"][:5]
                )
            )
        shutil.rmtree(quarantine)
    except Exception:
        if swapped:
            if sidecar_root.exists():
                shutil.rmtree(sidecar_root)
        if quarantined and quarantine.exists() and not sidecar_root.exists():
            os.replace(quarantine, sidecar_root)
        if staging_root.exists():
            shutil.rmtree(staging_root)
        for agent_file, before in agent_bytes_before.items():
            atomic_write_bytes(target_root / agent_file, before)
        raise
    return {
        "version": UPGRADE_RESULT_VERSION,
        "generated_at": utc_now(),
        "status": "pass",
        "upgrade_id": upgrade_id,
        "target_repo": target_root.as_posix(),
        "sidecar_dir": sidecar_dir,
        "payload_version": plan["proposed"]["payload_version"],
        "plan_sha256": plan["plan_sha256"],
        "managed_tree_sha256": new_ownership["managed_tree_sha256"],
        "rollback_command": (
            f"{sidecar_dir}/scripts/moradin_forge.sh upgrade-rollback "
            f"--target . --upgrade-id {upgrade_id} --approve"
        ),
    }


def _replace_current_agent_block(
    current_payload: bytes,
    *,
    current_metadata: dict[str, Any],
    previous_block: str,
    agent_file: str,
) -> bytes:
    current = current_payload.decode("utf-8")
    current_block = extract_agent_marker_block(current)
    expected = str(current_metadata.get("owned_block_sha256", ""))
    if not current_block or sha256_bytes(current_block.encode("utf-8")) != expected:
        raise ForgeError(
            f"upgrade rollback refused because managed {agent_file} marker changed"
        )
    start = current.index(AGENTS_MARKER_BEGIN)
    end = start + len(current_block)
    return (current[:start] + previous_block + current[end:]).encode("utf-8")


def rollback_upgrade(
    target_root: Path,
    *,
    upgrade_id: str,
    approve: bool,
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
) -> dict[str, Any]:
    if not approve:
        raise ForgeError("upgrade rollback requires --approve")
    if not re.fullmatch(r"upgrade_[0-9]{8}T[0-9]{12}Z", upgrade_id):
        raise ForgeError("upgrade_id has an invalid format")
    sidecar_dir = normalize_sidecar_dir(sidecar_dir)
    target_root = target_root.resolve()
    sidecar_root = target_root / sidecar_dir
    issues = ownership_issues(sidecar_root)
    if issues:
        summary = "; ".join(f"{item.code}:{item.path}" for item in issues[:5])
        raise ForgeError(
            "upgrade rollback refused because managed content changed: " + summary
        )
    current_ownership = load_ownership_record(sidecar_root)
    backup_root = sidecar_root / UPGRADE_BACKUPS_RELATIVE / upgrade_id
    backup_sidecar = backup_root / "sidecar"
    backup_metadata_path = backup_root / "upgrade_backup.json"
    if (
        not backup_sidecar.is_dir()
        or backup_sidecar.is_symlink()
        or not backup_metadata_path.is_file()
        or backup_metadata_path.is_symlink()
    ):
        raise ForgeError(f"upgrade backup does not exist: {upgrade_id}")
    try:
        backup_metadata = json.loads(
            backup_metadata_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ForgeError("upgrade backup metadata is invalid") from error
    if (
        not isinstance(backup_metadata, dict)
        or backup_metadata.get("version") != "MoradinForgeUpgradeBackupV1"
        or backup_metadata.get("upgrade_id") != upgrade_id
        or not isinstance(backup_metadata.get("agent_files"), dict)
    ):
        raise ForgeError("upgrade backup metadata does not match the requested id")
    backup_issues = ownership_issues(backup_sidecar)
    if backup_issues:
        summary = "; ".join(
            f"{item.code}:{item.path}" for item in backup_issues[:5]
        )
        raise ForgeError(
            "upgrade backup failed ownership verification: " + summary
        )

    current_agent_metadata = _agent_metadata_map(current_ownership)
    agent_bytes_before: dict[str, bytes] = {}
    agent_bytes_restored: dict[str, bytes] = {}
    for agent_file, previous in backup_metadata["agent_files"].items():
        if (
            agent_file not in SUPPORTED_AGENT_FILES
            or not isinstance(previous, dict)
            or agent_file not in current_agent_metadata
        ):
            continue
        previous_block = str(previous.get("owned_block", ""))
        previous_block_sha = str(previous.get("owned_block_sha256", ""))
        if (
            not previous_block
            or not previous_block_sha
            or sha256_bytes(previous_block.encode("utf-8"))
            != previous_block_sha
        ):
            raise ForgeError(
                f"upgrade backup marker metadata is invalid for {agent_file}"
            )
        path = target_root / agent_file
        before = path.read_bytes()
        agent_bytes_before[agent_file] = before
        agent_bytes_restored[agent_file] = _replace_current_agent_block(
            before,
            current_metadata=current_agent_metadata[agent_file],
            previous_block=previous_block,
            agent_file=agent_file,
        )

    staging = target_root / f".{sidecar_dir.lstrip('.')}.restore-{uuid.uuid4().hex}"
    quarantine = target_root / f".{sidecar_dir.lstrip('.')}.failed-{uuid.uuid4().hex}"
    _copy_sidecar_without_prior_backups(backup_sidecar, staging)
    quarantined = False
    swapped = False
    try:
        os.replace(sidecar_root, quarantine)
        quarantined = True
        os.replace(staging, sidecar_root)
        swapped = True
        for agent_file, restored in agent_bytes_restored.items():
            atomic_write_bytes(target_root / agent_file, restored)
        verification = verify_integration(target_root, sidecar_dir)
        if verification["status"] != "pass":
            raise ForgeError(
                "restored sidecar failed verification: "
                + "; ".join(
                    f"{item['code']}:{item['path']}"
                    for item in verification["issues"][:5]
                )
            )
        shutil.rmtree(quarantine)
    except Exception:
        if swapped:
            if sidecar_root.exists():
                shutil.rmtree(sidecar_root)
        if quarantined and quarantine.exists() and not sidecar_root.exists():
            os.replace(quarantine, sidecar_root)
        if staging.exists():
            shutil.rmtree(staging)
        for agent_file, before in agent_bytes_before.items():
            atomic_write_bytes(target_root / agent_file, before)
        raise
    restored_ownership = load_ownership_record(sidecar_root)
    return {
        "version": UPGRADE_ROLLBACK_RESULT_VERSION,
        "generated_at": utc_now(),
        "status": "pass",
        "upgrade_id": upgrade_id,
        "target_repo": target_root.as_posix(),
        "sidecar_dir": sidecar_dir,
        "payload_version": restored_ownership.get("payload_version", ""),
        "managed_tree_sha256": restored_ownership.get("managed_tree_sha256", ""),
    }


def forge_explainer() -> str:
    return """Moradin's Forge is an agent-first local integration kit.

When a user sends an agent here, first ask which workspace roots may be
inspected. Discover repositories only below those roots and show the list
before reading standard guidance, manifests, CI, container, and deployment
configuration. Explain the proposed tooling, local sidecar, independently
owned AGENTS.md or CLAUDE.md blocks, validation, and rollback.

Verified user-level installers may run only after the user approves the exact
tooling-plan digest. Forge never elevates itself: it generates reviewable Bash
or PowerShell scripts for the user to run. Existing repo workflows and
unrelated agent guidance remain untouched.

The deterministic path is:
1. `scripts/moradin_forge.sh explain`
2. `scripts/moradin_forge.sh onboard --workspace <approved-workspace>`
3. review workspace scope, tools, configuration, agent blocks, and scripts
4. apply only the separately approved tooling and repository actions
5. `scripts/moradin_forge.sh verify --target <repo>`
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
    if payload.get("version") == "MoradinForgeRollbackResultV1":
        print(f"rollback: {payload['status']}")
        print(f"target_repo: {payload['target_repo']}")
        print(f"agents_restored: {payload['agents_restored']}")
        return
    if payload.get("version") in {
        ONBOARD_PLAN_VERSION,
        WORKSTATION_PLAN_VERSION,
        UPGRADE_PLAN_VERSION,
        UPGRADE_RESULT_VERSION,
        UPGRADE_ROLLBACK_RESULT_VERSION,
    }:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moradin's Forge agent-first integration helper.")
    parser.add_argument("--forge-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("explain", help="Print the agent-first Forge explainer.")

    onboard = subparsers.add_parser(
        "onboard",
        help="Discover repositories below approved workspaces and produce a consent plan.",
    )
    onboard.add_argument("--json", action="store_true", help="Print JSON output.")
    onboard.add_argument("--workspace", type=Path, action="append", required=True)
    onboard.add_argument("--profile", default="practical-full")
    onboard.add_argument("--refresh-versions", action="store_true")
    onboard.add_argument("--include-tool", action="append", default=[])
    onboard.add_argument("--exclude-tool", action="append", default=[])

    tooling_plan = subparsers.add_parser(
        "tooling-plan",
        help="Build an adaptive practical-full workstation plan.",
    )
    tooling_plan.add_argument("--json", action="store_true", help="Print JSON output.")
    tooling_plan.add_argument("--workspace", type=Path, action="append", required=True)
    tooling_plan.add_argument("--profile", default="practical-full")
    tooling_plan.add_argument("--refresh-versions", action="store_true")
    tooling_plan.add_argument("--include-tool", action="append", default=[])
    tooling_plan.add_argument("--exclude-tool", action="append", default=[])

    tooling_update = subparsers.add_parser(
        "tooling-update-plan",
        help="Refresh latest stable metadata and build a tooling update plan.",
    )
    tooling_update.add_argument("--json", action="store_true", help="Print JSON output.")
    tooling_update.add_argument("--workspace", type=Path, action="append", required=True)
    tooling_update.add_argument("--profile", default="practical-full")
    tooling_update.add_argument("--include-tool", action="append", default=[])
    tooling_update.add_argument("--exclude-tool", action="append", default=[])

    tooling_apply = subparsers.add_parser(
        "tooling-apply",
        help="Execute digest-approved user-level tooling actions.",
    )
    tooling_apply.add_argument("--json", action="store_true", help="Print JSON output.")
    tooling_apply.add_argument("--plan", type=Path, required=True)
    tooling_apply.add_argument("--approve-plan-sha256", required=True)
    tooling_apply.add_argument("--approve-user-config", action="store_true")

    tooling_bundle = subparsers.add_parser(
        "tooling-bundle",
        help="Build a checksummed offline tooling bundle from an approved plan.",
    )
    tooling_bundle.add_argument("--json", action="store_true", help="Print JSON output.")
    tooling_bundle.add_argument("--plan", type=Path, required=True)
    tooling_bundle.add_argument("--output", type=Path, required=True)

    tooling_rollback = subparsers.add_parser(
        "tooling-rollback",
        help="Remove Forge-recorded user-local tools from a receipt.",
    )
    tooling_rollback.add_argument("--json", action="store_true", help="Print JSON output.")
    tooling_rollback.add_argument("--receipt", type=Path, required=True)
    tooling_rollback.add_argument("--approve", action="store_true")

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
    apply.add_argument(
        "--approve-agent-file",
        action="append",
        choices=SUPPORTED_AGENT_FILES,
        default=[],
    )
    apply.add_argument(
        "--create-agent-file",
        action="append",
        choices=SUPPORTED_AGENT_FILES,
        default=[],
    )
    apply.add_argument("--write-install-request", action="store_true")
    apply.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)

    verify = subparsers.add_parser("verify", help="Verify an adopted Moradin sidecar.")
    verify.add_argument("--json", action="store_true", help="Print JSON output.")
    verify.add_argument("--target", type=Path, required=True)
    verify.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)

    rollback = subparsers.add_parser(
        "rollback",
        help="Remove an owned, unmodified Forge adoption after confirmation.",
    )
    rollback.add_argument("--json", action="store_true", help="Print JSON output.")
    rollback.add_argument("--target", type=Path, required=True)
    rollback.add_argument("--approve", action="store_true")
    rollback.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)

    upgrade_plan_parser = subparsers.add_parser(
        "upgrade-plan",
        help="Build a read-only transactional sidecar upgrade plan.",
    )
    upgrade_plan_parser.add_argument("--json", action="store_true", help="Print JSON output.")
    upgrade_plan_parser.add_argument("--target", type=Path, required=True)
    upgrade_plan_parser.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)

    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="Apply a digest-approved transactional sidecar upgrade.",
    )
    upgrade_parser.add_argument("--json", action="store_true", help="Print JSON output.")
    upgrade_parser.add_argument("--target", type=Path, required=True)
    upgrade_parser.add_argument("--plan", type=Path, required=True)
    upgrade_parser.add_argument("--approve-plan-sha256", required=True)
    upgrade_parser.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)

    upgrade_rollback = subparsers.add_parser(
        "upgrade-rollback",
        help="Restore the immediate Forge sidecar predecessor.",
    )
    upgrade_rollback.add_argument("--json", action="store_true", help="Print JSON output.")
    upgrade_rollback.add_argument("--target", type=Path, required=True)
    upgrade_rollback.add_argument("--upgrade-id", required=True)
    upgrade_rollback.add_argument("--approve", action="store_true")
    upgrade_rollback.add_argument("--sidecar-dir", default=DEFAULT_SIDECAR_DIR)

    context = subparsers.add_parser(
        "context-primer",
        help="Print a compact public context primer capped at 6 KiB.",
    )
    context.add_argument("--target", type=Path, required=True)

    state = subparsers.add_parser("state", help="Print compact repository state.")
    state.add_argument("--json", action="store_true", help="Print JSON output.")
    state.add_argument("--target", type=Path, required=True)

    brief = subparsers.add_parser("repo-brief", help="Print compact repository guidance.")
    brief.add_argument("--json", action="store_true", help="Print JSON output.")
    brief.add_argument("--target", type=Path, required=True)

    rerun = subparsers.add_parser(
        "rerun-advice",
        help="Advise whether to run, reuse, or investigate a command.",
    )
    rerun.add_argument("--json", action="store_true", help="Print JSON output.")
    rerun.add_argument("--target", type=Path, required=True)
    rerun.add_argument("command_argv", nargs=argparse.REMAINDER)

    checkpoint = subparsers.add_parser(
        "session-checkpoint",
        help="Record a sanitized local command outcome fingerprint.",
    )
    checkpoint.add_argument("--json", action="store_true", help="Print JSON output.")
    checkpoint.add_argument("--target", type=Path, required=True)
    checkpoint.add_argument("--outcome", choices=("pass", "fail", "skipped"), required=True)
    checkpoint.add_argument("command_argv", nargs=argparse.REMAINDER)

    diagnostic = subparsers.add_parser(
        "diagnostic-brief",
        help="Summarize local efficiency counters without raw session data.",
    )
    diagnostic.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    forge_root = args.forge_root.resolve()
    try:
        if args.command == "explain":
            print(forge_explainer())
            return 0
        if args.command == "onboard":
            def show_discovered_repositories(repositories: list[Path]) -> None:
                print(
                    "Discovered repositories within approved workspaces:",
                    file=sys.stderr,
                    flush=True,
                )
                if not repositories:
                    print("- none", file=sys.stderr, flush=True)
                for repository in repositories:
                    print(f"- {repository}", file=sys.stderr, flush=True)

            payload = build_onboard_plan(
                args.workspace,
                forge_root=forge_root,
                profile=args.profile,
                refresh_versions=args.refresh_versions,
                include_tools=args.include_tool,
                exclude_tools=args.exclude_tool,
                discovery_callback=show_discovered_repositories,
            )
            tooling_artifacts = write_tooling_plan_artifacts(
                forge_root,
                payload["tooling_plan"],
            )
            run_id = datetime.now(tz=UTC).strftime("onboard_%Y%m%dT%H%M%S%fZ")
            output_root = forge_root / CONTROL_ROOT_RELATIVE / "onboard_runs" / run_id
            write_json(output_root / "onboard_plan.json", payload)
            (output_root / "onboard_plan.md").write_text(
                tooling_plan_markdown(payload["tooling_plan"]),
                encoding="utf-8",
            )
            payload["artifacts"] = {
                "json": (output_root / "onboard_plan.json").as_posix(),
                "markdown": (output_root / "onboard_plan.md").as_posix(),
                "tooling_json": tooling_artifacts["json"],
                "tooling_markdown": tooling_artifacts["markdown"],
                "privileged_bash": tooling_artifacts["privileged_bash"],
                "privileged_bash_sha256": tooling_artifacts[
                    "privileged_bash_sha256"
                ],
                "privileged_powershell": tooling_artifacts[
                    "privileged_powershell"
                ],
                "privileged_powershell_sha256": tooling_artifacts[
                    "privileged_powershell_sha256"
                ],
            }
            print_payload(payload, args.json)
            return 0
        if args.command in {"tooling-plan", "tooling-update-plan"}:
            payload = build_tooling_plan(
                args.workspace,
                forge_root=forge_root,
                profile=args.profile,
                refresh_versions=(
                    args.refresh_versions
                    if args.command == "tooling-plan"
                    else True
                ),
                include_tools=args.include_tool,
                exclude_tools=args.exclude_tool,
            )
            payload["artifacts"] = write_tooling_plan_artifacts(
                forge_root,
                payload,
            )
            if args.json:
                print_payload(payload, True)
            else:
                print(tooling_plan_markdown(payload).rstrip())
                print(f"plan_artifact: {payload['artifacts']['markdown']}")
            return 0 if payload["status"] == "ready" else 1
        if args.command == "tooling-apply":
            payload = apply_tooling_plan(
                args.plan,
                approved_sha256=args.approve_plan_sha256,
                forge_root=forge_root,
                user_config_approved=args.approve_user_config,
            )
            print_payload(payload, args.json)
            return 0
        if args.command == "tooling-bundle":
            payload = build_offline_bundle(
                args.plan,
                output=args.output.resolve(),
            )
            print_payload(payload, args.json)
            return 0 if payload["status"] == "pass" else 1
        if args.command == "tooling-rollback":
            payload = rollback_tooling_receipt(
                args.receipt,
                approve=args.approve,
            )
            print_payload(payload, args.json)
            return 0 if payload["status"] == "pass" else 1
        if args.command == "readiness":
            target_root = args.target.resolve() if args.target else None
            readiness = detect_readiness(target_root)
            if args.write_install_request or readiness["missing_required"] or readiness["missing_optional"]:
                readiness["install_request"] = write_install_request_artifacts(
                    forge_root,
                    readiness,
                    target_root=target_root,
                )
                readiness["tooling_plan"] = write_gap_tooling_plan(
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
            if (
                args.write_install_request
                or plan["readiness"]["missing_required"]
                or plan["readiness"]["missing_optional"]
            ):
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
                    agent_files=tuple(args.approve_agent_file),
                    create_agent_files=tuple(args.create_agent_file),
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
        if args.command == "rollback":
            result = rollback_integration(
                args.target,
                approve=args.approve,
                sidecar_dir=args.sidecar_dir,
            )
            print_payload(result, args.json)
            return 0
        if args.command == "upgrade-plan":
            payload = build_upgrade_plan(
                forge_root,
                args.target,
                args.sidecar_dir,
            )
            payload["artifacts"] = write_upgrade_plan_artifacts(forge_root, payload)
            if args.json:
                print_payload(payload, True)
            else:
                print(upgrade_plan_markdown(payload).rstrip())
                print(f"plan_artifact: {payload['artifacts']['markdown']}")
            return 0
        if args.command == "upgrade":
            payload = upgrade_integration(
                forge_root,
                args.target,
                plan_path=args.plan,
                approved_sha256=args.approve_plan_sha256,
                sidecar_dir=args.sidecar_dir,
            )
            print_payload(payload, args.json)
            return 0
        if args.command == "upgrade-rollback":
            payload = rollback_upgrade(
                args.target,
                upgrade_id=args.upgrade_id,
                approve=args.approve,
                sidecar_dir=args.sidecar_dir,
            )
            print_payload(payload, args.json)
            return 0
        if args.command == "context-primer":
            print(
                context_primer(
                    args.target.resolve(),
                    runtime_root=forge_root,
                ).rstrip()
            )
            return 0
        if args.command == "state":
            print_payload(compact_repo_state(args.target), args.json)
            return 0
        if args.command == "repo-brief":
            print_payload(repo_brief(args.target), args.json)
            return 0
        if args.command == "rerun-advice":
            command_argv = list(args.command_argv)
            if command_argv[:1] == ["--"]:
                command_argv = command_argv[1:]
            payload = rerun_advice(
                args.target.resolve(),
                command_argv,
                runtime_root=forge_root,
            )
            print_payload(payload, args.json)
            return 0
        if args.command == "session-checkpoint":
            command_argv = list(args.command_argv)
            if command_argv[:1] == ["--"]:
                command_argv = command_argv[1:]
            payload = session_checkpoint(
                args.target.resolve(),
                command_argv,
                args.outcome,
                runtime_root=forge_root,
            )
            print_payload(payload, args.json)
            return 0
        if args.command == "diagnostic-brief":
            print_payload(diagnostic_brief(runtime_root=forge_root), args.json)
            return 0
    except (ForgeError, WorkstationError) as error:
        print(f"moradin-forge: {error}")
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
