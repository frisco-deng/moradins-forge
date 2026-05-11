---
title: "Task Routing"
status: approved
owner: platform-operations
last_reviewed: 2026-02-24
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
  - https://medium.com/@DataDo/building-production-grade-agentic-rag-a-technical-deep-dive-part-1-beyond-fixed-windows-9879cf3cc7b1
related_docs:
  - index.md
  - ../00_overview/engineer_entrypoint.md
  - ../11_ops/codex_run_loop.md
  - ../11_ops/change_tracking_system.md
  - ../11_ops/archive_process.md
  - ../11_ops/git_workflow_gitlab.md
  - Harness/artifacts/control/archive_register.md
  - Harness/artifacts/control/changelog.md
  - Harness/artifacts/control/human_gate_stats.md
  - docs/exec_plans/tech-debt-tracker.md
---

# Task Routing

## Purpose

- Provide an enforceable pre-flight and post-flight gate for this workflow.

## Checklist

- [ ] Classify request type (contract, service, retrieval, ingestion, ops, security, harness).
- [ ] Route to mandatory docs and checklist artifacts before editing.
- [ ] Confirm explicit phase, stage, and cycle scope.
- [ ] Prefer the shortest repo-native command path (`make`, `uv run`, `npm --prefix`, `rg`, `mv`) before inventing longer manual sequences.
- [ ] Escalate to ADR when boundary or long-lived design changes are required.
- [ ] Confirm human approver for multi-cycle work.
- [ ] Confirm post-gate harness triage owner and report target.
- [ ] Confirm changelog and tracking report owner for cycle closeout.

## Evidence Required

- Command or CI output links for lint, test, and compatibility checks.
- Updated doc links and contract references where applicable.
- Explicit human decision (`continue`, `pause`, or `stop`).
- Explicit changelog approval state and approval reference.
- Human gate quick stats entry with remaining-cycle and remaining-loop estimates.
- Archive register row for cycle-created archive records.
- Harness routing decision (`upgrade_next_cycle`, `defer_with_risk`, or `reject`).

## Verification Checklist

- [ ] Checklist items are specific, testable, and owner-assigned.
- [ ] Required artifacts are linked and current.
- [ ] Escalation path is clear when a gate fails.
- [ ] Harness routing evidence exists for closed cycles.
- [ ] Changelog approval evidence exists before cycle continuation.
- [ ] Human gate stats evidence exists before cycle continuation.
- [ ] Archive register evidence exists before cycle continuation.

## Related Docs

- index.md
- ../00_overview/engineer_entrypoint.md
- ../11_ops/codex_run_loop.md
- ../11_ops/change_tracking_system.md
- ../11_ops/archive_process.md
- ../11_ops/git_workflow_gitlab.md
- Harness/artifacts/control/archive_register.md
- Harness/artifacts/control/changelog.md
- Harness/artifacts/control/human_gate_stats.md
- docs/exec_plans/tech-debt-tracker.md
