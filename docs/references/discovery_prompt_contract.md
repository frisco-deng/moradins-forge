---
title: "Discovery Prompt Contract"
status: approved
owner: platform-operations
last_reviewed: 2026-03-02
source_refs: []
related_docs:
  - ../11_ops/discovery_loop.md
  - docs/design_docs/project_builder_control_api.md
---

# Discovery Prompt Contract

## Purpose

Define stable prompt and output-shape requirements for discovery question and synthesis generation.

## Inputs

- Intake fields (stage 1)
- Existing question set (stage 2)
- Answer map (stage 3)

## Required Question Output Shape

- `questions[]`
- each entry:
- `question_id`
- `prompt`
- `rationale`
- `required`

## Required Synthesis Output Shape

- `summary`
- `recommended_profile`
- `must_haves[]`
- `open_questions[]`
- `product_spec`
- `design`
- `plan`

## Fallback Rule

If configured LLM backend is unavailable or response validation fails, deterministic local synthesis is mandatory.

## Product-Aware Planning

Retain the existing synthesis fields and saved-session contracts. Ground the
product intent, users, constraints and declared integrations in supplied facts;
name missing evidence and its affected decision instead of using answer counts.
Unrelated responses do not become product constraints. Existing answer records
remain available for targeted review.

New phase plans retain `phase_1`, `phase_2` and `phase_3`: working product baseline,
normal-path integration/repeatability, then automation and target-driven
refinement. These are dependency-aware slices of the accepted product, not
automatic services, branches or new approval gates. Existing discovery/adoption
approval and protected operations remain binding; old generated artifacts retain
their historical scope and are not silently rewritten.

Follow-on prompt IDs remain stable. Native entrypoints wire the pure planning
module; generation cannot execute a plan, approve adoption or change a model.
