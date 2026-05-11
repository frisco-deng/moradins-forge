---
title: "Project Builder Runbook"
status: approved
owner: platform-operations
last_reviewed: 2026-03-29
source_refs: []
related_docs:
  - docs/design_docs/project_builder_control_api.md
  - docs/product_specs/project_builder_ui.md
  - ../references/project_builder_prompt_catalog.md
  - ../15_checklists/project_builder_release_acceptance_matrix.md
  - project_builder_ssh_operator_guide.md
---

# Project Builder Runbook

## Startup

Primary agent-first adoption starts from `FORGE.md` and
`scripts/moradin_forge.*`. Use the browser only when you need diagnostics,
visual deploy-state review, or release evidence.

1. `scripts/moradin_forge.sh plan --target <repo>`
2. Review proposed writes and request-only install artifacts.
3. `scripts/moradin_forge.sh apply --target <repo> --approve`
4. Optional UI: `./harness_devops.sh --port 5273`
5. For the guarded existing-project sandbox path, use `make sandbox-ui`
6. Open `/deploy/quick-start`, `/deploy/readiness`, `/deploy/map`,
   `/deploy/builder`, and `/deploy/status`
7. Confirm `/system-status` reports the expected feature flags before using remote flows
8. Use `make release-check` when you need release-grade evidence instead of a spot check
9. Use `make ui-review-screenshots` when you need a deterministic local screenshot set for route review

Browser access modes for the current-scope release:

- local Linux: browse on `localhost`
- WSL: browse from Windows on `localhost` or the WSL IPv4 address
- remote Linux: keep the harness UI loopback-only and use `ssh -L 5273:127.0.0.1:5273 <linux-host>`

## Builder Wizard

The Builder route is organized into five operator-facing steps:

1. `Target Repo`
2. `Project Context`
3. `Deploy Harness`
4. `Build Project Phases`
5. `Run Phase Prompt`

The deploy summary remains visible during the flow and keeps only the high-signal state:

- selected workflow
- selected target repo
- connection mode
- approval state
- critical-gap count
- generated artifact links

`Explainability` and `Advanced` stay collapsed by default:

- `Explainability`
  - workflow graph
  - payload fill tree
- `Advanced`
  - repo creation and completeness tools
  - import tooling
  - remote SSH checks

## Companion Workflow

- The Builder is an optional web companion to Codex or Claude beside VSCode or Claude.
- The browser is not the execution host; CLI commands always run on the Linux host that launched the harness.
- Assistant action bars expose prompt preview, copied prompts, copied terminal commands, and artifact links so the operator can stay in the editor while using the harness as the control surface.
- The current-scope release does not include a Windows-native desktop shell or an embedded editor.
- `/deploy/map` is the visual preflight surface for understanding what the harness will fill before opening Builder.

## Guided Quick Start

`/deploy/quick-start` is now a guided onboarding surface instead of a markdown-first page.

The current operator path is:

1. `Quick Start`
2. `Readiness`
3. `Deploy Map`
4. `Builder`
5. `Verify`
6. `Deploy Example`
   - tutorial-only
   - seeded
   - read-only

Quick Start behavior:

- the page opens with a dimmed overlay tutorial until the operator dismisses or completes it
- the tutorial must never trigger deploy, scan, generate, or assistant execution
- `Readiness` writes request-only install artifacts and repo registry snapshots without executing host installs
- `Deploy Example` reuses deterministic preview data so the operator can see Builder and Verify states without acting on a repo
- the longer markdown runbook remains available as a secondary, collapsible panel
- once every guided step is complete, the operator can explicitly remove the tutorial instead of having it silently return

## Workflow Selection

Use the first choice as the main path selector:

- `New Project`
  - create a fresh repo from approved discovery synthesis
- `Existing Project`
  - scan a repo, collect discovery context, then deploy a guarded sidecar
- `Import Existing Harness`
  - import a known-good harness from local path or archive bundle

Repo creation and completeness checks remain under the advanced tools panel.

## Discovery Flow

1. Start the discovery session with structured intake or prompt intake.
2. Generate questions.
3. Answer unresolved items.
4. Generate synthesis.
5. Mark the approval artifact before generate/deploy actions.
6. For existing-project work, carry the generated follow-on prompts into the phase implementation loop instead of auto-running them.

Prompt artifacts written per session:

- `prompt_context_v1.json`
- `prompt_bundle.json`
- `prompt_bundle.md`
- `project_scan.json` and `project_scan.md` when a scan is attached
- `template_fill_map.json`
- `template_fill_map.md`
  - includes `Scan-Derived Context` with detected languages, package managers, CI surfaces, deployment surfaces, and critical gaps
