#!/usr/bin/env python3
"""Build and audit sanitized public Moradin Forge exports."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "moradin-forge-public-export"
PUBLIC_AUDIT_DIRNAME = "public_audit"
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

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".mk",
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

SKIP_DIR_NAMES = {
    ".git",
    ".harness_devops",
    ".harness_template",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vite",
    "__pycache__",
    "dist",
    "node_modules",
    "public_audit",
    "public_exports",
    "ui_audit",
    "ui_phase5_audit",
    "wheels",
}

SKIP_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".tsbuildinfo",
}

SKIP_FILE_PREFIXES = {
    ".codex_pr_body_",
}

EXPORT_SKIP_PREFIXES = {
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

EXPORT_SKIP_EXACT = {
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
    "main.py",
    "scripts/check_branch_hygiene.py",
    "scripts/run_alignment_proof.py",
    "scripts/run_builder_beta_smoke.py",
    "scripts/run_live_adoption_release.py",
    f"scripts/run_{PR_HARDENING_TOKEN}.py",
    "scripts/run_seed_generation_release.py",
    "scripts/start_cycle_branch.py",
    "scripts/start_moradin_migration.py",
    "scripts/validate_release_report_artifacts.py",
    "tests/contracts/test_docs_integrity.py",
    "tests/contracts/test_docs_path_compatibility.py",
    "tests/scripts/test_alignment_proof.py",
    "tests/scripts/test_branch_hygiene.py",
    "tests/scripts/test_builder_beta_smoke.py",
    "tests/scripts/test_live_adoption_release.py",
    "tests/scripts/test_manage_harness_template.py",
    f"tests/scripts/test_run_{PR_HARDENING_TOKEN}.py",
    "tests/scripts/test_seed_generation_release.py",
    "tests/scripts/test_start_cycle_branch.py",
    "tests/scripts/test_start_moradin_migration.py",
    "tests/scripts/test_validate_release_report_artifacts.py",
}

EXPORT_SKIP_PREFIXES.update(
    {
        "Harness/artifacts/control/forge_runs",
        "Harness/artifacts/control/efficiency",
        "Harness/artifacts/control/install_requests",
        "Harness/artifacts/control/migration_start",
        "Harness/artifacts/control/migration_waves",
        f"Harness/artifacts/control/{PR_HARDENING_TOKEN}",
        "Harness/artifacts/control/public_export",
        "Harness/artifacts/control/repo_registry",
        "Harness/artifacts/control/onboard_runs",
        "Harness/artifacts/control/tooling_plans",
        "Harness/artifacts/control/tooling_receipts",
        "Harness/artifacts/control/upgrade_runs",
        "Harness/artifacts/control/discovery_sessions",
        "testing_suite",
        "tests/testing_suite",
    }
)

PUBLIC_MAKEFILE_TEXT = """\
.PHONY: lint-py lint-md test test-py ui-test ui-build payload-validate payload-smoke template-validate template-smoke forge-explain forge-readiness forge-brief forge-onboard forge-tooling-plan forge-tooling-update-plan forge-tooling-apply forge-tooling-bundle forge-tooling-rollback forge-plan forge-adopt-dry-run forge-adopt forge-verify forge-upgrade-plan forge-upgrade forge-upgrade-rollback forge-rollback forge-smoke public-export public-portability-check

PUBLIC_EXPORT_DIR ?= /tmp/moradin-forge-public-export-check
PUBLIC_SIDECAR_SMOKE_DIR ?= /tmp/moradin-forge-sidecar-smoke-check
WORKSPACE ?=
PLAN ?=
PLAN_SHA256 ?=
OUTPUT ?=
RECEIPT ?=
AGENT_FILES ?=
CREATE_AGENT_FILES ?=
UPGRADE_ID ?=

lint-py:
\tUV_CACHE_DIR=/tmp/uv-cache uv run ruff check .

lint-md:
\tUV_CACHE_DIR=/tmp/uv-cache uv run pymarkdownlnt --enable-extensions front-matter --disable-rules "*" --enable-rules md022 scan --recurse --exclude .git --exclude .venv --exclude node_modules --exclude dist .

