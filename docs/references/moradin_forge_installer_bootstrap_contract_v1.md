---
title: "Moradin Forge Installer Bootstrap Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/forge_bootstrap.py
  - ../../install/bootstrap-linux.sh
  - ../../install/bootstrap-macos.sh
  - ../../install/bootstrap-windows.ps1
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
  - tooling_readiness_install_execution_contract_v2.md
  - moradin_forge_public_export_contract_v1.md
---

# Moradin Forge Installer Bootstrap Contract V1

## Purpose

Bootstrap clones or primes Forge and creates a small agent-readable start card
before an agent spends context rediscovering the repository. Bootstrap is not
adoption and never runs Forge `apply`.

## Entrypoints

- Linux or WSL: `install/bootstrap-linux.sh`
- macOS: `install/bootstrap-macos.sh`
- Windows PowerShell: `install/bootstrap-windows.ps1`
- Shared core: `scripts/forge_bootstrap.py`

The shared core accepts repository URL, ref, destination, optional target,
dependency mode, dry-run mode, and JSON output. Existing in-place checkouts are
reused rather than force-switched.

## Runtime-Prerequisite Bridge

When Python 3 is present, bootstrap may prime dependencies already supported by
the host. It does not install new host tools.

When Python 3 is absent, the native wrapper generates a reviewable prerequisite
script under `artifacts/bootstrap/latest/`:

- Linux emits Bash that requires the user to invoke `sudo ... --apply`;
- macOS emits a user-run Homebrew script;
- Windows emits PowerShell for a user-approved session.

The wrapper exits without running the generated installer. Dry-run is the
script default, reversal guidance is printed, and the user must provide the
explicit apply flag. Elevation is checked only after the dry run so the script
can be reviewed without privilege.

## Start Card

Successful non-dry-run bootstrap writes:

- `artifacts/bootstrap/latest/agent_start.json`
- `artifacts/bootstrap/latest/agent_start.md`

The card uses placeholders and excludes raw home paths, temp paths, hostnames,
usernames, SSH clone URLs, session paths, and target repository content.

## Safety Rules

- Bootstrap never invokes `sudo` or elevation.
- Bootstrap never edits a target repository.
- Bootstrap never runs Forge adoption or tooling apply.
- PATH, credentials, and global Git configuration remain untouched.
- Generated artifacts are ignored and excluded from public exports and
  sidecar payloads.

## Full Connected Tooling Suite

`install/tooling-suite.sh`, `install/tooling-suite-macos.sh`, and
`install/tooling-suite.ps1` are separate human-run workstation installers, not
bootstrap. They use the V2 contract. Linux may request sudo after an exact plan
review and digest confirmation; Windows emits a reviewable elevated script for
the human. This exception does not permit bootstrap or an agent to invoke
elevation. Complete air-gap operations remain Linux-only.
