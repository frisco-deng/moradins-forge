---
title: "Moradin Forge Installer Bootstrap Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-06-09
source_refs:
  - ../../scripts/forge_bootstrap.py
  - ../../install/bootstrap-linux.sh
  - ../../install/bootstrap-macos.sh
  - ../../install/bootstrap-windows.ps1
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
  - tooling_readiness_install_request_contract_v1.md
  - moradin_forge_public_export_contract_v1.md
---

# Moradin Forge Installer Bootstrap Contract V1

## Purpose

The installer bootstrap path lets a user clone or prime Forge with a small,
agent-readable start card before an agent spends tokens rediscovering the repo.
Bootstrap is not adoption: it must not install host tools, patch a target repo,
or run Forge `apply`.

## Entrypoints

- Linux or WSL: `install/bootstrap-linux.sh`
- macOS: `install/bootstrap-macos.sh`
- Windows PowerShell: `install/bootstrap-windows.ps1`
- Shared core: `scripts/forge_bootstrap.py`

All entrypoints support the same public options:

- repo URL, defaulting to `https://github.com/frisco-deng/moradins-forge.git`
- ref, defaulting to `main`
- destination Forge checkout
- optional target repo placeholder
- dependency mode: `none`, `minimal`, or `full`
- dry-run mode
- JSON output

## Behavior

- Existing in-place Forge checkouts are reused and not force-switched.
- External destinations are cloned or updated with `git` when present.
- `minimal` dependency mode uses `uv sync --group dev` only when `uv` is
  already available.
- `full` mode additionally runs UI dependency priming only when `npm` and the UI
  package manifest are present.
- Missing tools are reported as request-only manual actions.

## Start Card

Successful non-dry-run bootstrap writes:

- `artifacts/bootstrap/latest/agent_start.json`
- `artifacts/bootstrap/latest/agent_start.md`

The start card uses placeholders such as `<forge-root>` and `<target-repo>`.
It must not contain raw home paths, temp paths, hostnames, usernames, SSH clone
URLs, Codex session paths, or target repo content.

## Safety Rules

- Bootstrap never executes `sudo`, `brew`, `winget`, shell profile edits,
  credential rewrites, or global Git configuration changes.
- Bootstrap never runs `scripts/moradin_forge.* apply`.
- Bootstrap never edits a target repo.
- Bootstrap artifacts stay under ignored `artifacts/` and are excluded from
  public exports and sidecar payloads.