test-py:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run pytest

test: test-py

ui-test:
\tnpm --prefix dev_tracker/ui run test

ui-build:
\tnpm --prefix dev_tracker/ui run build

payload-validate:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py validate

payload-smoke:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py smoke-test

template-validate: payload-validate

template-smoke: payload-smoke

forge-explain forge-brief:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py explain

forge-readiness:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py readiness

forge-onboard:
\t@if [ -z "$(WORKSPACE)" ]; then echo "Usage: make forge-onboard WORKSPACE=<workspace-path>"; exit 1; fi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py onboard --workspace "$(WORKSPACE)"

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

forge-plan forge-adopt-dry-run:
\t@if [ -z "$(TARGET)" ]; then \\
\t\techo "Usage: make $@ TARGET=<repo-path>"; \\
\t\texit 1; \\
\tfi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py plan --target "$(TARGET)" --write-install-request

forge-adopt:
\t@if [ -z "$(TARGET)" ] || [ "$(APPROVE)" != "1" ]; then \\
\t\techo "Usage: make forge-adopt TARGET=<repo-path> APPROVE=1 [AGENT_FILES='AGENTS.md CLAUDE.md']"; \\
\t\texit 1; \\
\tfi
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/moradin_forge.py apply --target "$(TARGET)" --approve $(if $(OVERWRITE),--overwrite-sidecar,) $(if $(PATCH_AGENTS),--patch-agents,) $(foreach file,$(AGENT_FILES),--approve-agent-file $(file)) $(foreach file,$(CREATE_AGENT_FILES),--create-agent-file $(file)) --write-install-request

forge-verify:
\t@if [ -z "$(TARGET)" ]; then \\
\t\techo "Usage: make forge-verify TARGET=<repo-path>"; \\
\t\texit 1; \\
\tfi
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
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py sidecar-smoke --output "$(PUBLIC_SIDECAR_SMOKE_DIR)" --force

public-export:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py export --output "$(PUBLIC_EXPORT_DIR)" --force --init-git

public-portability-check:
\tPYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/public_export.py check --output "$(PUBLIC_EXPORT_DIR)" --sidecar-output "$(PUBLIC_SIDECAR_SMOKE_DIR)" --force --init-git
"""

PUBLIC_FILE_OVERRIDES: dict[str, str] = {
    "Makefile": PUBLIC_MAKEFILE_TEXT,
    "Harness/artifacts/control/current_guidance.md": """\
---
title: "Moradin Forge Public Guidance"
status: public-contract
owner: moradin-forge
---

# Moradin Forge Public Guidance

## Agent Rules

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

## Current State

- `canonical_payload`: `Harness/moradin_payload/manifest.yaml`
- `sidecar_default_dir`: `.moradins-harness`
- `legacy_aliases_enabled`: true
- `compatibility_scope`: legacy aliases are sanitizer-only compatibility
  history; first-read docs use Moradin payload names.
- `removal_gate`: one public compatibility window after downstream users have
  moved to Moradin payload commands.

Compatibility aliases exist only to keep early adopters stable while public
Forge commands become canonical.
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

