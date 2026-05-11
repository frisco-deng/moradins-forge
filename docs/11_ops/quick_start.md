---
title: "Quick Start"
status: approved
owner: platform-operations
last_reviewed: 2026-03-17
source_refs: []
related_docs:
  - local_dev.md
  - project_builder_runbook.md
  - docs/entrypoint_guide/how_to_direct.md
  - docs/design_docs/project_builder_visual_reference.md
  - ../15_checklists/project_builder_release_checklist.md
---

# Quick Start

## Purpose

- Provide the five-minute startup path for Moradin's Forge agent-first adoption
  and the optional browser diagnostics workbench.

## Five-Minute Forge Startup

1. Ask the agent to read:
   - `FORGE.md`
   - `Harness/entrypoints/forge.md`
   - `docs/references/moradin_forge_agent_integration_contract_v1.md`
2. Have the agent explain the sidecar, adapter writes, readiness gaps, rollback,
   and validation commands before changing the target repo.
3. Create a dry-run plan:
   - Linux/macOS: `scripts/moradin_forge.sh plan --target <target-repo>`
   - Windows PowerShell: `.\scripts\moradin_forge.ps1 plan --target <target-repo>`
4. After explicit consent, apply:
   - Linux/macOS: `scripts/moradin_forge.sh apply --target <target-repo> --approve`
   - Windows PowerShell: `.\scripts\moradin_forge.ps1 apply --target <target-repo> --approve`
5. Review:
   - `.moradins-harness/Harness/artifacts/control/forge_integration/integration.md`
   - any install request under `Harness/artifacts/control/install_requests/`
   - the target repo's validation command output

Forge does not execute host install commands. Missing tools are request-only
artifacts for a human to review and run.

## Optional Workbench Startup

1. Install dependencies:
   - `uv sync`
   - `npm --prefix dev_tracker/ui install`
2. Launch the harness:
   - `./harness_devops.sh --port 5273`
   - if an earlier harness instance is already running: `./harness_devops.sh --port 5273 --restart-existing`
   - for the guarded existing-project sandbox path: `make sandbox-ui`
3. Open the UI:
   - local Linux: `http://localhost:5273/`
   - WSL: `http://localhost:5273/` from Windows first, then the WSL IPv4 address if needed
   - remote Linux: `ssh -L 5273:127.0.0.1:5273 <linux-host>`
4. Open these pages in order:
   - `/deploy/quick-start`
   - `/deploy/readiness`
   - `/deploy/map`
   - `/deploy/builder`
   - `/deploy/status`

## Supported Current-Scope Release Access Modes

- `local Linux`
  - Run and browse on the same Linux host.
- `WSL`
  - Run in WSL and browse from Windows through `localhost` or the WSL IP.
- `remote Linux via SSH tunnel`
  - Keep the UI loopback-only and forward the port with `ssh -L`.

Do not expose the current-scope release UI on a public network.

## Launcher Notes

- Root launcher config: `harness_devops.toml`
- Generated runtime state: `.harness_devops/runtime.json`
- Preview the resolved launch without starting processes:
  - `./harness_devops.sh --port 5273 --dry-run`
- If the launcher reports a foreign process on the requested UI port or `127.0.0.1:8787`, free the port or choose a different `--port`.
- The launcher may restart only previously identified Moradins Harness processes, never unrelated services.

## First Successful Builder Flow

1. Open `/deploy/map` and choose the workflow you want to understand.
2. Open `/deploy/readiness` and create request-only install artifacts for any missing tools that must be fixed before deploy.
3. Open `/deploy/builder`.
4. Use the five-step route:
   - `Target Repo`
   - `Project Context`
   - `Deploy Harness`
   - `Build Project Phases`
   - `Run Phase Prompt`
5. Expand `Explainability` only when you need the workflow graph or fill tree.
6. Expand `Advanced` only when you need repo utilities, import tools, or remote SSH checks.
7. For an existing-project sandbox pass, target the latest `existing_project_fixture_*` repo recorded in `public_audit/dry_run_smoke_test_report.md` under `<projects-root>/moradin_tmp_runs`.
8. Run `Build Project Phases` after deploy so `phase_plan.json`, `phase_plan.md`, `execution_prompts.json`, and `alignment_state.md` are written before you move to `/deploy/status`.

## Where Output Appears

- Prompt/context artifacts:
  - `Harness/artifacts/control/discovery_sessions/<session_id>/`
- Install request artifacts:
  - `Harness/artifacts/control/install_requests/<request_id>/`
- Repo registry artifacts:
  - `Harness/artifacts/control/repo_registry/`
- Assistant run artifacts:
  - `Harness/artifacts/control/assistant_runs/`
- Generated payload fill maps:
  - `template_fill_map.json`
  - `template_fill_map.md`
- Follow-on planning artifacts:
  - `phase_plan.json`
  - `phase_plan.md`
  - `execution_prompts.json`
  - `alignment_state.json`
  - `alignment_state.md`
- Live visual replay:
  - `/deploy/builder` shows the latest fill tree, alignment summary, and follow-on prompt actions
  - `/deploy/map` reuses the latest cached builder output
  - `/deploy/status` refreshes project status and alignment state after guarded deploy work

## Release-Grade Validation

- `make payload-validate` validates the Moradin payload manifest and compatibility scaffold.
- `make alpha-check` remains the structural preflight.
- `make release-check` reruns the latest payload smoke fixture, deploys the harness into that existing-project sandbox, proves the goal-driven seed-generation path, and records durable report snapshots under `public_audit/release_reports_excluded/`.
- `make alignment-proof` builds on `make release-check`, validates the retained alignment artifacts across the proof flows, and can optionally run one guarded assistant handoff with `ASSISTANT_E2E=1`.

## Companion Model

- The agent-first Forge scripts are the primary control surface.
- The browser UI is an optional diagnostics and review workbench.
- Codex CLI or Claude Code CLI run locally beside the user's editor.
- Moradin does not replace VSCode, Codex, or Claude; it supplies local reflexes,
  deterministic briefs, request-only readiness, and bounded sidecar adoption.
