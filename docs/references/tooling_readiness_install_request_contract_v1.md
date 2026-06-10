---
title: "Tooling Readiness And Install Request Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-06-09
source_refs:
  - dev_tracker/ui/scripts/control-api.mjs
  - scripts/moradin_forge.py
  - scripts/forge_bootstrap.py
related_docs:
  - moradin_payload_contract_v1.md
  - moradin_forge_agent_integration_contract_v1.md
  - assistant_handoff_contract_v1.md
---

# Tooling Readiness And Install Request Contract V1

## Purpose

Moradin checks host tooling before deploy work and writes install request
artifacts for human review. Moradin does not execute host install commands from
the UI or from native Forge scripts.

## API

- `GET /api/moradin/readiness`
- `POST /api/moradin/install-request`
- `scripts/moradin_forge.sh readiness`
- `scripts/moradin_forge.ps1 readiness`
- `install/bootstrap-linux.sh`
- `install/bootstrap-macos.sh`
- `install/bootstrap-windows.ps1`

## Readiness Checks

Readiness checks cover:

- host baseline: `git`, `uv`, `node`, `npm`
- assistant handoff modes: Codex CLI, Codex App manual handoff, Claude Code CLI
- shell and bridge surfaces: `tpldeck`, `uvbootstrap`, `codex-run`,
  `codex-docker`, `codex-exec`
- optional scanners: `gitleaks`, `trivy`, `actionlint`, `zizmor`, `conftest`,
  `yamllint`

Each check records `present`, `missing`, or `manual`, plus any human-run install
commands and verification command.

Bootstrap readiness uses the same request-only model but keeps output smaller:
it requires `git` plus a Python 3 launcher, treats `uv`, `node`, and `npm` as
optional priming tools, and writes sanitized agent start-card guidance instead
of running host installation commands.

## Install Request Artifacts

Requests are written under:

`Harness/artifacts/control/install_requests/<request_id>/`

Each request includes:

- `install_request.json`
- `install_request.md`
- selected tool ids
- request-only safety text
- human-run commands when Moradin knows a stable command
- runbook references for environment-specific installs

## Safety Rules

- UI actions create artifacts only.
- Native Forge scripts create artifacts only for install gaps.
- Install commands must be reviewed and run by a human in a shell they control.
- Missing optional scanner or bridge tools must not block payload validation.
- Missing required baseline tools should block deploy work until resolved.
- Bootstrap must not execute `sudo`, `brew`, `winget`, shell profile edits,
  credential rewrites, global Git config changes, or Forge `apply`.
