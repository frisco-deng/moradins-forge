---
title: "Architecture Overview"
status: approved
owner: platform-architecture
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - implementation_phases.md
  - service_catalog.md
  - ../03_architecture/index.md
---

# Architecture

## Goals

- Preserve deterministic harness governance and quality gate execution.
- Provide a local Builder control plane that can create/import/generate project repos safely.
- Keep discovery synthesis optional-LLM with deterministic fallback.

## Core Surfaces

- Tracker UI (`dev_tracker/ui`) for observability and builder operations.
- Control API (`dev_tracker/ui/scripts/control-api.mjs`) for local orchestration endpoints.
- Governance docs under `Harness/artifacts/control/` and `docs/exec_plans/`.

## Non-Goals

- No automatic execution endpoint after synthesis generation.
- No implicit branch/routing bypass for cycle closeout.
