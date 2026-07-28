---
title: "Moradin Payload Contract V1"
status: approved
owner: platform-architecture
last_reviewed: 2026-06-10
source_refs:
  - Harness/moradin_payload/manifest.yaml
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
  - tooling_readiness_install_request_contract_v1.md
  - repo_registry_adapter_contract_v1.md
  - ../11_ops/project_builder_runbook.md
---

# Moradin Payload Contract V1

## Purpose

The Moradin payload is the canonical deployable kit used by new-project generation
and existing-project sidecar adoption. Moradin's Forge uses the same payload
manifest for agent-first local adoption.

## Source Of Truth

- Manifest: `Harness/moradin_payload/manifest.yaml`
- Kind: `moradin_payload`
- Payload id: `moradin_harness_payload`
- Default sidecar directory: `.moradins-harness`
- Compatibility scaffold: `.harness_template/`
- Agent-first entrypoint: `FORGE.md`
- Bootstrap entrypoints: `install/bootstrap-linux.sh`,
  `install/bootstrap-macos.sh`, and `install/bootstrap-windows.ps1`

The compatibility scaffold remains available for one beta release window, but primary
UI routes, docs, and commands use Moradin payload language.

## Copy Rules

- `include_paths` is the allowlist for payload materialization.
- `exclude_paths` removes Forge-only, generated, or volatile paths from any
  included directory.
- New-project generation and existing-project sidecar deploy must use the same
  manifest.
- Forge native scripts must use the same manifest for sidecar materialization.
- Bootstrap scripts and `scripts/forge_bootstrap.py` are included so a copied
  sidecar can explain or prime Forge from the same contract surface.
- Symlinks are rejected during payload copy.
- Generated local evidence is not copied downstream.

## Compatibility Aliases

- Canonical script: `scripts/manage_moradin_payload.py`
- Legacy script alias: `scripts/manage_harness_template.py`
- Canonical targets: `make payload-validate`, `make payload-smoke`
- Legacy target aliases: `make template-validate`, `make template-smoke`
- Canonical route: `/payload`
- Legacy route: `/template` redirects to `/payload`