- `phase_plan.json`
- `phase_plan.md`
- `execution_prompts.json`
- `alignment_state.json`
- `alignment_state.md`

Follow-on planning contract:

- `bootstrap_prompt.md` always records the scan-summary keys `languages`, `package_managers`, `ci_surfaces`, and `deployment_surfaces`, even when a category is empty.
- `phase_plan.json` should preserve and extend detected validation and deployment surfaces instead of silently overwriting them.
- `alignment_state.json` becomes the canonical answer for what the harness filled, what discovery filled, what is still manual, and what the operator should do next.

## New Project Flow

1. Choose `New Project`.
2. Set destination repo and payload profile.
3. Complete discovery and approval.
4. Run `Generate Project Repo`.
5. Review the validation payload and payload fill map artifacts.

## Existing Project Flow

1. Enable `BUILDER_EXISTING_PROJECT_MODE=true`.
2. Choose `Existing Project`.
3. Pick `local` or `remote_ssh`.
4. For sandbox validation, target the latest `existing_project_fixture_*` repo recorded in `public_audit/dry_run_smoke_test_report.md` under `<projects-root>/moradin_tmp_runs`.
5. For first live adoption evidence, run `PYTHONPATH=. UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_live_adoption_release.py` and use the generated sacrificial repo under `<projects-root>/moradin_tmp_runs/live_adoption_repo_*`.
6. For `remote_ssh`, select a saved SSH profile and run:
   - `Test Connection`
   - `List Target Root`
   - `Check Sidecar`
     - enter the target repo path under the allowlisted root when probing the deployed sidecar
7. Run project scan.
8. Complete discovery and approval.
9. Review critical-gap policy:
   - `block_with_override`
   - `warn_only`
   - `hard_block`
10. Deploy the sidecar.
11. Run `Build Project Phases`.
12. Open `/deploy/status`.

## Moradin Payload And Readiness

- Payload source of truth: `Harness/moradin_payload/manifest.yaml`
- Compatibility script alias: `scripts/manage_harness_template.py`
- Canonical validation: `make payload-validate`
- Canonical smoke: `make payload-smoke`
- Readiness API:
  - `GET /api/moradin/readiness`
  - `POST /api/moradin/install-request`
  - `GET /api/moradin/repo-registry`
- Install request artifacts:
  - `Harness/artifacts/control/install_requests/<request_id>/`
- Repo registry artifacts:
  - `Harness/artifacts/control/repo_registry/`

Remote deploy contract:

- generate and validate the sidecar locally first
- stream it via tar-over-SSH
- unpack only under `<allowlisted_root>/<target_repo>/<sidecar_dir>`
- no free-form destructive remote shell is exposed in the UI

## Import Flow

1. Choose `Import Existing Harness`.
2. Set destination repo.
3. Either provide a local source path or upload a `.zip`, `.tar.gz`, or `.tgz`.
4. Use overwrite confirmation only when the destination is intentionally being replaced.

## Assistant Buttons

Builder, Review Hub, and Project Status all expose the same action bar:

- `Preview Prompt`
- `Run Selected Assistant`
- `Copy Prompt`
- `Open Artifacts`

Current-scope release behavior is read-only/generation-only:

- stdout/stderr are captured
- artifacts are written under `Harness/artifacts/control/assistant_runs/`
- no repo mutation or auto-apply endpoint is exposed

## Failure Handling

- `outside_allowlist`
- `symlink_escape_blocked`
- `invalid_bundle_filename`
- `unsupported_bundle_format`
- `overwrite_confirmation_required`
- `approval_required`
- `existing_project_mode_disabled`
- `remote_ssh_disabled`
- `origin_not_allowed`
- `invalid_remote_auth_method`
- `missing_remote_pem_path`
- `critical_gaps_blocked`
- `critical_gaps_hard_blocked`
- `assistant_command_missing`

## Privacy and Origin Controls

- `BUILDER_PATH_DISCLOSURE_MODE=masked` is the default operator-safe setting.
- `BUILDER_PATH_DISCLOSURE_MODE=full` is local-debug only.
- trusted origins are enforced by the control API through `TRACKER_TRUSTED_ORIGINS` and `TRACKER_API_TRUSTED_ORIGINS`.

## Post-Run Checks

