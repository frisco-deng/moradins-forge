---
title: "Assistant Handoff Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-05-08
source_refs:
  - dev_tracker/ui/scripts/control-api.mjs
  - FORGE.md
  - scripts/moradin_forge.py
related_docs:
  - tooling_readiness_install_request_contract_v1.md
  - moradin_forge_agent_integration_contract_v1.md
  - moradin_forge_public_export_contract_v1.md
  - project_builder_prompt_catalog.md
---

# Assistant Handoff Contract V1

## Purpose

Moradin prepares compact, reviewable handoff artifacts for Codex CLI, Codex App
manual paste flows, Claude Code CLI, and Moradin's Forge agent-first adoption.

## Supported Modes

- `codex_cli`
- `codex_app_manual_handoff`
- `claude_code`
- `moradin_forge_agent`
- `manual_handoff`

## Handoff Rules

- Prompt bundles and follow-on prompts are artifacts before execution.
- CLI execution remains explicit and operator-triggered.
- Codex App mode is manual: copy the prompt artifact into the app and paste the
  resulting changes back through the normal repo workflow.
- Assistant run artifacts stay under `Harness/artifacts/control/assistant_runs/`.
- Assistant runs do not create a host-tool install path.
- Forge agent mode must read `FORGE.md` and `Harness/entrypoints/forge.md`,
  explain target-repo changes, and require explicit consent before running
  `scripts/moradin_forge.* apply`.

## Token Reduction Rules

Assistants should prefer:

- repo registry summaries
- builder, adoption, release, and onboarding briefs
- Forge dry-run plans under `Harness/artifacts/control/forge_runs/`
- project scan artifacts
- phase plans and alignment state

Avoid re-reading large generated artifact directories unless the user asks for
release proof details.