PUBLIC_WORKBENCH_STUBS: dict[str, str] = {
    "Harness/artifacts/control/loop_state.md": """\
---
title: "Public Workbench Loop State"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Loop State

## Current State

- `run_count`: 0

## Cycle History

| run_id | status | notes |
| --- | --- | --- |
""",
    "Harness/artifacts/control/capability_gap_register.md": """\
---
title: "Public Workbench Capability Gap Register"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Capability Gap Register

## Register Table

| gap_id | opened_on | status | class | owner | enforcement_target | evidence_link |
| --- | --- | --- | --- | --- | --- | --- |
""",
    "Harness/artifacts/control/loop_processes.md": """\
---
title: "Public Workbench Loop Processes"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Loop Processes

## Process Table

| process_id | process_type | trigger | steps_summary | required_artifacts | human_gate | next_cycle_rule |
| --- | --- | --- | --- | --- | --- | --- |
""",
    "Harness/artifacts/control/human_gate_stats.md": """\
---
title: "Public Workbench Human Gate Stats"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Human Gate Stats

## Human Gate Stats Table

| gate_id | date | cycle_id | loop_id | cycles_completed | estimated_cycles_remaining | estimated_loops_remaining | stages_remaining | pending_approvals | pending_features | open_capability_gaps | open_harness_upgrades | completion_percent | next_cycle_type | reviewer_action_required | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| public-0 | 2026-05-11 | public | public | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none | none | Public export placeholder. |
""",
    "Harness/artifacts/control/archive_register.md": """\
---
title: "Public Workbench Archive Register"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Archive Register

## Archive Register Table

| archive_id | archived_on | record_type | source_cycle | title | status | archive_path | upgrade_review | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
""",
    "Harness/artifacts/control/documentation_review_status.md": """\
---
title: "Public Workbench Documentation Review Status"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Documentation Review Status

- status: pass
- reason: public export placeholder
""",
    "Harness/artifacts/reports/repo_skill_registry.md": """\
---
title: "Public Workbench Repo Skill Registry"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Repo Skill Registry

No repo-local skill registry is bundled with the public export.
""",
    "docs/exec_plans/index.md": """\
---
title: "Public Workbench Execution Plans"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Execution Plans

The public export does not bundle local execution history.
""",
    "docs/exec_plans/updates/active/index.md": """\
---
title: "Public Workbench Active Updates"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Active Updates
""",
    "docs/exec_plans/upgrades/active/index.md": """\
---
title: "Public Workbench Active Upgrades"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Active Upgrades
""",
    "docs/exec_plans/tooling/active/index.md": """\
---
title: "Public Workbench Active Tooling"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Active Tooling
""",
    "docs/exec_plans/implementation/active/index.md": """\
---
title: "Public Workbench Active Implementation"
status: public-placeholder
owner: moradin-forge
---

# Public Workbench Active Implementation
""",
}

FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
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

SANITIZE_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
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


