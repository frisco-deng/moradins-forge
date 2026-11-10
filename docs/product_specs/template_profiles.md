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

- Profiles are advisory classifications. Deployment assumptions above are design
  candidates, not requirements to add services, persistence or orchestration.
  Ground selected components in the product journey and existing architecture.
- An agent-platform label grants no delegation, model/provider change or runtime
  authority. Existing user and repository boundaries remain binding.
- Profile selection must be explicit during discovery synthesis.
- Generated docs/plans must include selected profile in frontmatter or metadata.
- Adopt profile defaults only when supported by accepted discovery facts and
  native product requirements; preserve supplied constraints and unknowns.
