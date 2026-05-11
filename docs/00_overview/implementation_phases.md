---
title: "Implementation Phases"
status: approved
owner: platform-operations
last_reviewed: 2026-03-23
source_refs: []
related_docs:
  - engineer_entrypoint.md
  - ../11_ops/codex_run_loop.md
---

# Implementation Phases

## Phase 0 - Harness Governance Foundation

Phase status: `completed`

### Stage S00 - Baseline Governance and Tooling

- [x] Canonical governance artifacts exist under `Harness/artifacts/control/`.
- [x] Branch hygiene and engineer-entry checks are wired into quality gates.
- [x] Tracker sync and QA signal outputs are generated deterministically.

Done when:

- Governance loop is enforceable with explicit human-gate control.

## Phase 1 - Redeployable Harness Seed (MH-004)

Phase status: `completed`

### Stage S01 - Full Seed Generator

- [x] Discovery-driven generate endpoint validates approval artifact before writing output.
- [x] Full harness seed output includes root manifests, docs trees, scripts, skills, tracker source, and tests.
- [x] Generator response returns seed version, generated files, and validation checks.

### Stage S02 - Contract and Test Hardening

- [x] Backend endpoint tests cover create/import/discovery/generate paths.
- [x] Safety tests verify overwrite guard, allowlist escape block, symlink escape block, and unsafe archive rejection.
- [x] Generated repo acceptance checks assert seed completeness and baseline gate readiness.

Done when:

- MH-004 release gates are green and artifacts are marked approved.

## Phase 2 - Builder UX and Visual Explainability

Phase status: `completed`

### Stage S03 - Workflow Graph and Deploy Map

- [x] `/deploy/builder` uses the staged builder flow and keeps explainability tooling available through collapsed `Explainability` and `Advanced` panels.
- [x] `/deploy/map` exists as a top-level route with workflow selection, a baseline harness tree, and fill-source legend.
- [x] Template fill visuals show both pre-run baseline paths and post-run concrete output when builder artifacts exist.

### Stage S04 - Builder Navigation and Companion UX Polish

- [x] Builder keeps the visual explanation surfaces visible near the main operator flow without overwhelming the primary deploy sequence.
- [x] Overview and Help route first-run users into Quick Start, Deploy Map, Builder, and System Status.
- [x] The harness is explicitly described as a Linux-hosted companion to Codex or Claude, not an editor replacement.

Done when:

- Operators can understand what the harness will deploy before they run Builder actions.

## Phase 3 - Docs Semantics and Onboarding Clarity

Phase status: `completed`

### Stage S05 - Docs Ownership Taxonomy and Engineer-Entry Governance

- [x] Docs are classified as `human_owned_context`, `system_managed`, or `generated`.
- [x] `docs/engineer_entry/index.md` is treated as generated/system-managed.
- [x] Any non-index doc under `docs/engineer_entry/` is human-owned and must use `owner: person:<slug>`.

### Stage S06 - Root Onboarding, README, Quick Start, and Direction Patterns

- [x] Root `README.md` leads with release quick start and access modes.
- [x] `docs/11_ops/quick_start.md` defines the five-minute startup path.
- [x] `docs/entrypoint_guide/how_to_direct.md` includes operator prompt patterns for builder, review, and project status flows.

Done when:

- The docs no longer imply that most of the repo is human-authored, and a new operator can start without inferring the intended flow.

## Phase 4 - Beta Validation and Sign-Off

Phase status: `completed`

### Stage S07 - Validation Matrix and Regression Expansion

- [x] `make beta-check` revalidated the sandbox-first existing-project flow after the UX/docs integration pass.
- [x] Browser coverage exists for the core quick-start, deploy-map, and builder flows.
- [x] Beta checklist and acceptance matrix reflect visual explainability, docs classification, and the first-run product-flow review requirements.

### Stage S08 - Reviewer Sign-Off and Governance Closeout

- [x] The repo-recorded implementation review explicitly marks `beta blocker` items complete and separates true `post-beta` leftovers.
- [x] Governance artifacts record the sandbox-first MVP closeout without ambiguity and clear `beta_integration_followup_required`.
- [x] MVP closeout is declared only after revalidation evidence, the implementation review note, and closeout artifacts are all recorded.

Done when:

- The Linux-hosted web companion is understandable, validated, and approved for sandbox-first MVP use.

## Phase 5 - Release Exit And Operationalization

Phase status: `completed`

### Stage S09 - Release Governance, Docs Review, And Active Contract Reset

- [x] `make release-check` is the canonical current-scope release gate and `make beta-check` is an undocumented compatibility alias only.
- [x] Active docs, runbooks, checklists, and launcher/help text describe the product as a current-scope release instead of a beta.
- [x] The overdue documentation review is recorded and `Harness/artifacts/control/release_exit_tracker.md` is created.

### Stage S10 - First Live Adoption And Prompt Refinement

- [x] A sacrificial real git repo under the allowlisted root is used as the required first live adoption target.
- [x] The existing-project route completes discovery, approval pause, sidecar deploy, follow-on planning, and status verification against that repo.
- [x] Prompt and template-fill behavior are refined from the live-adoption findings and documented in the prompt catalog and runbook.

### Stage S11 - UI Performance Hardening

- [x] Route loading uses page-level lazy boundaries.
- [x] Vite vendor chunks isolate the heavy route domains so the entry chunk no longer triggers the current warning.
- [x] Route URLs, builder behavior, and browser coverage remain stable.

### Stage S12 - Sandbox User Emulation And Bootstrap Review

- [x] `testing_suite/` probes every detected sandbox and requires every detected-and-runnable sandbox to pass.
- [x] The suite launches the real harness stack, drives the live UI, marks the explicit approval artifact through a helper, and verifies the generated sidecar plus discovery artifacts.
- [x] Aggregate release reports are written under `public_audit/release_reports_excluded/`.

### Stage S13 - Review Closeout And Promotion Evidence

- [x] `HUMAN_REVIEW.md` is refreshed into the release review tracker and surfaced with the release tracker in Review Hub.
- [x] Control artifacts, changelog, loop state, human gate stats, archive register, and tech-debt routing are updated for the release candidate.
- [x] `HUP-0013` is closed and the repo is ready for human `dev -> main` review.

Done when:

- The Linux-hosted companion is documented, validated, and reviewed as a current-scope release candidate with live-adoption and sandbox evidence.