- `make release-check`
- `make alignment-proof`
- `make ui-review-screenshots`
- `make ui-playwright-mcp-doctor`
- `npm --prefix dev_tracker/ui run sync-docs`
- `uv run pytest`
- `uv run ruff check .`
- `make lint-md`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`

## UI Evaluator Loop

Use the repo-native sequence first:

1. `make ui-test`
2. `make ui-test-browser`
3. `make ui-build`
4. `make ui-review-screenshots`

`make ui-review-screenshots` writes a deterministic local screenshot bundle under `dev_tracker/ui/.review_evidence/`.

This evidence is:

- local only
- not required repo truth
- intended for cycle review and operator walkthroughs

## Playwright MCP Opt-In

Playwright MCP is optional and repo-local.

Use it only when Codex itself needs to drive a live browser during an evaluator loop. Do not treat it as part of the baseline release gate.

Repo-local setup:

1. `make ui-playwright-mcp-doctor`
2. `dev_tracker/ui/scripts/bootstrap-playwright-mcp.sh`
3. rerun `node ./dev_tracker/ui/scripts/playwright-mcp-doctor.mjs --require-mcp` if you need strict MCP confirmation from your shell

Keep these boundaries intact:

- ordinary repo validation stays on `make ui-test-browser`
- screenshot capture stays on `make ui-review-screenshots`
- Playwright MCP is human-enabled and opt-in only

## Release Evidence

`make release-check` is the current-scope release gate for the guarded sandbox path. It:

- refreshes the latest dry-run fixtures with `payload-smoke`
- resolves the newest `existing_project_fixture_*` target
- deploys the harness into that sandbox through the current builder API
- writes the latest report to `public_audit/release_reports_excluded/latest.json` and `public_audit/release_reports_excluded/latest.md`
- runs the sacrificial live-adoption pass through `scripts/run_live_adoption_release.py`
- runs the goal-driven seed-generation pass through `scripts/run_seed_generation_release.py`
- snapshots proof-owned artifacts under `public_audit/release_evidence_excluded/<report_name>/` before temporary control roots are removed
- keeps those retained proof bundles manager-only so they do not flow into downstream harness copies
- fails if any report-linked proof artifact no longer exists after the proof run
- runs the sandbox user-emulation matrix through `testing_suite/runner.py auto`

`make alignment-proof` is the post-release-check alignment validator. It:

- confirms the retained `alignment_state.json` and `alignment_state.md` artifacts exist for the release proof reports
- fails if the alignment artifact is missing versioning, source breakdown, or next-action guidance
- optionally runs one guarded assistant handoff with `ASSISTANT_E2E=1 ASSISTANT=codex_cli` or `ASSISTANT=claude_code`
- uses `codex exec --color never --sandbox read-only` for Codex-backed proof runs so the handoff stays non-interactive and read-only
- accepts `ALIGNMENT_PROOF_ASSISTANT_TIMEOUT_SECONDS=<seconds>` when the assistant-backed proof needs a longer host timeout window
- verifies that the assistant run stays in `local_repo` scope and does not mutate the sandbox target repo

First live adoption evidence is tracked separately:

- `scripts/run_live_adoption_release.py` creates the sacrificial repo, runs the guarded existing-project flow end to end, and writes `public_audit/release_reports_excluded/live_adoption.json` plus `public_audit/release_reports_excluded/live_adoption.md`
- `public_audit/release_reports_excluded/live_adoption_baseline.json` preserves the pre-refinement baseline used to confirm the prompt/payload cleanup improved the emitted bootstrap artifacts

Goal-driven seed-generation evidence is tracked separately:

- `scripts/run_seed_generation_release.py` scans a sacrificial source repo, blocks generation on approval, generates a fresh harness seed repo from the approved discovery goal, and writes `public_audit/release_reports_excluded/seed_generation.json` plus `public_audit/release_reports_excluded/seed_generation.md`
- the matching durable artifact bundle lives under `public_audit/release_evidence_excluded/seed_generation/`

Sandbox user-emulation evidence is tracked separately:

- `testing_suite/runner.py auto` probes Docker rootless, Podman, Bubblewrap, Distrobox, and optional Incus reachability before running the release-candidate UI flow against every detected-and-runnable sandbox-backed repo
- `public_audit/release_reports_excluded/sandbox_matrix.json` plus `public_audit/release_reports_excluded/sandbox_matrix.md` capture aggregate status
- Per-sandbox bootstrap reviews are written beside the aggregate matrix in `public_audit/release_reports_excluded/`, using filenames derived from the sandbox id for both `.json` and `.md` outputs
- the suite isolates discovery-draft docs under a temporary release-run root so the manager repo does not pick up generated `discovery_*` docs during automation
- detected-but-unusable sandboxes are reported as skipped with a concrete reason; Incus remains non-blocking unless the daemon is reachable
