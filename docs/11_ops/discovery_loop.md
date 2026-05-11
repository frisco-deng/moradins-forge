---
title: "Discovery Loop"
status: approved
owner: platform-operations
last_reviewed: 2026-03-02
source_refs: []
related_docs:
  - ../15_checklists/discovery_gate.md
  - ../references/discovery_prompt_contract.md
  - docs/design_docs/project_builder_control_api.md
---

# Discovery Loop

## Objective

Convert initial project intent into approved, actionable harness artifacts using staged intake and synthesis.

## Stages

1. Intake capture (`project_goal`, `users`, `constraints`, `timeline`, `integrations`, `compliance`, `deployment_target`).
2. Generate deterministic question set.
3. Capture and refine answers.
4. Generate synthesis drafts.
5. Human approval gate before execution.

## Output Artifacts

- `Harness/artifacts/control/discovery_sessions/<session_id>/session.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/synthesis.md`
- `docs/product_specs/discovery_<session_id>_project_spec.md`
- `docs/design_docs/discovery_<session_id>_architecture.md`
- `docs/exec_plans/implementation/active/plan_<session_id>_discovery_generated.md`

## Blocking Rules

Block execution when any condition is true:

- approval artifact remains pending
- required intake keys are missing
- synthesis generation failed or missing

## Routing

- Non-critical refinement feedback routes to `docs/exec_plans/tooling/active/`.
- Approved discovery plan routes into implementation execution cycle planning.
