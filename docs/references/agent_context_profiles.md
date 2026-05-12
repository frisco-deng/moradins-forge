---
title: "Agent Context Profiles"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-12
source_refs:
  - ../../AGENTS.md
  - ../../README.md
  - ../../FORGE.md
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
  - moradin_forge_public_export_contract_v1.md
  - repo_operating_model_v1.md
---

# Agent Context Profiles

## Purpose

Give coding agents a compact load order for common Forge work. Start with the
smallest profile that fits the task, then load deeper contracts only when a
decision or validation step requires them.

## Adoption Profile

Use when applying Forge to another repo.

Read:

- `README.md`
- `FORGE.md`
- `AGENTS.md`
- `Harness/entrypoints/forge.md`
- `Harness/moradin_payload/manifest.yaml`
- `docs/references/moradin_forge_agent_integration_contract_v1.md`

Run:

- `make forge-explain`
- `make forge-readiness`
- `make forge-plan TARGET=<target-repo>`

Stop before `make forge-adopt` until the user explicitly approves the target
repo writes.

## Forge Development Profile

Use when changing Forge behavior or tests.

Read:

- `AGENTS.md`
- `FORGE.md`
- `Harness/entrypoints/agent.md`
- `docs/references/repo_operating_model_v1.md`
- The script, UI, test, or doc files directly touched by the task

Run the shortest relevant local gate first, then expand to the public gates
when behavior, payload, or release surfaces change.

## Public Release Profile

Use before public PRs, public exports, or release tags.

Read:

- `docs/references/repo_operating_model_v1.md`
- `docs/references/moradin_forge_public_export_contract_v1.md`
- `docs/references/moradin_payload_contract_v1.md`
- `Harness/moradin_payload/manifest.yaml`

Run:

- `make test`
- `make payload-validate`
- `make payload-smoke`
- `make forge-smoke`
- `make public-portability-check`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
- `npm --prefix dev_tracker/ui audit --audit-level=moderate`

## UI Diagnostics Profile

Use when reviewing the optional workbench or control API.

Read:

- `README.md`
- `docs/00_overview/architecture.md`
- `docs/11_ops/project_builder_runbook.md`
- `dev_tracker/ui/package.json`
- The affected UI page, loader, script, and tests

Run:

- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`

## Improvement Notes

- Strength: Forge already gives agents deterministic entrypoints, consent
  boundaries, sidecar writes, and public portability gates.
- Gap: agents can still over-read because the repo includes docs, payload,
  scripts, tests, and an optional UI in one export.
- Gap: validation commands should avoid mutating tracked governance files unless
  a command explicitly requests that side effect.
- Next enhancement: keep task profiles current as new command surfaces are added
  and prefer profile-specific first reads over broad repository scans.
