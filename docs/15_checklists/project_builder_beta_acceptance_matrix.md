---
title: "Project Builder Beta Acceptance Matrix"
status: approved
owner: platform-operations
last_reviewed: 2026-03-17
source_refs: []
related_docs:
  - ../11_ops/project_builder_runbook.md
  - ../11_ops/quick_start.md
  - ../design_docs/project_builder_control_api.md
  - ../references/project_builder_prompt_catalog.md
  - ../exec_plans/updates/completed/update_review_2026-03-17_hup0010_mvp_sandbox_implementation_review.md
---

# Project Builder Beta Acceptance Matrix

## Purpose

- Define the release-blocking sandbox scenarios for the current builder MVP.

## Acceptance Matrix

| scenario_id | scenario | required checks | evidence root | pass rule |
| --- | --- | --- | --- | --- |
| BETA-001 | Automated existing-project sandbox preflight | latest dry-run fixture resolves, existing-project mode is enabled, discovery synthesizes, deploy blocks before approval, approval artifact is marked, project scan passes, sidecar deploy succeeds, follow-on phase artifacts are written, project status succeeds | `Harness/artifacts/reports/beta/latest.json` | all checks pass |
| BETA-002 | Live operator first-run route | `/deploy/quick-start -> /deploy/map -> /deploy/builder -> /deploy/status`, latest `existing_project_fixture_*` target is used, fill-map and phase-plan artifacts appear, no hidden repo mutation occurs outside `.moradins-harness` | `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md` | all checks pass |

## Beta-Ready Definition

`beta ready` means:

- `make beta-check` exits successfully.
- `Harness/artifacts/reports/beta/latest.json` reports a passing automated sandbox preflight.
- The implementation review note and closeout report both record the live operator route as complete.
