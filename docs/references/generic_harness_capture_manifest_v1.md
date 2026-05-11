---
title: "Generic Harness Capture Manifest V1"
status: approved
owner: platform-operations
last_reviewed: 2026-03-29
source_refs: []
related_docs:
  - portability_copy_contract.md
  - generic_harness_bootstrap_sequence.md
  - Harness/artifacts/control/compatibility_window_status.md
  - docs/exec_plans/tooling/completed/tlg_2026_027_cycle_028_compatibility_removal_runbook.md
---

# Generic Harness Capture Manifest V1

## Purpose

- Define the deterministic harness-core copy boundary for bootstrapping a new generic deployable harness repository.
- Keep product/runtime implementation code out of the captured package.
- Keep manager-only proof evidence out of downstream sidecars and generated harness seeds.

## Include Globs

- `AGENTS.md`
- `ARCHITECTURE.md`
- `DESIGN.md`
- `FRONTEND.md`
- `PLANS.md`
- `PRODUCT_SENSE.md`
- `QUALITY_SCORE.md`
- `RELIABILITY.md`
- `SECURITY.md`
- `README.md`
- `Makefile`
- `pyproject.toml`
- `uv.lock`
- `docs/exec_plans/**`
- `Harness/artifacts/**`
- `docs/engineer_entry/**`
- `docs/00_overview/**`
- `docs/01_principles/**`
- `docs/02_contracts/**`
- `docs/03_architecture/**`
- `docs/11_ops/**`
- `docs/13_style_guides/**`
- `docs/15_checklists/**`
- `docs/entrypoint_guide/**`
- `docs/design_docs/**`
- `docs/product_specs/**`
- `docs/references/**`
- `skills/**`
- `scripts/check_branch_hygiene.py`
- `scripts/check_contract_compatibility.py`
- `scripts/generate_openapi_snapshots.py`
- `scripts/generate_phase4_reports.py`
- `scripts/validate_repo_skills.py`
- `scripts/validate_capture_contract.py`
- `dev_tracker/ui/src/**`
- `dev_tracker/ui/scripts/**`
- `dev_tracker/ui/tests/**`
- `dev_tracker/ui/package.json`
- `dev_tracker/ui/package-lock.json`
- `dev_tracker/ui/tsconfig.json`
- `dev_tracker/ui/tsconfig.app.json`
- `dev_tracker/ui/vite.config.ts`
- `dev_tracker/ui/index.html`
- `tests/contracts/**`
- `tests/scripts/**`

## Exclude Globs

- `apps/services/**`
- `rag_pipeline/**`
- `tests/api/**`
- `tests/connectors/**`
- `tests/runtime/**`
- `tests/retrieval/**`
- `tests/evaluation/**`
- `tests/events/**`
- `tests/observability/**`
- `docs/04_services/**`
- `docs/05_ingestion/**`
- `docs/06_retrieval/**`
- `docs/07_storage/**`
- `docs/08_observability/**`
- `docs/09_evaluation/**`
- `docs/10_security/**`
- `docs/12_pipelines/**`
- `docs/14_adrs/**`
- `docs/16_examples/**`
- `docs/99_generated/**`
- `docs/capability_pipeline/**`
- `docs/archive/**`
- `public_audit/release_evidence_excluded/**`
- `dev_tracker/ui/public/generated/**`
- `dev_tracker/ui/dist/**`
- `dev_tracker/ui/node_modules/**`
- `dev_tracker/ui/.vite/**`
- `**/*.tsbuildinfo`

## Allowed Legacy Reference Files

- `docs/references/portability_copy_contract.md`
- `dev_tracker/ui/scripts/sync-docs.mjs`
- `dev_tracker/ui/scripts/watch-docs.mjs`
- `dev_tracker/ui/scripts/check-engineer-entry-frontmatter.mjs`
- `dev_tracker/ui/src/pages/FeaturesPage.tsx`
- `dev_tracker/ui/src/pages/ExchangePage.tsx`
- `dev_tracker/ui/src/components/ExchangeNodeCard.tsx`
- `docs/references/generic_harness_capture_manifest_v1.md`
- `docs/exec_plans/tooling/completed/tlg_2026_027_cycle_028_compatibility_removal_runbook.md`
- `scripts/validate_capture_contract.py`
- `tests/contracts/test_docs_path_compatibility.py`
- `tests/scripts/test_validate_capture_contract.py`

## Deterministic Copy Order

1. Root manifests and build/dependency manifests.
2. `Harness/artifacts/**` and `docs/exec_plans/**`.
3. `docs/01_principles/**`, `docs/11_ops/**`, `docs/15_checklists/**`, and `docs/references/**`.
4. `skills/**` and selected `scripts/**`.
5. `dev_tracker/ui/**` source/scripts/tests and manifest files.
6. `tests/contracts/**` and `tests/scripts/**`.

## Normalization Rules

- Keep canonical path roots unchanged (`Harness/artifacts`, `docs/exec_plans`, `skills`).
- Canonical-only path policy is enforced.
- Do not include generated tracker payloads from `dev_tracker/ui/public/generated/**`.
- Do not include manager-only proof evidence retained under `public_audit/release_evidence_excluded/**`.
- Do not include product runtime domains excluded above.

## Verification

- `make validate-capture-contract`
- `make lint-py`
- `make lint-md`
- `make compat-contracts`
- `make openapi-snapshots`
- `make phase4-reports`
- `make validate-skills`
- `npm --prefix dev_tracker/ui run sync-docs`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
