---
title: "Agent Harness Governance"
status: approved
owner: platform-operations
last_reviewed: 2026-02-24
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - ../engineer_entry/index.md
  - codex_run_loop.md
  - change_tracking_system.md
  - upgrades.md
  - ../15_checklists/agent_cycle_gate.md
  - ../15_checklists/capability_gap_review.md
  - Harness/artifacts/control/changelog.md
  - Harness/artifacts/control/current_features.md
  - Harness/artifacts/control/current_guidance.md
  - Harness/artifacts/control/loop_processes.md
  - Harness/artifacts/control/capability_gap_register.md
  - docs/exec_plans/tech-debt-tracker.md
---

# Agent Harness Governance

## Purpose

- Define enforceable governance for planner and implementer cycles in this repository.
- Ensure every discovered capability gap becomes both legible in docs and enforceable in controls.

## Governance Policy

- Agents run one approved cycle at a time.
- A human must explicitly approve continuation to the next cycle.
- Cycle continuation approval must be recorded in changelog fields before cycle `N+1`.
- Any contract, security, or boundary uncertainty triggers a mandatory stop.
- `docs/00_overview/engineer_entrypoint.md` plus non-index `docs/engineer_entry/**/*.md` are human-owned context; agents may read but must not write them.
- `docs/engineer_entry/index.md` is generated navigation and must stay synchronized with the engineer-entry tree summary.
- Every cycle must answer: "What capability is missing, and how do we make it both legible and enforceable for the agent?" unless reviewer-approved skip is explicit.
- Behavior changes are incomplete until docs, rules, and checklists are synchronized.

## Capability Gap Loop

1. Detect missing capability or unclear enforcement point.
2. Log gap in `Harness/artifacts/control/capability_gap_register.md`.
3. Evaluate with `../15_checklists/capability_gap_review.md`.
4. Define a legibility artifact (docs, ADR, glossary, prompt template, or runbook update).
5. Define an enforcement artifact (lint, contract rule, CI gate, checklist gate, or stop condition).
6. Assign owner and closure evidence.
7. Close only after objective evidence is attached.
8. Route pending capability ideas to `docs/exec_plans/implementation/active/` before upgrade-gate triage.

## Post-Gate Harness Upgrade Policy

- After every human review gate, triage harness and tooling improvements.
- Record each candidate in `docs/exec_plans/tech-debt-tracker.md`.
- Human reviewer must route each candidate as `upgrade_next_cycle`, `defer_with_risk`, or `reject`.
- Items routed to `upgrade_next_cycle` are executed before the next feature cycle.

## Required Artifacts Per Cycle

- Plan artifact path with phase and stage target.
- Command evidence (`make lint`, tests, compatibility output).
- Docs and rules sync evidence or explicit no-change rationale.
- Updated `Harness/artifacts/control/changelog.md` row for the cycle.
- Updated `Harness/artifacts/control/current_features.md` when capabilities changed.
- Updated `Harness/artifacts/control/current_guidance.md` when guidance changed.
- Updated `Harness/artifacts/control/loop_processes.md` when process semantics changed.
- Updated loop state and capability gap status.
- Updated `docs/exec_plans/tech-debt-tracker.md` status.
- Explicit continue, pause, or stop decision by human reviewer.

## Enforcement Mechanisms

- Checklist gate in `../15_checklists/agent_cycle_gate.md`.
- Gap closure checklist in `../15_checklists/capability_gap_review.md`.
- Change tracking contract in `change_tracking_system.md`.
- Engineer-entry guard script: `npm --prefix dev_tracker/ui run check:engineer-entry`.
- Loop-state update contract in `Harness/artifacts/control/loop_state.md`.
- Harness upgrade routing contract in `docs/exec_plans/tech-debt-tracker.md`.
- CI quality gates (`make lint`, `make lint-md`) before merge.

## Verification Checklist

- [ ] Every cycle has scope, evidence, and decision trail.
- [ ] Engineer-entry context was loaded and no agent write occurred in `docs/engineer_entry/`.
- [ ] Changelog approval state blocks or allows continuation correctly.
- [ ] Capability gaps are tracked to closure with owners.
- [ ] Docs and rules stay synchronized with behavior changes.
- [ ] Harness upgrade candidates are routed after every human gate.
- [ ] No unattended loop continuation occurs.

## Related Docs

- ../engineer_entry/index.md
- codex_run_loop.md
- change_tracking_system.md
- upgrades.md
- ../15_checklists/agent_cycle_gate.md
- ../15_checklists/capability_gap_review.md
- Harness/artifacts/control/changelog.md
- Harness/artifacts/control/current_features.md
- Harness/artifacts/control/current_guidance.md
- Harness/artifacts/control/loop_processes.md
- Harness/artifacts/control/capability_gap_register.md
- docs/exec_plans/tech-debt-tracker.md
