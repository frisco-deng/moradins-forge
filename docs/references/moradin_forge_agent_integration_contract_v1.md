---
title: "Moradin Forge Agent Integration Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-05-08
source_refs:
  - FORGE.md
  - Harness/entrypoints/forge.md
  - Harness/entrypoints/forge_agent_handoff.md
  - scripts/moradin_forge.py
related_docs:
  - moradin_payload_contract_v1.md
  - moradin_forge_public_export_contract_v1.md
  - tooling_readiness_install_request_contract_v1.md
  - assistant_handoff_contract_v1.md
---

# Moradin Forge Agent Integration Contract V1

## Purpose

Moradin's Forge is the agent-first local adoption path. A user can send Codex,
Claude Code, or another agent to this repo; the agent reads the Forge
entrypoints, explains the integration, asks for consent, then applies Moradin
locally through deterministic scripts.

## Integration Flow

1. Explain: `scripts/moradin_forge.sh explain` or
   `.\scripts\moradin_forge.ps1 explain`.
2. Readiness check: `scripts/moradin_forge.sh readiness --target <target-repo>`.
3. Dry-run plan: `scripts/moradin_forge.sh plan --target <target-repo>`.
4. Human review: user reviews proposed writes, readiness gaps, and rollback.
5. Apply after consent: `scripts/moradin_forge.sh apply --target <target-repo>
   --approve`.
6. Verify: `scripts/moradin_forge.sh verify --target <target-repo>`.

## Write Boundary

Forge may write only:

- the target repo's `.moradins-harness/` sidecar,
- adapter snippets under `.moradins-harness/adapters/`,
- install-request artifacts under `Harness/artifacts/control/install_requests/`,
- Forge run artifacts under `Harness/artifacts/control/forge_runs/`,
- a marked Moradin block in an existing target `AGENTS.md` only when
  `--patch-agents` is explicitly approved.

`verify` must report missing sidecar files, copied manager artifacts, forbidden
private references, and mismatches between recorded adapter status and the
target `AGENTS.md` marker.

Forge must not execute host install commands, publish repo contents, edit
private source tooling, or overwrite an existing sidecar without an explicit
overwrite flag.

## Platform Entrypoints

- Linux/macOS: `scripts/moradin_forge.sh`
- Windows PowerShell: `scripts/moradin_forge.ps1`
- Core implementation: `scripts/moradin_forge.py`

The native wrappers choose `uv` when available and fall back to a local Python 3
interpreter. Missing tools are reported through request-only readiness artifacts.

## Rollback

Remove `.moradins-harness/` from the target repo. If Forge patched root
`AGENTS.md`, remove the block bounded by `moradin-forge:start` and
`moradin-forge:end`. No host tool install rollback is needed because Forge does
not run host installs.
