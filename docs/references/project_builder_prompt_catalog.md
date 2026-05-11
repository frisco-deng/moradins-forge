---
title: "Project Builder Prompt Catalog"
status: approved
owner: platform-operations
last_reviewed: 2026-03-23
source_refs: []
related_docs:
  - docs/design_docs/project_builder_control_api.md
  - ../11_ops/project_builder_runbook.md
---

# Project Builder Prompt Catalog

## Current Prompt Surfaces

1. Deterministic discovery system instructions in `control-api.mjs`
2. Discovery question-generation prompt
3. Discovery synthesis-generation prompt
4. Prompt bundle preview assembled from compact context artifacts
5. `Bootstrap Hydration` follow-on prompt
6. `Build Project Phases` follow-on prompt
7. `Implement Phase 1` follow-on prompt
8. `Run All Phases` follow-on prompt

## Workflow-Specific Templates

- `new_project_questions`
- `new_project_synthesis`
- `existing_project_questions`
- `existing_project_synthesis`

Follow-on prompt ids:

- `bootstrap_hydration`
- `phase_planning`
- `phase_1_execution`
- `run_all_phases`

## Context Inputs

Prompt bundles now reference compact context instead of raw markdown bodies:

- `context_pack_v1.json`
- `prompt_context_v1.json`
- discovery session context
- optional project scan summary with stable `languages`, `package_managers`, `ci_surfaces`, `deployment_surfaces`, and `critical_gaps` fields
- optional synthesis context
- structured intake fields including `other_context`

## Artifact Outputs

- `prompt_context_v1.json`
- `prompt_bundle.json`
- `prompt_bundle.md`
- `project_scan.json`
- `project_scan.md`
- `template_fill_map.json`
- `template_fill_map.md`
- `bootstrap_prompt.md`
- `phase_plan.json`
- `phase_plan.md`
- `execution_prompts.json`
- `execution_prompts.md`

## Follow-On Prompt Intent

- `Bootstrap Hydration` tells Codex or Claude to hydrate placeholders, align canonical docs, preserve deterministic checks, keep the harness loop intact, and treat detected repo surfaces as constraints. The prompt always records `languages`, `package_managers`, `ci_surfaces`, and `deployment_surfaces` even when a scan category is empty.
- `Build Project Phases` turns discovery output into repo-specific phase plans and verification routes while preserving detected validation and deployment surfaces in the plan summary.
- `Implement Phase 1` scopes execution to the first phase only so harness hydration and scope lock happen before broader implementation.
- `Run All Phases` prepares a full multi-phase route while preserving explicit human review checkpoints.

`template_fill_map.md` now includes a `Scan-Derived Context` section so operators can review the scan summary beside the placeholder fill plan before moving into execution.

## Fallback Rules

- If hosted or CLI providers are unavailable, discovery remains deterministic.
- If model output is malformed, discovery falls back to the deterministic question/synthesis builders already embedded in the control API.

## Prompt Caching

- OpenAI prompt caching hooks are enabled through request metadata when configured.
- CLI providers are unchanged and do not use hosted prompt caching.
