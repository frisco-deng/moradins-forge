---
title: "Project Builder Beta Checklist"
status: approved
owner: platform-operations
last_reviewed: 2026-03-17
source_refs: []
related_docs:
  - ../11_ops/project_builder_runbook.md
  - ../11_ops/quick_start.md
  - ../11_ops/project_builder_ssh_operator_guide.md
  - project_builder_beta_acceptance_matrix.md
  - ../references/project_builder_prompt_catalog.md
  - ../product_specs/project_builder_ui.md
  - ../exec_plans/updates/completed/update_review_2026-03-17_hup0010_mvp_sandbox_implementation_review.md
  - ../exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md
---

# Project Builder Beta Checklist

Cycle note:
`cycle_032_hup0010_mvp_sandbox_closeout` is the MVP closeout cycle. The builder loop is intentionally unchanged; this checklist tracks the simplified deploy route, deterministic sandbox validation, and the implementation review signoff.

## Launcher And Sandbox Startup

- [x] `./harness_devops.sh --port <n>` still launches the UI and control API for the live operator path. Evidence: `docs/11_ops/quick_start.md` and `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md`.
- [x] `make sandbox-ui` launches the live sandbox path with `BUILDER_EXISTING_PROJECT_MODE=true` and `BUILDER_ALLOWLIST_ROOT=<projects-root>/moradin_tmp_runs`. Evidence: `Makefile`, `docs/11_ops/project_builder_runbook.md`, and `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md`.
- [x] `--restart-existing` remains part of the supported live sandbox launch path. Evidence: `make sandbox-ui` shells through `./harness_devops.sh --port 5273 --restart-existing`.
- [x] `make beta-check` is the release-blocking MVP gate and runs `alpha-check`, `template-smoke`, and the guarded practical sandbox preflight in order. Evidence: `Makefile` and `Harness/artifacts/reports/beta/latest.md`.

## Builder Flow

- [x] The primary operator route is the staged five-step flow: `Target Repo -> Project Context -> Deploy Harness -> Build Project Phases -> Run Phase Prompt`. Evidence: `dev_tracker/ui/src/pages/ProjectBuilderPage.tsx`, `dev_tracker/ui/tests/builder-page.test.tsx`, and `docs/11_ops/project_builder_runbook.md`.
- [x] Project context includes structured intake plus `other_context`, while freeform prompt mode remains available as an advanced path. Evidence: `dev_tracker/ui/tests/builder-page.test.tsx` and `dev_tracker/ui/tests/control-api-backend.test.ts`.
- [x] Explainability and advanced repo/import tooling remain available without crowding the primary flow. Evidence: `ProjectBuilderPage.tsx` and `docs/product_specs/project_builder_ui.md`.
- [x] Follow-on prompt assets are generated after deploy for `bootstrap_hydration`, `phase_planning`, `phase_1_execution`, and `run_all_phases`. Evidence: `dev_tracker/ui/tests/control-api-backend.test.ts`, `Harness/artifacts/reports/beta/latest.json`, and `docs/references/project_builder_prompt_catalog.md`.

## Sandbox Existing-Project Flow

- [x] The deterministic practical test resolves the latest `existing_project_fixture_*` target from the smoke-test outputs before attempting deploy. Evidence: `scripts/manage_harness_template.py`, `tests/scripts/test_manage_harness_template.py`, and `Harness/artifacts/reports/beta/latest.json`.
- [x] The guarded `existing_project` flow blocks deploy before approval, records approval, runs project scan, deploys the sidecar, and writes `phase_plan.json`, `phase_plan.md`, and `execution_prompts.json`. Evidence: `scripts/run_builder_beta_smoke.py`, `Harness/artifacts/reports/beta/latest.json`, and `dev_tracker/ui/tests/control-api-backend.test.ts`.
- [x] The live first-run route is `/deploy/quick-start -> /deploy/map -> /deploy/builder -> /deploy/status`. Evidence: `dev_tracker/ui/tests/first-run-path.browser.test.tsx`, `docs/15_checklists/project_builder_beta_acceptance_matrix.md`, and `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md`.
- [x] No hidden repo mutation occurs outside the guarded `.moradins-harness` sidecar and no auto-execution endpoint runs Codex. Evidence: `docs/design_docs/project_builder_control_api.md`, `docs/product_specs/project_builder_ui.md`, and the cycle-032 closeout report.

## Docs, Tracking, And Review

- [x] The beta checklist, acceptance matrix, implementation phases, and active-objective docs all reflect the simplified five-step builder flow and sandbox-first MVP gate. Evidence: `docs/15_checklists/project_builder_beta_checklist.md`, `docs/15_checklists/project_builder_beta_acceptance_matrix.md`, and `docs/00_overview/implementation_phases.md`.
- [x] The active HUP-0010 beta integration track is closed and archived into completed commissioning records. Evidence: `docs/exec_plans/commissioning/completed/plan_2026-03-07_hup0010_beta_integration_track.md` and `docs/exec_plans/commissioning/completed/index.md`.
- [x] The implementation review note records the UI review outcome directly and separates `beta blocker` work from `post-beta` leftovers. Evidence: `docs/exec_plans/updates/completed/update_review_2026-03-17_hup0010_mvp_sandbox_implementation_review.md`.

## Regression Gates

- [x] `make branch-hygiene` passes for the cycle closeout state. Evidence: `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md`.
- [x] `make alpha-check` passes. Evidence: `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md`.
- [x] `make beta-check` passes and writes the canonical beta preflight report bundle. Evidence: `Harness/artifacts/reports/beta/latest.json`, `Harness/artifacts/reports/beta/latest.md`, and the cycle-032 closeout report.

## MVP Closeout Gate

- [x] The UI review is triaged directly in the implementation review note. `beta blocker`: none. `post-beta`: thin wrapper, expanded auth/hosting, and bundle-size work. Evidence: `docs/exec_plans/updates/completed/update_review_2026-03-17_hup0010_mvp_sandbox_implementation_review.md`.
- [x] README, Quick Start, How To Direct, `/deploy/quick-start`, `/deploy/map`, `/deploy/builder`, and `/deploy/status` are revalidated as one first-run operator path. Evidence: `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md`.
- [x] HUP-0010 beta integration closeout is recorded in a new approved cycle artifact set. Evidence: `docs/exec_plans/commissioning/completed/plan_2026-03-07_hup0010_beta_integration_track.md`, `docs/exec_plans/commissioning/completed/report_2026-03-17_cycle_032_hup0010_mvp_sandbox_closeout.md`, and `Harness/artifacts/control/loop_state.md`.
