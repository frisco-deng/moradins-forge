---
title: "Documentation Review Gate"
status: approved
owner: docs-build-pipeline
last_reviewed: 2026-03-02
source_refs: []
related_docs:
  - ../11_ops/documentation_review_loop.md
  - ../11_ops/codex_run_loop.md
  - Harness/artifacts/control/documentation_review_status.md
  - docs/exec_plans/tooling/active/index.md
  - docs/exec_plans/tech-debt-tracker.md
---

# Documentation Review Gate

## Purpose

- Enforce scheduled documentation-review checks with risk-based continuation blocking.

## Gate Checklist

- [ ] Review executed on cadence (every 3 completed cycles).
- [ ] Contract docs match current interface behavior.
- [ ] Security docs match current policy and enforcement controls.
- [ ] Human-gate docs and checklists match active run-loop enforcement.
- [ ] Canonical path references resolve under `Harness/artifacts/` and `docs/exec_plans/`.
- [ ] Critical findings are either fixed or continuation is blocked.
- [ ] Non-critical findings are routed to `docs/exec_plans/tooling/active/` and `docs/exec_plans/tech-debt-tracker.md`.
- [ ] Documentation review status artifact is updated.
