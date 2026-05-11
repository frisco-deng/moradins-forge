---
title: "Codex Run Loop"
status: approved
owner: platform-operations
last_reviewed: 2026-03-22
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - ../engineer_entry/index.md
  - ../00_overview/implementation_phases.md
  - change_tracking_system.md
  - archive_process.md
  - ../15_checklists/agent_cycle_gate.md
  - documentation_review_loop.md
  - ../15_checklists/documentation_review_gate.md
  - upgrades.md
  - agent_harness_governance.md
  - Harness/artifacts/control/archive_register.md
  - Harness/artifacts/control/changelog.md
  - Harness/artifacts/control/current_features.md
  - Harness/artifacts/control/current_guidance.md
  - Harness/artifacts/control/loop_processes.md
  - Harness/artifacts/control/human_gate_stats.md
  - Harness/artifacts/control/loop_state.md
  - Harness/artifacts/control/capability_gap_register.md
  - Harness/artifacts/control/documentation_review_status.md
  - Harness/artifacts/control/compatibility_window_status.md
  - docs/exec_plans/tech-debt-tracker.md
---

# Codex Run Loop

## Purpose

- Define a planner-to-implementer execution loop with mandatory human checkpoints and capability-gap enforcement.
- Ensure cycle, stage, and phase state remains legible in docs and enforceable in checklists.
- Route harness and tooling improvements through a deterministic post-gate upgrade process.

## Lexicon Contract

- `phase`: top-level delivery tranche in `../00_overview/implementation_phases.md`.
- `stage`: bounded implementation checkpoint inside a phase.
- `cycle`: one approved planner-to-implementer execution pass.
- `loop`: the sequence of cycles that progresses an objective.
- Every cycle report must include `phase_id`, `stage_id`, and `cycle_id`.

## Cycle Contract

1. Planner produces decision-complete plan artifact with `phase_id`, `stage_id`, and scope boundary.
2. Implementer creates one scoped cycle branch before editing:
3. `make branch-start PHASE=<n> STAGE=<n> SCOPE=<scope> [PREFIX=harness] [CYCLE_ID=<id>]`
4. Implementer keeps `main` clean and synced; cycle branches route to `dev`, not `main`.
5. Implementer executes exactly one approved cycle.
6. Implementer records deterministic command evidence and residual risks.
7. Implementer updates impacted docs and rules when behavior, policy, or stage status changes.
8. Implementer runs branch and engineer-entry guard checks before cycle closeout:
9. `make branch-hygiene` and `npm --prefix dev_tracker/ui run check:engineer-entry`.
10. Implementer runs suggestion pass and writes pending items under `docs/exec_plans/implementation/active/` when missing capabilities are discovered.
11. Implementer updates cycle tracking reports in `Harness/artifacts/control/`:
12. `changelog.md`, `current_features.md`, `current_guidance.md`, and `loop_processes.md`.
13. Implementer appends `human_gate_stats.md` with estimated cycles and loops remaining at cycle closeout.
14. Implementer archives update and upgrade outcomes and appends `archive_register.md`.
15. Implementer updates loop state and capability gap register as required.
16. Implementer updates `docs/exec_plans/tech-debt-tracker.md` with tooling and harness improvement routing.
17. Implementer answers: "What capability is missing, and how do we make it both legible and enforceable for the agent?" unless reviewer explicitly approves skip.
18. Human reviewer records explicit `continue`, `pause`, or `stop` decision.
19. If `continue`, human reviewer records harness routing decision: `upgrade_next_cycle`, `defer_with_risk`, or `reject`.
20. Reviewer updates changelog approval fields (`human_gate_decision`, `approval_ref`, `approval_status`).
21. Human reviewer approves `dev -> main` promotion separately after integrated review is complete.
22. Every 3 completed cycles, run the documentation review loop and apply risk-based blocking for critical drift.

## Phase Transition Contract

1. Associate each cycle with one phase from `../00_overview/implementation_phases.md`.
2. Associate each cycle with one target stage inside that phase.
3. Do not advance phase status until all phase exit criteria are satisfied.
4. Record phase and stage transition evidence in plan artifact and loop-state notes.
5. Ensure docs and rules are synchronized before marking stage or phase transitions.
6. Human reviewer must approve every phase transition explicitly.

## Mandatory Human Gate

