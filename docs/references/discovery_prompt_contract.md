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
