---
title: "Template Profiles"
status: approved
owner: product-operations
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - ../references/redeployable_harness_contract_v1.md
  - docs/exec_plans/commissioning/completed/plan_mh_004_redeployable_release.md
---

# Template Profiles

## Purpose

Define profile presets for redeployable harness generation from Builder + discovery outputs.

## Profiles

- `web_app`
- baseline user-facing service architecture
- deploy target assumptions: web frontend + API + datastore

- `data_pipeline`
- ingestion, transform, scheduling, and observability baseline
- deploy target assumptions: batch/event pipeline

- `agent_platform`
- multi-agent orchestration, memory, and tool contracts baseline
- deploy target assumptions: orchestrator + model/tool adapters

- `internal_tooling`
- operator-focused internal systems baseline
- deploy target assumptions: role-based access + audit surfaces

## Contract

- Profile selection must be explicit during discovery synthesis.
- Generated docs/plans must include selected profile in frontmatter or metadata.
- Profile defaults are additive and can be overridden by approved discovery answers.
