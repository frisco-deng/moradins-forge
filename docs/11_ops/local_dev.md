---
title: "Local Dev"
status: approved
owner: platform-architecture
last_reviewed: 2026-03-08
source_refs: []
related_docs:
  - index.md
  - quick_start.md
  - project_builder_runbook.md
  - ../00_overview/engineer_entrypoint.md
---

# Local Dev

## Purpose

- Define the default local startup path for the Moradins Harness control plane.
- Keep local launch behavior deterministic for builder, review, and status workflows.

## Canonical Startup

Use the repo-root launcher instead of manually sequencing UI commands:

1. `./harness_devops.sh --port 5273`
2. Open `http://localhost:5273/`
3. For a port preview without launching, run `./harness_devops.sh --port 5273 --dry-run`
4. If an earlier Moradins Harness instance is still running, rerun with `./harness_devops.sh --port 5273 --restart-existing`
5. Start the release flow in:
   - `/deploy/quick-start`
   - `/deploy/map`
   - `/deploy/builder`
   - `/deploy/status`

## Launcher Contract

- `harness_devops.sh --port <1-65535>`
- `harness_devops.sh --help`
- `harness_devops.sh --dry-run`
- `harness_devops.sh --restart-existing`
- `--port` controls only `TRACKER_UI_PORT`
- Control API remains on `TRACKER_API_PORT` default `8787`
- Root launcher config is `harness_devops.toml`
- Generated runtime state is `.harness_devops/runtime.json`
- CLI `--port` overrides config `ui_port`; env vars override config defaults
- The script validates the config and port, preflights the UI/API ports, prints resolved URLs, then executes `npm --prefix dev_tracker/ui run dev:ops`
- Managed Moradins Harness instances can be restarted interactively or via `--restart-existing`
- Foreign processes on the requested UI port or `127.0.0.1:8787` are reported and never terminated by the launcher

## Direct Commands

Only use these when debugging the launcher:

1. `npm --prefix dev_tracker/ui run sync-docs`
2. `npm --prefix dev_tracker/ui run control-api`
3. `npm --prefix dev_tracker/ui run dev`

## Local Networking

- Preferred URLs:
  - `http://localhost:<TRACKER_UI_PORT>/`
  - `http://127.0.0.1:<TRACKER_UI_PORT>/`
  - `http://<wsl-ip>:<TRACKER_UI_PORT>/` for WSL-to-Windows browser flows
- Remote Linux host access for the current-scope release uses SSH local port forwarding only:
  - `ssh -L <TRACKER_UI_PORT>:127.0.0.1:<TRACKER_UI_PORT> <linux-host>`
- `TRACKER_UI_HOST` remains optional and is auto-selected by the existing WSL-aware policy.
- `TRACKER_API_PORT` remains fixed at `8787` for the current-scope release.
- `TRACKER_TRUSTED_ORIGINS` is the preferred CORS override for the control API.
- `TRACKER_API_TRUSTED_ORIGINS` remains the legacy alias.
- Do not use a public bind or internet-exposed ingress for the current-scope release.

## Recovery and Repeatability

- `Ctrl+C` from `./harness_devops.sh` should stop the supervisor, control API, docs watcher, and Vite dev server.
- Clean shutdown removes `.harness_devops/runtime.json`.
- If the runtime file exists but its recorded pids are dead, the next launch treats it as stale state and replaces it.
- If the launcher finds a live Moradins Harness instance:
  - interactive TTYs prompt for restart confirmation
  - non-interactive usage must pass `--restart-existing`
- If the launcher finds a foreign process:
  - it reports the occupied port, pid, and command when available
  - operators must free the port or choose a different UI port

## Builder Defaults

- Discovery provider/model defaults live in Settings, not env-only UI state.
- SSH profiles saved in Settings are non-secret metadata only.
- SSH supports `ssh_agent` and `pem_path` in the current-scope release.
- PAT / HTTPS auth is explicitly deferred until a future scope expansion.

## Verification

- `uv run ruff check .`
- `uv run pytest`
- `make lint-md`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`

## Failure Modes

- Invalid launcher port: script exits before starting the UI.
- Invalid launcher config: script exits before starting the UI.
- Existing managed harness instance: launcher prompts for restart or requires `--restart-existing`.
- Foreign process on UI or API port: launcher fails fast and reports the owner when detectable.
- Missing local dependencies: `npm --prefix dev_tracker/ui run dev:ops` fails directly.
- Trusted-origin mismatch: Builder/UI requests are blocked by the control API.
- WSL browser drift: restart WSL, then rerun `./harness_devops.sh --port <n>`.
