---
title: "Git Workflow Gitlab"
status: approved
owner: platform-architecture
last_reviewed: 2026-03-22
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
  - https://medium.com/@DataDo/building-production-grade-agentic-rag-a-technical-deep-dive-part-1-beyond-fixed-windows-9879cf3cc7b1
related_docs:
  - index.md
  - ../00_overview/engineer_entrypoint.md
  - tooling_pipeline.md
  - change_tracking_system.md
---

# Git Workflow Gitlab

## Purpose

- Define runbooks and environment controls for safe, repeatable operations.
- This document defines executable expectations for `git_workflow_gitlab`.

## Scope

- In scope: decisions, interfaces, risks, and checks that can be validated.
- Out of scope: speculative implementation detail without contract or runbook impact.

## Topic Decisions

- Git workflow enforces branch isolation and reviewed merges.
- Workflow steps are deterministic and owner-assigned.
- The MR gate for implementation work is `dev`, not `main`.
- `main` stays clean, synced to `origin/main`, and acts as the production baseline.
- `dev` is the human-review integration branch for combined feature work.
- `dev -> main` requires explicit human signoff.
- Operational procedures require deterministic command evidence.
- Run-loop governance enforces one-cycle execution and human continuation gates.

## Incremental Branch Structure

- Start every cycle from a clean, synced `main` and create one scoped branch.
- Deterministic branch-start command:
- `make branch-start PHASE=<n> STAGE=<n> SCOPE=<scope> [PREFIX=harness] [CYCLE_ID=<id>]`
- Branch naming policy:
- `feature/<scope>` for feature delivery.
- `fix/<scope>` for defects and regressions.
- `docs/<scope>` for docs-only cycles.
- `harness/<scope>` for harness and tooling enforcement updates.
- Optional phase shorthand for cycle docs: `p<phase>-s<stage>/<scope>`.
- Branch suffix must include an incremental routing marker (`p<phase>-s<stage>` or `cycle-<id>`).
- A cycle branch should map to one `phase_id`, one `stage_id`, and one `cycle_id`.
- Close every cycle branch through MR into `dev`.
- Return local working state to `main` after the feature branch is merged or closed.
- Promote `dev` to `main` only after human review approves the full integration state.

## Branch Start Contract

1. Create branch before any repo-tracked edits.
2. Branch must include phase/stage routing marker and scoped suffix.
3. `main` must be clean and synced to `origin/main` before branching.
4. If work needs to continue from a dirty state, branch immediately and keep the dirty state off `main`.
4. If branch-start command fails, stop and resolve git state before coding.

## Outstanding Branch Cleanup Routine

1. Run `make branch-hygiene` before cycle closeout.
2. Confirm work branches have upstream tracking, naming compliance, and routing markers.
3. Merge approved feature branches into `dev`.
4. Delete merged local feature branches (`git branch -d <branch>`).
5. Delete merged remote feature branches after the `dev` merge when the review system allows it.
6. Confirm `main` stays clean and synced to `origin/main`.
7. Promote `dev -> main` only after explicit human signoff.
8. Rebase or close stale unmerged branches using explicit reviewer decision.

## Waiver Routine

- Prefer cleanup over waivers.
- Use `Harness/artifacts/control/branch_hygiene_exception.json` only when a human
  explicitly approves starting scoped migration work before branch cleanup.
- The waiver must list exact local branches, remote branches, and stale local
  branches, include an expiration, and apply only to the active migration branch.
- `make branch-hygiene`, `make verify-security`, and `make review-ready` may pass
  with waived findings, but `dev -> main` promotion still requires cleanup or a
  renewed human waiver.

## Merge Request Gate Contract

- Every implementation branch must open an MR to `dev`.
- `main` must not receive direct feature MRs.
- `dev -> main` is a separate human-review promotion step.
- Required evidence in MR:
- `make lint`
- `PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run pytest`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
- `npm --prefix dev_tracker/ui run check:engineer-entry`
- `make branch-hygiene`
- MR closeout must include changelog approval fields and cycle artifact links.

## Interfaces / Dependencies

- Git interfaces include branch naming, MR policy, and evidence links.
- Workflow interfaces define input/output artifacts per stage.
- GitLab/GitHub interfaces map `feature -> dev` and `dev -> main` checks to required quality gates.
- Ops artifacts coordinate deployment, upgrades, and incident execution.

## Failure Modes / Risks

- Direct changes to main bypass governance controls.
- Dirty or divergent `main` breaks the clean-baseline contract.
- Direct edits on `dev` blur the human-review integration state.
- Workflow ambiguity causes inconsistent execution.
- Incorrect remote or target branch can break governance.
- Runbook drift causing inconsistent operator response.

## Verification Checklist

- [ ] Git workflow checks are part of cycle gate verification.
- [ ] Workflow completeness is checked before handoff.
- [ ] Feature MR targets `dev`.
- [ ] `main` remains clean and synced after feature work is pushed.
- [ ] Human signoff is recorded before `dev -> main`.
- [ ] Runbook steps are deterministic and operator-ready.
- [ ] Branch names follow incremental branch naming policy.
- [ ] Branch hygiene check passes before merge.
- [ ] Merged branches are cleaned up locally and remotely.

## Related Docs

- index.md
- ../00_overview/engineer_entrypoint.md
- tooling_pipeline.md
- change_tracking_system.md
