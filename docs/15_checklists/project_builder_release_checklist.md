---
title: "Project Builder Release Checklist"
status: approved
owner: platform-operations
last_reviewed: 2026-03-23
source_refs: []
related_docs:
  - ../11_ops/project_builder_runbook.md
  - ../11_ops/quick_start.md
  - ../11_ops/project_builder_ssh_operator_guide.md
  - project_builder_release_acceptance_matrix.md
  - ../references/project_builder_prompt_catalog.md
  - ../product_specs/project_builder_ui.md
  - ../../Harness/artifacts/control/release_exit_tracker.md
---

# Project Builder Release Checklist

Program note:
This checklist tracks the current-scope release candidate after the sandbox-first MVP closeout. It supersedes the beta checklist for active work while historical beta artifacts remain archived for historical evidence.

## Release Scope Lock

- [x] The current-scope release remains Linux-hosted, local/SSH, and single-user.
- [x] `HUP-0012` remains deferred because public hosting, PAT / HTTPS auth, and multi-user controls are out of scope.
- [x] Active docs, launcher text, and UI copy describe the product as a current-scope release instead of a beta.

## Canonical Gates And Reports

- [x] `make release-check` is the canonical gate.
- [x] `make alignment-proof` exists as the post-gate alignment validator.
- [x] `make beta-check` exists only as an undocumented transition alias.
- [x] Canonical reports write to `public_audit/release_reports_excluded/`.
- [x] Release reports only point at durable artifact snapshots or retained sandbox repos after the proof run completes.

## Live Adoption And Prompt Quality

- [x] A sacrificial real git repo under the allowlisted root is used for first live adoption.
- [x] The existing-project flow completes discovery, approval pause, sidecar deploy, follow-on plan generation, and status verification against that repo.
- [x] Prompt and template-fill outputs are reviewed and refined from the live-adoption findings.
- [x] A goal-driven seed-generation proof scans a sacrificial repo, blocks on approval, generates a fresh harness seed repo, and records the resulting template-fill evidence.
- [x] The release proof reports retain `alignment_state.json` and `alignment_state.md` so operators can inspect what remains manual after the proof run.

## Performance Hardening

- [x] Route loading uses page-level lazy boundaries.
- [x] `npm --prefix dev_tracker/ui run build` completes without the current chunk-size warning.
- [x] Route and builder/status/browser coverage remain green after the split.

## Sandboxed User Emulation

- [x] `testing_suite/` probes Docker rootless, Podman, Bubblewrap, and Distrobox.
- [x] Every detected-and-runnable sandbox passes.
- [x] Every detected-but-unusable sandbox is reported as skipped with a concrete reason.
- [x] The suite proves no bootstrap mutation escapes the guarded `.moradins-harness` sidecar.
- [x] The suite leaves no new discovery-generated docs in the manager repo.

## Review And Promotion Readiness

- [x] `Harness/artifacts/control/release_exit_tracker.md` is complete.
- [x] `HUMAN_REVIEW.md` is refreshed into the release review tracker and marked complete.
- [x] Review Hub surfaces the release tracker and latest release report.
- [x] `HUP-0013` is closed with evidence and `HUP-0011` / `HUP-0012` remain explicitly deferred.
