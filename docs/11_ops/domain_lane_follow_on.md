---
title: "Manager Domain Lanes And Local Worker Follow-On"
status: draft
owner: platform-operations
last_reviewed: 2026-04-07
source_refs:
  - ../../../systems_improvements/codex_tooling_case_study/metrics_and_method.md
  - ../../../systems_improvements/codex_tooling_case_study/linkedin_post_draft.md
related_docs:
  - codex_run_loop.md
  - tooling_pipeline.md
  - quick_start.md
  - ../15_checklists/agent_cycle_gate.md
  - ../../Harness/entrypoints/agent.md
  - ../../Harness/README.md
---

# Manager Domain Lanes And Local Worker Follow-On

## Purpose

- Capture the next manager-safe follow-on after the `waifu-stack` V2 and sample-library lane hardening.
- Keep the current Moradins public loop stable while making the next domain-brief pattern explicit.
- Define a bounded local-worker contract that stays advisory and does not replace Codex as the orchestrator.

## Current State

- The manager repo already has a stable public loop:
  - `make repo-brief`
  - `make verify-fast`
  - `make review-ready`
- The next proven improvement from the workspace study is not more generic commands.
- It is better middle-and-back-half execution:
  - explicit domain briefs
  - latest-run metadata
  - failure fingerprints
  - unchanged-state summaries
  - stronger artifact reuse before broad reruns

## Manager Domain Briefs

Additive manager-domain entrypoints are available:

- `make builder-brief`
- `make adoption-brief`
- `make release-brief`

These do **not** replace the shared contract. They sit on top of it and become
the preferred starting point for their own bounded task families. Artifacts are
written under `Harness/artifacts/task_lanes/**`.

### `builder-brief`

Use for:

- project builder readiness
- builder-specific smoke results
- fill-map or generation troubleshooting
- builder UX or deployment-side validation

Current summary surface:

- latest builder report artifact
- current builder state fingerprint
- latest failure fingerprint when present
- recommended next narrow command

### `adoption-brief`

Use for:

- onboarding and repo-import flows
- documentation/adoption guidance checks
- operator-readiness work

Current summary surface:

- current adoption state and open blockers
- latest adoption artifact
- next deterministic command

### `release-brief`

Use for:

- release evidence
- approval and gate tracking
- pre-promotion verification

Current summary surface:

- current release-state artifact
- approval/gate freshness
- latest release or review evidence
- recommended next deterministic command

## Anti-Loop Behavior To Reuse

When the manager repo adopts these lanes, it should reuse the same advisory
pattern proven in the shared deck:

- active-lane marker
- latest-run metadata
- repo-state fingerprint
- failure fingerprint
- same-signature rerun warning
- unchanged-state warning
- explicit next-lane recommendation before broad reruns

This remains advisory, not blocking:

- warn before `make review-ready` or heavier release checks when no fresh
  domain-brief artifact exists
- surface the last artifact first
- recommend the narrow or repair-oriented lane first

## Bounded Gemma 4 Local Worker

Codex remains the orchestrator and final decision-maker. The local worker is a
bounded helper for small summarization and routing tasks only.

### Backend

- use the existing `aiproject` Gemma 4 small-profile stack
- keep the worker local-only and optional

### Allowed Tasks

- summarize the latest artifact
- cluster repeated failure fingerprints
- classify the active lane
- condense long reports into short next-step briefs
- propose the next deterministic command

### Explicitly Out Of Scope

- code mutation
- final review or security decisions
- repo discovery from scratch
- broad long-context coding work

### Proposed Contract

Input:

- `task_type`
- `repo_id`
- `artifact_paths`
- `state_fingerprint`
- `max_tokens`
- `allowed_actions`

Output:

- `summary`
- `recommended_next_command`
- `confidence`
- `needs_codex_escalation`
- `citations`

### Fallback Behavior

- if Gemma is unavailable, fall back to deterministic local synthesis
- if Gemma is low-confidence, escalate back to Codex
- worker output stays advisory and must never become the source of truth

## Adoption Sequence

1. keep the current manager repo command surface stable
2. use `make builder-brief`, `make adoption-brief`, and `make release-brief`
   before broad reruns in those lanes
3. add latest-run metadata and failure fingerprints before any stronger guardrails
4. only then pilot the bounded Gemma worker on artifact summarization

## Verification

- the manager public loop still works unchanged for ordinary repo work
- domain briefs are additive and task-specific
- latest-run metadata never replaces deterministic evidence
- the local worker remains optional and advisory only
