---
title: "Redeployable Harness Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-03-29
source_refs: []
related_docs:
  - portability_copy_contract.md
  - generic_harness_capture_manifest_v1.md
  - docs/product_specs/template_profiles.md
  - docs/exec_plans/commissioning/completed/plan_mh_004_redeployable_release.md
---

# Redeployable Harness Contract V1

## Goal

Define destination-harness requirements to generate additional project repos deterministically.

## Required Capabilities

- Builder route (`/builder`) with create/import/discovery operations.
- Discovery-generated canonical docs and plan artifacts for both `prompt` and `onboarding` intake modes.
- Template profile selection (`web_app`, `data_pipeline`, `agent_platform`, `internal_tooling`).
- Human-gate enforcement before execution handoff.
- Generate response metadata: `harness_seed_version`, `generated_files[]`, and validation checks.

## Required Copy Set

- Root manifests (`AGENTS.md`, `ARCHITECTURE.md`, `DESIGN.md`, `FRONTEND.md`, `PLANS.md`, `PRODUCT_SENSE.md`, `QUALITY_SCORE.md`, `RELIABILITY.md`, `SECURITY.md`)
- `docs/exec_plans/**`
- `Harness/artifacts/**`
- `docs/engineer_entry/**`
- `docs/00_overview/**`
- `docs/01_principles/**`
- `docs/02_contracts/**`
- `docs/03_architecture/**`
- `docs/13_style_guides/**`
- `docs/entrypoint_guide/**`
- `docs/references/**`
- `skills/**`
- `dev_tracker/ui/**`
- required scripts + `Makefile`

## Excluded Manager-Only Evidence

- Release-proof evidence under `public_audit/release_evidence_excluded/**` remains in the manager repo for auditability.
- Redeployable harness copies must exclude that proof evidence so downstream payloads stay focused on the runtime/control scaffold.

## Release Gate

- `make lint`
- `make validate-capture-contract`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`

## Next Version Trigger

Increment contract version when any required capability or required copy-set path changes.
