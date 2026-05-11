---
title: "Generic Harness Bootstrap Sequence"
status: approved
owner: platform-operations
last_reviewed: 2026-03-02
source_refs: []
related_docs:
  - generic_harness_capture_manifest_v1.md
  - portability_copy_contract.md
  - Harness/artifacts/control/compatibility_window_status.md
---

# Generic Harness Bootstrap Sequence

## Purpose

- Define destination-side Day-0 bootstrap steps for importing this harness-core package into a new generic deployable harness repository.
- Keep this source repository unchanged beyond capture-contract publication.

## Day-0 Bootstrap

1. Copy files using `generic_harness_capture_manifest_v1.md` include/exclude rules.
2. Validate copy integrity in destination with `python scripts/validate_capture_contract.py`.
3. Run deterministic setup in destination:
- `npm --prefix dev_tracker/ui install`
- `make validate-skills`
- `make compat-contracts`
- `make openapi-snapshots`
- `make phase4-reports`
- `npm --prefix dev_tracker/ui run sync-docs`
4. Run destination quality gates:
- `make lint-py`
- `make lint-md`
- `PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run pytest`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`

## First-Cycle Initialization in Destination

1. Keep compatibility pointers/fallbacks enabled for the first 2 approved cycles.
2. Record window status in destination `Harness/artifacts/control/compatibility_window_status.md`.
3. Generate first destination changelog row and loop-state row before scope expansion.
4. Do not remove legacy pointers/fallbacks until cycle 2/2 is approved.

## External Template Policy

- External template path `<EXTERNAL_TEMPLATE_ROOT>` remains reference-only for this source repo cycle.
- No template overwrite or cutover occurs in this cycle.
- Any cutover executes only in a separately approved destination cycle with rollback gates.

## Destination Acceptance

- Capture manifest validation passes.
- Tracker sync and UI tests/build pass.
- Canonical artifacts resolve from `Harness/artifacts` and `docs/exec_plans`.
- Compatibility-window telemetry is visible and accurate.