@dataclass(frozen=True)
class ScanHit:
    path: str
    pattern: str
    line: int
    excerpt: str


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def as_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_text_path(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in TEXT_FILENAMES


def is_binary_or_unreadable(path: Path) -> bool:
    if not is_text_path(path):
        return True
    try:
        sample = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\x00" in sample


def sanitize_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in SANITIZE_REPLACEMENTS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def origin_marker_patterns() -> list[tuple[str, re.Pattern[str]]]:
    markers: set[str] = set()
    for key in ("USER", "USERNAME", "LOGNAME"):
        marker = os.environ.get(key, "").strip()
        if marker:
            markers.add(marker)
    hostname = socket.gethostname().strip()
    if hostname:
        markers.add(hostname)
        markers.add(hostname.split(".", 1)[0])
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
    return [*FORBIDDEN_PATTERNS, *origin_marker_patterns()]


def sanitize_public_text(relative: str, text: str) -> str:
    sanitized = sanitize_text(text)
    if relative != ".gitignore":
        return sanitized

    trailing_newline = sanitized.endswith("\n")
    lines = [
        "/artifacts/" if line.strip() == "artifacts/" else line
        for line in sanitized.splitlines()
    ]
    return "\n".join(lines) + ("\n" if trailing_newline else "")


def should_skip_relative(relative: str, is_dir: bool) -> bool:
    parts = relative.split("/")
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    if not is_dir and LEGACY_DISCOVERY_DOC_RE.match(relative):
        return True
    if not is_dir and any(Path(relative).name.startswith(prefix) for prefix in SKIP_FILE_PREFIXES):
        return True
    if not is_dir and any(relative.endswith(suffix) for suffix in SKIP_FILE_SUFFIXES):
        return True
    if relative in EXPORT_SKIP_EXACT:
        return True
    return any(
        relative == prefix or relative.startswith(f"{prefix}/")
        for prefix in EXPORT_SKIP_PREFIXES
    )


def copy_sanitized_file(relative: str, source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if is_binary_or_unreadable(source):
        shutil.copy2(source, destination)
        return
    text = source.read_text(encoding="utf-8")
    destination.write_text(sanitize_public_text(relative, text), encoding="utf-8")
    shutil.copystat(source, destination)


def write_public_file_override(relative: str, source: Path, destination: Path) -> bool:
    content = PUBLIC_FILE_OVERRIDES.get(relative)
    if content is None:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    shutil.copystat(source, destination)
    return True


def copy_public_tree(source_root: Path, export_root: Path) -> list[str]:
    copied: list[str] = []
    for root, dirnames, filenames in os.walk(source_root):
        root_path = Path(root)
        relative_root = "" if root_path == source_root else as_relative(root_path, source_root)
        dirnames[:] = [
            dirname
            for dirname in sorted(dirnames)
            if not should_skip_relative(
                f"{relative_root}/{dirname}".strip("/"),
                is_dir=True,
            )
        ]
        for filename in sorted(filenames):
            source = root_path / filename
            relative = as_relative(source, source_root)
            if should_skip_relative(relative, is_dir=False):
                continue
            if source.is_symlink():
                continue
            destination = export_root / relative
            if not write_public_file_override(relative, source, destination):
                copy_sanitized_file(relative, source, destination)
            copied.append(relative)
    return copied


def write_public_workbench_stubs(export_root: Path) -> list[str]:
    written: list[str] = []
    for relative, content in sorted(PUBLIC_WORKBENCH_STUBS.items()):
        path = export_root / relative
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(relative)
    return written


def scan_tree(root: Path) -> list[ScanHit]:
    hits: list[ScanHit] = []
    for scan_root, dirnames, filenames in os.walk(root):
        root_path = Path(scan_root)
        relative_root = "" if root_path == root else as_relative(root_path, root)
        dirnames[:] = [
            dirname
            for dirname in sorted(dirnames)
            if dirname != ".git"
            and not should_skip_relative(
                f"{relative_root}/{dirname}".strip("/"),
                is_dir=True,
            )
        ]
        for filename in sorted(filenames):
            path = root_path / filename
            if is_binary_or_unreadable(path):
                continue
            relative = as_relative(path, root)
            if should_skip_relative(relative, is_dir=False):
                continue
            text = path.read_text(encoding="utf-8")
            for index, line in enumerate(text.splitlines(), start=1):
                for pattern_name, pattern in forbidden_patterns():
                    if pattern.search(line):
                        hits.append(
                            ScanHit(
                                path=relative,
                                pattern=pattern_name,
                                line=index,
                                excerpt=line.strip()[:180],
                            )
                        )
    return hits


def write_public_audit(root: Path, payload: dict[str, Any]) -> dict[str, str]:
    audit_root = root / PUBLIC_AUDIT_DIRNAME
    audit_root.mkdir(parents=True, exist_ok=True)
    json_path = audit_root / "portability_report.json"
    markdown_path = audit_root / "portability_report.md"
    safe_payload = json.loads(sanitize_text(json.dumps(payload)))
    json_path.write_text(
        json.dumps(safe_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sidecar_smoke_payload = safe_payload.get("sidecar_smoke", {})
    fresh_git_payload = safe_payload.get("fresh_git", {})
    lines = [
        "# Moradin Forge Public Portability Report",
        "",
        f"- generated_at: `{safe_payload['generated_at']}`",
        f"- root: `{safe_payload['root']}`",
        f"- status: `{safe_payload['status']}`",
        f"- copied_file_count: `{safe_payload.get('copied_file_count', 0)}`",
        f"- forbidden_hit_count: `{len(safe_payload['forbidden_hits'])}`",
        f"- sidecar_smoke: `{sidecar_smoke_payload.get('status', 'not_run')}`",
        f"- fresh_git_commit_count: `{fresh_git_payload.get('commit_count', 'not_initialized')}`",
        "",
    ]
    if safe_payload["forbidden_hits"]:
        lines.append("## Forbidden Hits")
        lines.append("")
        for hit in safe_payload["forbidden_hits"][:50]:
            lines.append(
                f"- `{hit['path']}:{hit['line']}` `{hit['pattern']}` {hit['excerpt']}"
            )
    markdown_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"json": json_path.as_posix(), "markdown": markdown_path.as_posix()}


def export_roots(copied_files: list[str]) -> list[str]:
    return sorted({relative.split("/", 1)[0] for relative in copied_files if relative})


def exclusion_summary() -> dict[str, Any]:
    return {
        "skip_dir_names": sorted(SKIP_DIR_NAMES),
        "skip_file_prefixes": sorted(SKIP_FILE_PREFIXES),
        "skip_file_suffixes": sorted(SKIP_FILE_SUFFIXES),
        "export_skip_exact": sorted(EXPORT_SKIP_EXACT),
        "export_skip_prefixes": sorted(EXPORT_SKIP_PREFIXES),
    }


def write_export_manifest(root: Path, payload: dict[str, Any]) -> dict[str, str]:
    audit_root = root / PUBLIC_AUDIT_DIRNAME
    audit_root.mkdir(parents=True, exist_ok=True)
    json_path = audit_root / "export_manifest.json"
    markdown_path = audit_root / "export_manifest.md"
    safe_payload = json.loads(sanitize_text(json.dumps(payload)))
    json_path.write_text(
        json.dumps(safe_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sidecar_smoke_payload = safe_payload.get("sidecar_smoke", {})
    fresh_git_payload = safe_payload.get("fresh_git", {})
    lines = [
        "# Moradin Forge Public Export Manifest",
        "",
        f"- generated_at: `{safe_payload['generated_at']}`",
        f"- status: `{safe_payload['status']}`",
        f"- copied_file_count: `{safe_payload.get('copied_file_count', 0)}`",
        f"- included_roots: `{', '.join(safe_payload.get('included_roots', []))}`",
        f"- excluded_rule_count: `{safe_payload.get('excluded_rule_count', 0)}`",
        f"- forbidden_hit_count: `{len(safe_payload.get('forbidden_hits', []))}`",
        f"- sidecar_smoke: `{sidecar_smoke_payload.get('status', 'not_run')}`",
        f"- fresh_git_commit_count: `{fresh_git_payload.get('commit_count', 'not_initialized')}`",
        "",
    ]
    markdown_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"json": json_path.as_posix(), "markdown": markdown_path.as_posix()}


def init_fresh_git_repo(export_root: Path) -> dict[str, Any]:
    if not shutil.which("git"):
        return {"initialized": False, "reason": "git not found"}
    commands = [
        ["git", "init", "-b", "main"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Moradin Forge Export",
            "-c",
            "user.email=forge-export@example.invalid",
            "commit",
            "-m",
            "Initial public Moradin Forge export",
        ],
    ]
    for command in commands:
        subprocess.run(command, cwd=export_root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    commit_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=export_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
    return {"initialized": True, "commit_count": int(commit_count)}


def export_public_tree(
    source_root: Path,
    export_root: Path,
    *,
    force: bool = False,
    init_git: bool = False,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    export_root = export_root.resolve()
    if export_root == source_root or source_root in export_root.parents:
        raise ValueError("export root must be outside the source repo")
    if export_root.exists():
        if not force:
            raise FileExistsError(f"export root already exists: {export_root}")
        shutil.rmtree(export_root)
    export_root.mkdir(parents=True)
    copied_files = copy_public_tree(source_root, export_root)
    generated_stub_files = write_public_workbench_stubs(export_root)
    copied_files.extend(generated_stub_files)
    hits = scan_tree(export_root)
    payload: dict[str, Any] = {
        "version": "MoradinPublicExportReportV1",
        "generated_at": utc_now(),
        "root": export_root.as_posix(),
        "source_root": "<forge-root>",
        "copied_file_count": len(copied_files),
        "included_roots": export_roots(copied_files),
        "generated_public_stubs": generated_stub_files,
        "excluded_rules": exclusion_summary(),
        "excluded_rule_count": (
            len(SKIP_DIR_NAMES)
            + len(SKIP_FILE_PREFIXES)
            + len(SKIP_FILE_SUFFIXES)
            + len(EXPORT_SKIP_EXACT)
            + len(EXPORT_SKIP_PREFIXES)
        ),
        "forbidden_hits": [hit.__dict__ for hit in hits],
        "status": "pass" if not hits else "fail",
        "fresh_git": {"initialized": False},
    }
    if init_git and shutil.which("git"):
        payload["fresh_git"] = {"initialized": True, "commit_count": 1}
        payload["audit"] = write_public_audit(export_root, payload)
        payload["manifest"] = write_export_manifest(export_root, payload)
        payload["fresh_git"] = init_fresh_git_repo(export_root)
    else:
        if init_git:
            payload["fresh_git"] = {"initialized": False, "reason": "git not found"}
        payload["audit"] = write_public_audit(export_root, payload)
        payload["manifest"] = write_export_manifest(export_root, payload)
    return payload


def scan_public_root(root: Path) -> dict[str, Any]:
    root = root.resolve()
    hits = scan_tree(root)
    payload: dict[str, Any] = {
        "version": "MoradinPublicPortabilityScanV1",
        "generated_at": utc_now(),
        "root": root.as_posix(),
        "forbidden_hits": [hit.__dict__ for hit in hits],
        "status": "pass" if not hits else "fail",
    }
    payload["audit"] = write_public_audit(root, payload)
    return payload


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_sidecar_smoke_target(target_root: Path) -> None:
    write_text(target_root / "AGENTS.md", "# Target Agent Notes\n\nKeep existing rules.\n")
    write_text(target_root / "Makefile", "verify:\n\ttrue\n")
    write_text(
        target_root / "package.json",
        json.dumps({"scripts": {"test": "node --test"}}, indent=2) + "\n",
    )
    write_text(target_root / "pyproject.toml", "[project]\nname = \"target\"\nversion = \"0.0.0\"\n")
    write_text(target_root / "go.mod", "module example.com/target\n\ngo 1.23\n")
    write_text(target_root / "Dockerfile", "FROM scratch\n")
    write_text(target_root / ".github/workflows/ci.yml", "name: ci\non: [push]\njobs: {}\n")


def sidecar_smoke(source_root: Path, output_root: Path, *, force: bool = False) -> dict[str, Any]:
    from scripts.moradin_forge import ForgeApplyOptions, apply_integration, verify_integration

    output_root = output_root.resolve()
    if output_root.exists():
        if not force:
            raise FileExistsError(f"sidecar smoke root already exists: {output_root}")
        shutil.rmtree(output_root)
    target_root = output_root / "target"
    write_sidecar_smoke_target(target_root)
    original_agents = (target_root / "AGENTS.md").read_text(encoding="utf-8")
    original_makefile = (target_root / "Makefile").read_text(encoding="utf-8")
    result = apply_integration(
        source_root.resolve(),
        target_root,
        ForgeApplyOptions(approve=True, patch_agents=False),
    )
    sidecar_root = target_root / ".moradins-harness"
    hits = scan_tree(sidecar_root)
    root_mutations = []
    if (target_root / "AGENTS.md").read_text(encoding="utf-8") != original_agents:
        root_mutations.append("AGENTS.md")
    if (target_root / "Makefile").read_text(encoding="utf-8") != original_makefile:
        root_mutations.append("Makefile")
    verification = verify_integration(target_root)
    payload: dict[str, Any] = {
        "version": "MoradinPublicSidecarSmokeV1",
        "generated_at": utc_now(),
        "root": sidecar_root.as_posix(),
        "apply_result": sanitize_text(json.dumps(result, sort_keys=True)),
        "verify_result": verification,
        "forbidden_hits": [hit.__dict__ for hit in hits],
        "root_mutations": root_mutations,
        "status": "pass" if not hits and not root_mutations and verification["status"] == "pass" else "fail",
    }
    payload["audit"] = write_public_audit(sidecar_root, payload)
    return payload


def check_public_export(
    source_root: Path,
    export_root: Path,
    sidecar_output_root: Path,
    *,
    force: bool = False,
    init_git: bool = False,
) -> dict[str, Any]:
    payload = export_public_tree(
        source_root,
        export_root,
        force=force,
        init_git=False,
    )
    sidecar_payload = sidecar_smoke(source_root, sidecar_output_root, force=force)
    payload["sidecar_smoke"] = {
        "status": sidecar_payload["status"],
        "root": sidecar_payload["root"],
        "forbidden_hit_count": len(sidecar_payload["forbidden_hits"]),
        "root_mutations": sidecar_payload["root_mutations"],
        "audit": sidecar_payload.get("audit", {}),
    }
    if payload["status"] != "pass" or sidecar_payload["status"] != "pass":
        payload["status"] = "fail"
    if init_git and shutil.which("git"):
        payload["fresh_git"] = {"initialized": True, "commit_count": 1}
        payload["audit"] = write_public_audit(export_root, payload)
        payload["manifest"] = write_export_manifest(export_root, payload)
        payload["fresh_git"] = init_fresh_git_repo(export_root)
    else:
        if init_git:
            payload["fresh_git"] = {"initialized": False, "reason": "git not found"}
        payload["audit"] = write_public_audit(export_root, payload)
        payload["manifest"] = write_export_manifest(export_root, payload)
    return payload


def print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload['status']}")
    print(f"root: {payload['root']}")
    print(f"forbidden_hits: {len(payload['forbidden_hits'])}")
    if "copied_file_count" in payload:
        print(f"copied_file_count: {payload['copied_file_count']}")
    if payload.get("sidecar_smoke"):
        print(f"sidecar_smoke: {payload['sidecar_smoke']['status']}")
    if payload.get("audit"):
        print(f"audit: {payload['audit']['markdown']}")
    if payload.get("manifest"):
        print(f"manifest: {payload['manifest']['markdown']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and audit public Moradin Forge exports.")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export", help="Write a sanitized public export tree.")
    export.add_argument("--output", type=Path, default=DEFAULT_EXPORT_DIR)
    export.add_argument("--force", action="store_true")
    export.add_argument("--init-git", action="store_true")
    export.add_argument("--json", action="store_true")

    scan = subparsers.add_parser("scan", help="Scan an existing tree for host-specific references.")
    scan.add_argument("--root", type=Path, required=True)
    scan.add_argument("--json", action="store_true")

    sidecar = subparsers.add_parser(
        "sidecar-smoke",
        help="Generate a disposable sidecar and scan it for public portability.",
    )
    sidecar.add_argument("--output", type=Path, required=True)
    sidecar.add_argument("--force", action="store_true")
    sidecar.add_argument("--json", action="store_true")

    check = subparsers.add_parser(
        "check",
        help="Create a public export, run sidecar smoke, and write combined audit manifests.",
    )
    check.add_argument("--output", type=Path, default=DEFAULT_EXPORT_DIR)
    check.add_argument("--sidecar-output", type=Path, required=True)
    check.add_argument("--force", action="store_true")
    check.add_argument("--init-git", action="store_true")
    check.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "export":
            payload = export_public_tree(
                args.source_root,
                args.output,
                force=args.force,
                init_git=args.init_git,
            )
            print_payload(payload, args.json)
            return 0 if payload["status"] == "pass" else 1
        if args.command == "scan":
            payload = scan_public_root(args.root)
            print_payload(payload, args.json)
            return 0 if payload["status"] == "pass" else 1
        if args.command == "sidecar-smoke":
            payload = sidecar_smoke(args.source_root, args.output, force=args.force)
            print_payload(payload, args.json)
            return 0 if payload["status"] == "pass" else 1
        if args.command == "check":
            payload = check_public_export(
                args.source_root,
                args.output,
                args.sidecar_output,
                force=args.force,
                init_git=args.init_git,
            )
            print_payload(payload, args.json)
            return 0 if payload["status"] == "pass" else 1
    except (FileExistsError, ValueError, subprocess.CalledProcessError) as error:
        print(f"public-export: {error}")
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
