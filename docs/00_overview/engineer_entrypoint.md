---
title: "Engineer Entrypoint"
status: approved
owner: platform-operations
last_reviewed: 2026-03-23
source_refs: []
related_docs:
  - index.md
  - implementation_phases.md
  - ../11_ops/codex_run_loop.md
  - ../15_checklists/agent_cycle_gate.md
---

# Engineer Entrypoint

## Mission

- Deliver a redeployable harness deployer that can seed new project repositories from either prompt intake or structured onboarding intake.

## Active Objective HUP-0010

- Current gate: the Phase 5 current-scope release-exit program is complete on `dev`; the next action is human `dev -> main` promotion review using `Harness/artifacts/control/release_exit_tracker.md`, `HUMAN_REVIEW.md`, and the release evidence pack.
- In scope for approved release-exit work: release-scope lock, first live project adoption through the existing-project route, prompt/template refinement, release governance/docs replacement, `make release-check`, review closeout, and sandbox user-emulation coverage.
- Deferred after current-scope release: `HUP-0011` thin wrapper work and `HUP-0012` expanded PAT / HTTPS auth, public hosting, and multi-user controls.
- Out of scope until a new approval exists: Windows-native desktop shell, public internet hosting, PAT / HTTPS auth, multi-user session work, and editor embedding beyond the Linux-hosted companion.
- Stop condition: do not change the deploy/discovery/approval loop, add hidden repo mutation, or introduce auto-execution inside target repos without a new approval.

## Execution Constraints

- Keep canonical-only docs policy. Do not reintroduce deprecated compatibility roots.
- Enforce human approval before execution handoff from discovery output.
- Keep generated repo output under allowlisted local root unless explicitly configured.
- Treat only `docs/00_overview/engineer_entrypoint.md` and non-index `docs/engineer_entry/**/*.md` as human-owned context for the current-scope release.
- `docs/engineer_entry/index.md` is generated navigation, not human-owned content.

## Required Artifacts Per Cycle

- Updated plan artifact in `docs/exec_plans/*/active/` or `completed/`.
- Control artifact updates in `Harness/artifacts/control/`.
- Deterministic test/gate evidence.
