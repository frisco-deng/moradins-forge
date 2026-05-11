---
title: "Change Tracking System"
status: approved
owner: platform-operations
last_reviewed: 2026-03-02
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - tooling_pipeline.md
  - codex_run_loop.md
  - agent_harness_governance.md
  - archive_process.md
  - upgrades.md
  - ../15_checklists/agent_cycle_gate.md
  - Harness/artifacts/control/archive_register.md
  - Harness/artifacts/control/changelog.md
  - Harness/artifacts/control/current_features.md
  - Harness/artifacts/control/current_guidance.md
  - Harness/artifacts/control/loop_processes.md
  - Harness/artifacts/control/human_gate_stats.md
  - Harness/artifacts/control/compatibility_window_status.md
---

# Change Tracking System

## Purpose

- Define the canonical human-readable tracking system for cycle history, current capability, guidance, and loop execution processes.
- Enforce approval visibility before advancing from cycle `N` to cycle `N+1`.

## Tracking Artifacts

- `Harness/artifacts/control/changelog.md`: append-only cycle ledger and human approval status.
- `Harness/artifacts/control/current_features.md`: current capability inventory and phase linkage.
- `Harness/artifacts/control/current_guidance.md`: active operator and agent guidance with enforcement anchors.
- `Harness/artifacts/control/loop_processes.md`: implementation and upgrade loop process definitions.
- `Harness/artifacts/control/human_gate_stats.md`: per-gate quick stats with estimated cycles and loops remaining.
- `Harness/artifacts/control/archive_register.md`: archive row ledger for suggestions, updates, and upgrade reviews.
- `Harness/artifacts/control/compatibility_window_status.md`: compatibility-window telemetry and closeout readiness.

## Required Update Contract Per Cycle

1. Append one changelog row for the cycle.
2. Record human gate decision and approval reference when reviewer decision is final.
3. Update current features if delivered capability changed.
4. Update current guidance if policy or prompt behavior changed.
5. Update loop processes if implementation or upgrade semantics changed.
6. Append one human gate stats row with estimated cycles and loops remaining.
7. Append archive register rows for new archived update/upgrade/suggestion records.
8. Record update, upgrade, and tooling review artifacts when those reviews are part of the cycle scope.
9. If `docs/engineer_entry/` changed, run engineer-entry guard and frontmatter validation before continuation.
10. During migration windows, update compatibility-window status with current slot and blockers.

## Approval Gate Contract

- Cycle `N+1` is blocked until cycle `N` changelog entry is `approval_status: approved`.
- `approval_ref` must be present for approved decisions.
- Allowed `human_gate_decision` values: `continue`, `pause`, `stop`, `pending`.
- Cycle `N+1` is blocked if `human_gate_stats.md` is missing a row for cycle `N`.

## Failure Modes

- Missing changelog update causes loss of traceability.
- Missing approval reference breaks cycle-gate enforcement.
- Drift between current guidance and `AGENTS.md` causes execution ambiguity.
- Missing gate stats row hides remaining-cycle estimates and weakens reviewer decisions.
- Missing archive register rows break historical traceability for updates/upgrades.
- Engineer-entry changes without frontmatter validation create ambiguous operator context.
- Agent-side writes in engineer-entry folder overwrite human source-of-truth guidance.

## Engineer-Entry Documentation/Lint Trigger

- Trigger: any detected change under `docs/engineer_entry/`.
- Required checks:
- `make lint-md`
- `npm --prefix dev_tracker/ui run check:engineer-entry`
- Optional full pass for handoff: `npm --prefix dev_tracker/ui run qa:pass`
- Continuation is blocked until these checks pass.

## Verification Checklist

- [ ] Changelog has one row per completed cycle.
- [ ] Approval status and approval reference are present before cycle continuation.
- [ ] Features, guidance, and loop-process reports are synchronized with latest cycle outputs.
- [ ] Human gate stats row exists and includes cycle/loop remaining estimates.
- [ ] Archive register rows exist for newly created archive records.
- [ ] Compatibility-window status is updated when a migration window is active.
- [ ] Agent gate and run-loop docs reference this tracking system.

## Related Docs

- tooling_pipeline.md
- codex_run_loop.md
- agent_harness_governance.md
- archive_process.md
- upgrades.md
- ../15_checklists/agent_cycle_gate.md
- Harness/artifacts/control/archive_register.md
- Harness/artifacts/control/changelog.md
- Harness/artifacts/control/current_features.md
- Harness/artifacts/control/current_guidance.md
- Harness/artifacts/control/loop_processes.md
- Harness/artifacts/control/human_gate_stats.md
- Harness/artifacts/control/compatibility_window_status.md