- No automatic transition from cycle `N` to cycle `N+1`.
- Unresolved contract or security ambiguity forces stop.
- Capability gaps must be logged before continuation.
- Missing docs or rules synchronization forces stop.
- Any attempted write in `docs/engineer_entry/` forces stop (engineer-owned context folder).
- Missing changelog entry for cycle `N` forces stop.
- Changelog `approval_status` other than `approved` for cycle `N` forces stop.
- Missing human-gate stats entry for cycle `N` forces stop.
- Missing archive register entry for cycle `N` update or upgrade records forces stop.
- Missing harness routing decision after cycle close forces stop.
- Feature work routed directly to `main` forces stop.
- Branch hygiene or engineer-entry guard failure forces stop.

## Post-Human-Gate Harness Upgrade Triage

1. Review prior cycle outputs for missing tooling, prompt, docs, or governance enforcement.
2. Log each candidate in `docs/exec_plans/tech-debt-tracker.md`.
3. Human reviewer chooses routing for each open candidate.
4. Routing values: `upgrade_next_cycle`, `defer_with_risk`, or `reject`.
5. If routed to `upgrade_next_cycle`, run a dedicated harness-upgrade cycle before feature cycle `N+1`.
6. Record routing decision in the plan artifact and loop-state notes.

## Required Artifacts Per Cycle

- Plan file reference with `phase_id`, `stage_id`, and `cycle_id`.
- Diff and deterministic command evidence summary.
- Docs and rules update list, or explicit "no docs/rules change" note.
- Branch hygiene evidence and engineer-entry guard result.
- Update, upgrade, and tooling review artifacts when generated in-cycle.
- `Harness/artifacts/control/changelog.md` update.
- `Harness/artifacts/control/current_features.md` update when feature state changed.
- `Harness/artifacts/control/current_guidance.md` update when policy or prompt guidance changed.
- `Harness/artifacts/control/loop_processes.md` update when loop semantics changed.
- `Harness/artifacts/control/human_gate_stats.md` update with estimated cycles/loops remaining.
- `Harness/artifacts/control/archive_register.md` update for archive records created in cycle.
- `Harness/artifacts/control/loop_state.md` update.
- `Harness/artifacts/control/capability_gap_register.md` update when needed.
- `docs/exec_plans/tech-debt-tracker.md` update.
- `npm --prefix dev_tracker/ui run check:engineer-entry` result for frontmatter and write-guard enforcement.
- `Harness/artifacts/control/compatibility_window_status.md` update when compatibility migration window is active.

## Stop Conditions

- Failed lint, test, or compatibility checks.
- Failed engineer-entry guard check.
- Boundary, policy, or contract uncertainty.
- Behavior changed but docs or rules were not updated.
- Tracking reports were not updated for cycle closeout.
- Missing or non-approved changelog approval state for the last cycle.
- Missing human-gate quick stats report update for the last cycle.
- Missing archive register update for cycle-produced archive records.
- Harness improvement candidates were not triaged and recorded.
- Missing capability-gap legibility/enforcement answer.
- Missing reviewer approval.

## Verification Checklist

- [ ] Exactly one cycle executed per approval.
- [ ] Cycle records phase, stage, and cycle mapping.
- [ ] Engineer-entry folder was used as context input and not modified by agent.
- [ ] Changelog row exists for the cycle and has approval state.
- [ ] Loop-state report updated.
- [ ] Capability gaps captured and assigned.
- [ ] Docs and rules changes are synchronized with behavior changes.
- [ ] Current features, guidance, and loop-process reports are synchronized.
- [ ] Human gate stats report includes estimated cycles and loops remaining.
- [ ] Archive register includes cycle-produced archive records.
- [ ] Harness upgrade routing decision recorded.
- [ ] Human continuation decision recorded.

## Related Docs

- ../engineer_entry/index.md
- ../00_overview/implementation_phases.md
- change_tracking_system.md
- archive_process.md
- ../15_checklists/agent_cycle_gate.md
- documentation_review_loop.md
- ../15_checklists/documentation_review_gate.md
- upgrades.md
- agent_harness_governance.md
- Harness/artifacts/control/archive_register.md
- Harness/artifacts/control/changelog.md
- Harness/artifacts/control/current_features.md
- Harness/artifacts/control/current_guidance.md
- Harness/artifacts/control/loop_processes.md
- Harness/artifacts/control/human_gate_stats.md
- Harness/artifacts/control/loop_state.md
- Harness/artifacts/control/capability_gap_register.md
- Harness/artifacts/control/documentation_review_status.md
- Harness/artifacts/control/compatibility_window_status.md
- docs/exec_plans/tech-debt-tracker.md
