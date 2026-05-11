---
title: "Project Builder UI"
status: approved
owner: product-operations
last_reviewed: 2026-03-29
source_refs: []
related_docs:
  - docs/design_docs/project_builder_control_api.md
  - ../11_ops/project_builder_runbook.md
  - docs/design_docs/project_builder_visual_reference.md
  - ../11_ops/quick_start.md
---

# Project Builder UI

## Goal

Keep the browser surface useful as an optional diagnostics workbench while the
primary adoption path moves to Moradin's Forge native agent scripts.

The product direction for this pass is:

- one optional harness workbench that can target multiple repos
- a quiet launchpad on `/home`
- a secondary `/deploy/*` path for readiness, repo targeting, project context
  capture, Moradin deployment, and next-step prompts
- no change to the underlying guarded discovery and deploy loop

Current-scope release direction:

- agent-first Forge scripts for Linux/macOS and Windows PowerShell
- browser companion beside VSCode, Codex, or Claude
- no automatic host tool installation

The UI must let a new operator answer three questions quickly:

1. Which workflow am I running?
2. What target am I acting on?
3. What did the harness fill automatically versus what discovery filled in?

## Primary Routes

- `/home`
- `/deploy/quick-start`
- `/deploy/readiness`
- `/deploy/map`
- `/deploy/builder`
- `/deploy/status`
- `/payload`

Secondary manager workspaces remain available, but they are no longer the first thing the operator sees when the immediate goal is deploying or extending a harness into a target repo.

`/deploy/map` remains the first visual explanation surface. It must still be reachable before the operator runs generation or sidecar deploy.

## Home Launchpad

`/home` is now a launchpad instead of a dashboard wall.

It must:

- lead with one primary CTA into Forge diagnostics or project selection
- summarize tracked repos, approvals, and runtime state at a glance
- surface the current active work package, active update cycle, active commissioning context, and pending human gate without forcing the operator into the review tables first
- keep manager queues and recent activity available below the fold or inside collapsible sections

When no project is selected, the above-the-fold state must stay simple:

- `Choose Project`
- `Open Diagnostics`
- `Latest Proof And Status`

The no-project state should explain that governance-heavy context moved lower on the page instead of leading the route.

## Deploy Focus Mode

All `/deploy/*` routes run in a focused shell mode:

- hide the global context rail
- trim topbar status chrome to essential deploy metadata
- keep deploy-route navigation visible
- avoid competing portfolio panels while the operator is making repo-specific decisions

The deploy secondary navigation must be lightweight:

- breadcrumb-style label plus current sub-route
- simple horizontal links
- optional unseen dots
- no boxed pill container around the tabs

The same secondary-nav pattern should be reused across deploy, reviews, settings, and project workspace surfaces.

## Builder Information Architecture

`/deploy/builder` keeps the existing workflow engine but reorganizes the surface into this explicit sequence:

1. `Target Repo`
2. `Project Context`
3. `Deploy Harness`
4. `Build Project Phases`
5. `Run Phase Prompt`

The first action is still workflow selection:

- `New Project`
- `Existing Project`
- `Import Existing Harness`

The UI must preserve the current workflow ids and backend behavior:

- `new_project`
- `existing_project`
- `import_existing_harness`

## Guided Quick Start Contract

`/deploy/quick-start` is the onboarding route, not a markdown wall.

It must:

- open with a focused overlay walkthrough
- dim the page behind the active tutorial step
- keep one clear next action visible at a time
- preserve the four real deploy routes:
  - `Quick Start`
  - `Readiness`
  - `Deploy Map`
  - `Builder`
  - `Verify`
- add one tutorial-only step:
  - `Deploy Example`
  - deterministic
  - read-only
  - no execution side effects

The tutorial state must track:

- dismissed
- completed
- visited route ids
- completed tutorial step ids
- example flow viewed

The operator must be able to:

- dismiss the tutorial
- resume it explicitly
- remove it only after all guided steps are complete

The longer markdown runbook remains secondary help and must render inside a constrained, scrollable panel.

## Builder Summary

The builder summary card must stay concise and operator-facing. It shows:

- stage readiness across the 5-step route
- selected target repo
- approval state
- follow-on prompt selection
- artifact links for prompt context, payload fill, approval, bootstrap prompt, phase plan, execution prompts, and alignment state
- a compact alignment summary once phase planning is written so the operator can see what remains manual before using an assistant prompt

## Project Context Contract

Structured intake is the default path.

The primary fields are:

- `project_goal`
- `users`
- `constraints`
- `timeline`
- `integrations`
- `compliance`
- `deployment_target`
- `other_context`

Freeform prompt mode remains available, but it is an advanced option instead of the main entry surface.

## Companion Support Model

