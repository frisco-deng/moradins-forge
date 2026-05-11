---
title: "Documentation Review Loop"
status: approved
owner: docs-build-pipeline
last_reviewed: 2026-03-02
source_refs: []
related_docs:
  - codex_run_loop.md
  - change_tracking_system.md
  - ../15_checklists/documentation_review_gate.md
  - Harness/artifacts/control/documentation_review_status.md
  - Harness/artifacts/control/loop_processes.md
  - docs/exec_plans/tooling/active/index.md
  - docs/exec_plans/tech-debt-tracker.md
---

# Documentation Review Loop

## Purpose

- Run a scheduled parallel documentation review routine outside the standard implementation loop.
- Prevent contract, security, and gate-rule drift while preserving feature-cycle throughput.

## Cadence

- Execute once every 3 completed cycles.

## Review Routine

1. Load canonical control artifacts from `Harness/artifacts/control/`.
2. Compare contracts, runbooks, and checklists against current behavior and enforcement scripts.
3. Classify findings as `critical` or `non_critical`.
4. Block cycle continuation only for `critical` findings.
5. Route `non_critical` findings into `docs/exec_plans/tooling/active/` and `docs/exec_plans/tech-debt-tracker.md`.
6. Update `Harness/artifacts/control/documentation_review_status.md` with last review and next due cycle.

## Critical Blocking Classes

- contract drift
- security drift
- human-gate enforcement drift
- canonical path breakage

## Non-Critical Routing Classes

- wording/clarity drift
- stale related-doc references that do not break gates
- informational tracker/help-panel drift

## Related Docs

- codex_run_loop.md
- change_tracking_system.md
- ../15_checklists/documentation_review_gate.md
- Harness/artifacts/control/documentation_review_status.md
- Harness/artifacts/control/loop_processes.md
- docs/exec_plans/tooling/active/index.md
- docs/exec_plans/tech-debt-tracker.md
