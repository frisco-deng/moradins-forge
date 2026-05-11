---
title: "Upgrades"
status: approved
owner: platform-architecture
last_reviewed: 2026-03-02
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
  - https://medium.com/@DataDo/building-production-grade-agentic-rag-a-technical-deep-dive-part-1-beyond-fixed-windows-9879cf3cc7b1
related_docs:
  - index.md
  - ../00_overview/engineer_entrypoint.md
  - docs/exec_plans/index.md
  - docs/exec_plans/implementation/active/index.md
  - docs/exec_plans/upgrades/active/index.md
  - change_tracking_system.md
  - archive_process.md
  - codex_run_loop.md
  - Harness/artifacts/control/archive_register.md
  - Harness/artifacts/control/changelog.md
  - Harness/artifacts/control/current_guidance.md
  - Harness/artifacts/control/loop_processes.md
  - docs/exec_plans/tech-debt-tracker.md
  - Harness/artifacts/control/human_gate_stats.md
---

# Upgrades

## Purpose

- Define runbooks and environment controls for safe, repeatable operations.
- Define a deterministic harness-upgrade loop executed after human review gates.
- This document defines executable expectations for `upgrades`.

## Scope

- In scope: decisions, interfaces, risks, and checks that can be validated.
- Out of scope: speculative implementation detail without contract or runbook impact.

## Topic Decisions

- Upgrade procedures include compatibility checks and rollback criteria.
- Operational procedures require deterministic command evidence.
- Run-loop governance enforces one-cycle execution and human continuation gates.
- Recovery and rollback plans are required for all production-impacting changes.
- Harness and tooling upgrades are triaged after every human review gate.

## Harness Upgrade Loop Contract

1. Post-cycle, review missing capabilities in tooling, prompts, docs, and governance.
2. Record suggestion candidates in `docs/exec_plans/implementation/active/` and summary rows in `docs/exec_plans/tech-debt-tracker.md`.
3. Human routes each candidate as `upgrade_next_cycle`, `defer_with_risk`, or `reject`.
4. For commissioned upgrades, move routed suggestion records to `docs/exec_plans/implementation/completed/`.
5. Execute `upgrade_next_cycle` items before starting feature cycle `N+1`.
6. Attach deterministic evidence and update changelog, guidance, loop-process, human-gate stats, and archive-register reports.
7. Require explicit human approval in changelog before feature cycle continuation.

## Interfaces / Dependencies

- Upgrade interfaces define preconditions and post-upgrade validation.
- Ops artifacts coordinate deployment, upgrades, and incident execution.
- Ops decisions are validated by checklists and generated run reports.
- Harness upgrade routing depends on cycle gate and loop-state artifacts.
- Upgrade completion depends on changelog approval and current guidance synchronization.

## Failure Modes / Risks

- Unsafe upgrades can cause partial service failure.
- Runbook drift causes inconsistent operator response.
- Cycle execution can bypass harness improvements without post-gate triage.

## Verification Checklist

- [ ] Upgrade runbooks include staged rollout checkpoints.
- [ ] Runbook steps are deterministic and operator-ready.
- [ ] Escalation and rollback paths are explicit.
- [ ] Loop governance dependencies are linked and current.
- [ ] Tech-debt tracker is updated after each human review gate.
- [ ] Human gate stats are updated with remaining-cycle and remaining-loop estimates.
- [ ] Upgrade review outcomes are archived and present in archive register.
- [ ] Changelog approval state is updated before resuming feature cycles.

## Related Docs

- index.md
- ../00_overview/engineer_entrypoint.md
- docs/exec_plans/index.md
- docs/exec_plans/implementation/active/index.md
- docs/exec_plans/upgrades/active/index.md
- change_tracking_system.md
- archive_process.md
- codex_run_loop.md
- Harness/artifacts/control/archive_register.md
- Harness/artifacts/control/changelog.md
- Harness/artifacts/control/current_guidance.md
- Harness/artifacts/control/loop_processes.md
- docs/exec_plans/tech-debt-tracker.md
- Harness/artifacts/control/human_gate_stats.md
