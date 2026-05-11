---
title: "Project Builder Release Acceptance Matrix"
status: approved
owner: platform-operations
last_reviewed: 2026-03-22
source_refs: []
related_docs:
  - ../11_ops/project_builder_runbook.md
  - ../11_ops/quick_start.md
  - ../design_docs/project_builder_control_api.md
  - ../references/project_builder_prompt_catalog.md
  - project_builder_release_checklist.md
---

# Project Builder Release Acceptance Matrix

## Purpose

- Define the release-blocking sandbox and live-adoption scenarios for the current-scope release.

## Acceptance Matrix

| scenario_id | scenario | required checks | evidence root | pass rule |
| --- | --- | --- | --- | --- |
| REL-001 | Automated release preflight | latest dry-run fixture resolves, existing-project mode is enabled, discovery synthesizes, deploy blocks before approval, approval artifact is marked, project scan passes, sidecar deploy succeeds, follow-on phase artifacts are written, project status succeeds | `public_audit/release_reports_excluded/latest.json` | all checks pass |
| REL-002 | First live repo adoption | sacrificial repo exists as a real git repo, discovery synthesizes, approval is explicitly recorded, sidecar deploy succeeds, prompt/template outputs are reviewed, and status succeeds | `public_audit/release_reports_excluded/live_adoption.json` | all checks pass |
| REL-003 | Goal-driven seed generation | scanned source repo context is preserved, generate-from-discovery blocks before approval, the fresh harness seed repo is created after approval, template-fill provenance is reviewable, and deterministic validation passes | `public_audit/release_reports_excluded/seed_generation.json` | all checks pass |
| REL-004 | Sandboxed user emulation suite | every detected-and-runnable sandbox passes, every detected-but-unusable sandbox is reported as skipped with reason, the live UI path is driven, and bootstrap review proves guarded sidecar-only mutation | `public_audit/release_reports_excluded/sandbox_matrix.json` | all required sandboxes pass |

## Release-Ready Definition

`release ready` means:

- `make release-check` exits successfully.
- `make alignment-proof` exits successfully.
- `public_audit/release_reports_excluded/latest.json` reports a passing automated release preflight.
- `public_audit/release_reports_excluded/live_adoption.json` reports a passing sacrificial live adoption.
- `public_audit/release_reports_excluded/seed_generation.json` reports a passing goal-driven seed-generation proof.
- each passing proof report retains durable `alignment_state.json` and `alignment_state.md` evidence.
- `public_audit/release_reports_excluded/sandbox_matrix.json` reports passing results for every detected-and-runnable sandbox.
- The review tracker and release tracker both record the candidate as ready for human `dev -> main` review.
