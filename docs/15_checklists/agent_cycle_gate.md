---
title: "Agent Cycle Gate"
status: approved
owner: platform-operations
last_reviewed: 2026-03-22
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - ../11_ops/codex_run_loop.md
  - ../11_ops/agent_harness_governance.md
  - ../11_ops/change_tracking_system.md
  - ../11_ops/archive_process.md
  - ../11_ops/upgrades.md
  - Harness/artifacts/control/archive_register.md
  - Harness/artifacts/control/changelog.md
  - Harness/artifacts/control/current_features.md
  - Harness/artifacts/control/current_guidance.md
  - Harness/artifacts/control/loop_processes.md
  - Harness/artifacts/control/human_gate_stats.md
  - Harness/artifacts/control/loop_state.md
  - Harness/artifacts/control/compatibility_window_status.md
  - docs/exec_plans/tech-debt-tracker.md
  - capability_gap_review.md
---

# Agent Cycle Gate

## Purpose

- Enforce pre-run and post-run controls for each planner-to-implementer cycle.

## Pre-Run Gate

- [ ] Approved plan artifact path is recorded.
- [ ] Cycle mapping is explicit: `phase_id`, `stage_id`, and `cycle_id`.
- [ ] Scope and acceptance criteria are unchanged.
- [ ] Prompt template or request text includes gate pause instruction.
- [ ] Required deterministic commands are listed.
- [ ] Expected docs, rules, and ADR updates are listed.
- [ ] Planned changelog entry and tracking report updates are listed.
- [ ] Reviewer assigned for post-run decision.

## Post-Run Gate

- [ ] Diff reviewed against approved scope.
- [ ] Lint, test, and compatibility evidence captured.
- [ ] Branch hygiene and engineer-entry guard checks passed.
- [ ] Feature branch is pushed and routed to `dev`, not `main`.
- [ ] Docs and rules updates completed, or explicit no-change rationale documented.
- [ ] ADR impact reviewed and documented.
- [ ] Changelog row appended for current cycle.
- [ ] Changelog approval fields updated (`human_gate_decision`, `approval_ref`, `approval_status`).
- [ ] Current features report updated or explicitly marked unchanged.
- [ ] Current guidance report updated or explicitly marked unchanged.
- [ ] Loop processes report updated or explicitly marked unchanged.
- [ ] Human gate stats report updated with estimated cycles and loops remaining.
- [ ] Archive register updated for cycle-produced archive records.
- [ ] Compatibility-window status updated when migration window is active.
- [ ] Loop state report updated.
- [ ] Capability gaps logged or explicitly marked none.
- [ ] Tech-debt tracker updated or explicitly marked none.
- [ ] Update, upgrade, and tooling review artifacts updated when generated in-cycle.
- [ ] Final capability-gap question answered or explicit reviewer-approved skip recorded.
- [ ] Human continue, pause, or stop decision captured.
- [ ] Human harness routing decision captured: `upgrade_next_cycle`, `defer_with_risk`, or `reject`.
- [ ] Human signoff requirement for `dev -> main` is recorded when promotion is in scope.

## Stop Conditions

- [ ] Contract ambiguity or incompatible schema drift.
- [ ] Security uncertainty or policy enforcement gap.
- [ ] Failed quality gates without approved exception.
- [ ] Behavior changed but docs or rules are not updated.
- [ ] Changelog row missing for cycle closeout.
- [ ] Changelog approval state not `approved` for cycle continuation.
- [ ] Human gate stats row missing for cycle closeout.
- [ ] Archive register row missing for cycle-produced archive records.
- [ ] Missing harness upgrade routing decision after cycle close.
- [ ] Feature work targets `main` instead of `dev`.
- [ ] Branch hygiene or engineer-entry guard check failed.
- [ ] Missing update, upgrade, or tooling review artifact updates for review-scoped cycle.
- [ ] Missing final capability-gap question answer without reviewer-approved skip.
- [ ] Missing human reviewer decision.

## Related Docs

- ../11_ops/codex_run_loop.md
- ../11_ops/agent_harness_governance.md
- ../11_ops/change_tracking_system.md
- ../11_ops/archive_process.md
- ../11_ops/upgrades.md
- Harness/artifacts/control/archive_register.md
- Harness/artifacts/control/changelog.md
- Harness/artifacts/control/current_features.md
- Harness/artifacts/control/current_guidance.md
- Harness/artifacts/control/loop_processes.md
- Harness/artifacts/control/human_gate_stats.md
- Harness/artifacts/control/loop_state.md
- Harness/artifacts/control/compatibility_window_status.md
- docs/exec_plans/tech-debt-tracker.md
- capability_gap_review.md