- local Linux uses `localhost`
- WSL uses Windows browser access through `localhost` or WSL IPv4
- remote Linux uses SSH local port forwarding only
- the selected assistant always runs on the Linux host that launched the harness
- tool installs are request-only: `/deploy/readiness` writes install request artifacts and never runs host install commands

## Payload Workspace

- `/payload` is the primary Moradin payload workspace.
- `/template` redirects to `/payload` for one compatibility window.
- Primary navigation must use `Payload`, not template wording.
- Payload validation should route operators to `make payload-validate` and `make payload-smoke`.

## Operational Defaults

Settings now own non-secret operator defaults:

- preferred assistant
- default discovery provider
- default discovery model
- saved SSH profile metadata

Secrets are not stored in browser state.

## SSH UX

Builder and System Status both expose SSH controls:

- saved profile selector
- `Test Connection`
- `List Target Root`
  - lists the selected repo when a target repo is supplied
- `Check Sidecar`
  - probes `<target_repo>/<sidecar_dir>` under the allowlisted root instead of the allowlisted root itself

Supported auth for the current-scope release:

- `ssh_agent`
- `pem_path`

Deferred for a future scope expansion:

- PAT / HTTPS Git-host flows

## Assistant UX

Builder, Review Hub, and Project Status share a reusable assistant action bar.

For the builder route, the prompt sources are now:

- discovery prompt preview
- `Bootstrap Hydration`
- `Build Project Phases`
- `Implement Phase 1`
- `Run All Phases`

- `Preview Prompt`
- `Run Selected Assistant`
- `Copy Prompt`
- `Copy Terminal Command`
- `Open Artifacts`

The assistant bar is an operator tool, not an execution trigger.
It must also show:

- assistant runtime availability
- browser access summary
- explicit Linux-host execution note

The assistant bar must never silently run Codex or Claude inside a target repo. Follow-on actions may load prompts and terminal commands, but execution stays human-triggered.

## Explainability Surfaces

The product still exposes two high-value visual surfaces:

- deploy flow visual
  - new project
  - existing project
  - import flow
  - implemented with React Flow in the UI
- payload fill map view
  - Moradin payload
  - profile overlay
  - user filled
  - scan derived
  - implemented as an expandable baseline-plus-output tree

These visuals now appear in two places:

- `/deploy-map` for the top-level explanation
- `/deploy/builder` inside a collapsed `Explainability` panel for workflow-specific execution context

Repo utilities and remote checks also move into collapsed `Advanced` panels so the main route stays calm.

## Docs Taxonomy Surface

The UI must stop using a vague catch-all label for most docs.

Docs are presented with these labels:

- `human-owned context`
  - `docs/00_overview/engineer_entrypoint.md`
  - `docs/engineer_entry/**/*.md` except `docs/engineer_entry/index.md`
- `system-managed`
  - all remaining docs outside the human-owned and generated buckets
- `generated`
  - any doc with `generated: true`

The Docs Explorer must show per-doc classification and let the operator filter on that label.
It must also make active exec plans visually distinct from archived provenance inputs so operators do not mistake the vNext input archive for current planning truth.

`/docs` is explorer-first:

- search bar first
- filters second
- doc list immediately visible
- no active upgrade or update tiles above the fold

## First-Run Product Flow

The expected release onboarding sequence is:

1. `README.md`
2. `docs/11_ops/quick_start.md`
3. `docs/entrypoint_guide/how_to_direct.md`
4. `/home`
5. `/deploy/quick-start`
6. `/deploy/readiness`
7. `/deploy/map`
8. `/deploy/builder`
9. `/deploy/status`

The UI should not assume the operator already knows the deployer internals before they reach `/builder`.

These visuals should explain what the Moradin payload deploys without opening docs first.

## Review and Status UX

- `/reviews/queue` remains the human decision hub and also exposes assistant actions.
- `/reviews/queue` and `/reviews/exchange` must surface the same active-package and pending-gate state before the denser review tables begin.
- `/reviews/exchange` is now an activity surface in behavior and visible labeling.
- `/reviews/exchange` should lead with the rolling change feed, then show governed work and supporting review state only where they help the feed.
- `/deploy/status` supports local and remote status refresh after guarded deploy work and becomes the alignment hub for goal lock, approval state, blocking gaps, provenance breakdown, and next action.
- `/settings/system` is the connection and runtime prep surface.
- portfolio, review, payload, and docs workspaces remain important but are secondary to the deploy route during builder operations.

## Non-Goals

- no hidden repo mutation from assistant buttons
- no automatic phase execution from the builder surface
- no free-form destructive remote shell
- no PAT-based Git-host auth in the current-scope release
- no public internet-exposed current-scope release deployment
- no embedded editor or VSCode-clone desktop shell
