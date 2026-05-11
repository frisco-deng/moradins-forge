---
title: "Change Control"
status: approved
owner: platform-operations
last_reviewed: 2026-02-23
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
  - https://medium.com/@DataDo/building-production-grade-agentic-rag-a-technical-deep-dive-part-1-beyond-fixed-windows-9879cf3cc7b1
related_docs:
  - index.md
  - ../00_overview/engineer_entrypoint.md
  - ../11_ops/codex_run_loop.md
  - ../11_ops/git_workflow_gitlab.md
---

# Change Control

## Purpose

- Provide an enforceable pre-flight and post-flight gate for this workflow.

## Checklist

- [ ] Link approved plan and implementation scope.
- [ ] Link quality-gate evidence (`make lint`, test output, compatibility reports).
- [ ] Confirm release owner, reviewer, and rollback owner.
- [ ] Record explicit go/no-go decision.

## Evidence Required

- Command or CI output links for lint/test/compatibility checks.
- Updated doc links and contract references where applicable.
- Explicit human decision (continue, pause, or stop).

## Verification Checklist

- [ ] Checklist items are specific, testable, and owner-assigned.
- [ ] Required artifacts are linked and current.
- [ ] Escalation path is clear when a gate fails.

## Related Docs

- index.md
- ../00_overview/engineer_entrypoint.md
- ../11_ops/codex_run_loop.md
- ../11_ops/git_workflow_gitlab.md
