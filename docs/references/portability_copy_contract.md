---
title: "Portability Copy Contract"
status: approved
owner: platform-operations
last_reviewed: 2026-03-29
source_refs: []
related_docs:
  - ../../README.md
  - ../../PLANS.md
  - docs/exec_plans/index.md
  - ../../Harness/artifacts/README.md
  - Harness/artifacts/control/compatibility_window_status.md
  - generic_harness_capture_manifest_v1.md
  - generic_harness_bootstrap_sequence.md
  - ../../AGENTS.md
---

# Portability Copy Contract

## Purpose

- Define the minimum stable harness package for copying into a new repository.
- Preserve governance and compatibility behavior during staged migrations.

## Required Copy Set

1. Root manifests:
- `AGENTS.md`
- `ARCHITECTURE.md`
- `DESIGN.md`
- `FRONTEND.md`
- `PLANS.md`
- `PRODUCT_SENSE.md`
- `QUALITY_SCORE.md`
- `RELIABILITY.md`
- `SECURITY.md`
2. Execution plans:
- `docs/exec_plans/**`
3. Harness artifacts:
- `Harness/artifacts/**`, excluding manager-only release-proof evidence under `public_audit/release_evidence_excluded/**`
4. Foundational principles:
- `docs/01_principles/**`
5. Skills:
- `skills/**`
6. Required scripts and make interfaces:
- `scripts/generate_openapi_snapshots.py`
- `scripts/check_contract_compatibility.py`
- `scripts/generate_phase4_reports.py`
- `scripts/validate_repo_skills.py`
- `scripts/validate_capture_contract.py`
- `make openapi-snapshots`
- `make compat-contracts`
- `make phase4-reports`
- `make validate-skills`
- `make validate-capture-contract`
- `make lint`

## Compatibility Window Contract

1. Compatibility window for this repository is closed as of 2026-03-02.
2. Canonical-only paths are now required:
- `AGENTS.md`
- `Harness/artifacts/**`
- `docs/exec_plans/**`
3. Legacy archive records remain as historical pointers under `docs/archive/records/**`, but are not runtime dependencies.

## Removal Checklist (Completed 2026-03-02)

- [x] Remove old-path pointer docs (`agents.md`, `docs/99_generated/**`, `docs/capability_pipeline/**`).
- [x] Remove tracker and script fallback lookups.
- [x] Run dead-link sweep and docs snapshot validation.
- [x] Confirm archive register paths remain canonical under `docs/exec_plans/*/completed/`.
- [x] Record closure in changelog and loop artifacts.

## Verification

- `make lint-py`
- `make lint-md`
- `make compat-contracts`
- `make openapi-snapshots`
- `make validate-skills`
- `make validate-capture-contract`
- `PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run pytest`
- `npm --prefix dev_tracker/ui run sync-docs`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`

## Proof Evidence Boundary

- Release-proof snapshots retained under `public_audit/release_evidence_excluded/**` are manager-only audit evidence.
- Those proof bundles must remain available for operator review in the manager repo.
- They must not be copied into downstream sidecars or generated harness seeds.
