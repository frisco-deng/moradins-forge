---
title: "Project Builder Control API"
status: approved
owner: platform-operations
last_reviewed: 2026-03-29
source_refs: []
related_docs:
  - docs/product_specs/project_builder_ui.md
  - ../11_ops/project_builder_runbook.md
  - ../references/project_builder_prompt_catalog.md
  - project_builder_visual_reference.md
  - ../11_ops/quick_start.md
---

# Project Builder Control API

## Purpose

Define the optional browser workbench contract for builder, discovery, remote
SSH sidecar deploy, prompt artifacts, and assistant-trigger actions. The primary
Forge adoption path is native script based and documented in
`moradin_forge_agent_integration_contract_v1.md`.

## Public Endpoints

- `GET /api/moradin/readiness`
- `POST /api/moradin/install-request`
- `GET /api/moradin/repo-registry`
- `GET /api/builder/status`
- `GET /api/builder/providers`
- `POST /api/builder/create-local-repo`
- `POST /api/builder/repo-completeness`
- `POST /api/builder/project-scan`
- `POST /api/builder/deploy-existing`
- `POST /api/builder/project-status`
- `GET /api/builder/project-status/history`
- `POST /api/builder/generate-from-discovery`
- `POST /api/builder/import-harness-path`
- `POST /api/builder/import-harness-bundle`
- `POST /api/builder/remote/ssh/test`
- `POST /api/builder/remote/ssh/execute`
- `POST /api/discovery/session/start`
- `POST /api/discovery/session/answer`
- `POST /api/discovery/session/generate`
- `POST /api/discovery/session/build-prompt-bundle`
- `POST /api/discovery/session/build-follow-on-plan`
- `GET /api/discovery/session/:session_id`
- `POST /api/assistant/run`

## Safety Contract

- All local writes stay inside `BUILDER_ALLOWLIST_ROOT`.
- Path traversal and symlink escape are rejected.
- Overwrite requires explicit confirmation tokens.
- Discovery generate/deploy operations require a human approval artifact.
- Moradin readiness install requests write artifacts only and never execute host install commands.
- Native Forge install requests follow the same request-only rule.
- Remote flows are disabled unless `BUILDER_REMOTE_SSH_ENABLED=true`.
- Existing-project flows are disabled unless `BUILDER_EXISTING_PROJECT_MODE=true`.
- No auto-execution endpoint is exposed.
- Assistant runs are read-only/generation-only and execute from an isolated temp working directory.

## Control Status Contract

`GET /api/status` also exposes current-scope release companion metadata for all UI routes:

- `ui_access.runtime_mode`
- `ui_access.bind_host`
- `ui_access.ui_port`
- `ui_access.preferred_urls`
- `ui_access.browser_access_summary`
- `ui_access.remote_ssh_tunnel_example`
- `ui_access.execution_host_summary`
- `ui_access.public_bind_supported=false`
- `assistant_runtimes.codex_cli`
- `assistant_runtimes.claude_code`

This data is the UI source of truth for:

- Linux vs WSL browser guidance
- remote SSH tunnel instructions
- assistant command availability on the Linux host
- copyable terminal command templates

## Moradin Readiness Contract

`GET /api/moradin/readiness` returns `MoradinToolingReadinessV1` with:

- payload manifest summary
- required and optional tool checks
- missing-tool install guidance
- request-only safety marker
- install request and repo registry artifact roots

`POST /api/moradin/install-request` writes:

- `Harness/artifacts/control/install_requests/<request_id>/install_request.json`
- `Harness/artifacts/control/install_requests/<request_id>/install_request.md`

`GET /api/moradin/repo-registry` writes:

- `Harness/artifacts/control/repo_registry/repositories.json`
- `Harness/artifacts/control/repo_registry/repositories.md`

Readiness and registry artifacts are reusable assistant context and must not
perform repo mutation or host installs.

## Tracker Snapshot Contract

`dev_tracker/ui/public/generated/tracker_snapshot_v1.json` now serializes `TrackerSnapshotV6`.

The summary contract uses purposeful doc buckets:

- `docs_human_owned_context`
- `docs_system_managed`
- `docs_generated`

Each doc record also carries a derived `classification` field for UI filtering.

Classification rules for the current-scope release:

- `human_owned_context`
  - `docs/00_overview/engineer_entrypoint.md`
  - `docs/engineer_entry/**/*.md` except `docs/engineer_entry/index.md`
- `generated`
  - any doc with `generated: true`
- `system_managed`
  - all other docs

## Builder Status Contract

`BuilderStatusV1` includes:

- `existing_project_mode_enabled`
- `allowlisted_root`
- `path_disclosure_mode`
- `scan_limits_defaults`
- `project_status_history_retention`
- `known_repos`
- `recent_operations`

## Remote Target Contract

Remote target requests are additive extensions on existing builder endpoints:

- `target_mode: local | remote_ssh`
- `remote_target.target_id`
- `remote_target.connection_mode=ssh`
- `remote_target.host`
- `remote_target.user`
- `remote_target.port`
- `remote_target.allowlisted_root`
- `remote_target.profile_label`
- `remote_target.auth_method: ssh_agent | pem_path`
- `remote_target.pem_path`
- `remote_target.known_hosts_mode: strict | accept_new`

Current-scope remote release:

- SSH only
- `ssh_agent` and PEM-path auth supported
- PAT / HTTPS auth documented but deferred

## Discovery Contract

`DiscoverySessionV1` stores:

- intake fields
- question round
- answers
- scan summary
- synthesis payload
- approval artifact state
- artifact references

Discovery prompt templates are now explicit:

- `new_project_questions`
- `new_project_synthesis`
- `existing_project_questions`
- `existing_project_synthesis`

Discovery intake now includes `other_context` so structured onboarding can capture project details that do not fit the canonical boxes.

Prompt bundle metadata includes:

- `workflow_type`
- `prompt_template_id`
- `included_context_sections`
- `artifact_references`
- `source_citations`
- `prompt_context_artifact_path`
- `context_pack_artifact_path`

## Follow-On Planning Contract

`POST /api/discovery/session/build-follow-on-plan`

Request:

- `session_id`
- `target_repo`
- optional `selected_profile`

Response `DiscoveryFollowOnPlanResponseV1` includes:

- `workflow_type`
- `selected_profile`
- `phase_plan.summary`
- `phase_plan.phases[]`
- `phase_plan.next_recommended_phase_id`
- `alignment_state`
- `prompts[]`
- `artifact_paths.bootstrap_prompt_markdown`
- `artifact_paths.phase_plan_json`
- `artifact_paths.phase_plan_markdown`
- `artifact_paths.execution_prompts_json`
- `artifact_paths.execution_prompts_markdown`
- `artifact_paths.alignment_state_json`
- `artifact_paths.alignment_state_markdown`

The follow-on prompts are operator-facing prompt assets, not auto-execution commands:

- `bootstrap_hydration`
- `phase_planning`
- `phase_1_execution`
- `run_all_phases`

Follow-on artifact expectations:

- `bootstrap_prompt.md` records stable scan-summary lines for `languages`, `package_managers`, `ci_surfaces`, and `deployment_surfaces`, even when a category resolves to `none`
- `template_fill_map.md` includes a `Scan-Derived Context` section so operators can inspect scan-derived constraints before execution
- `phase_plan.json` carries scan-aware validation and deployment guidance forward into the recommended phases
- `alignment_state.json` is the canonical contract for what is already aligned, what remains manual, and which reviewed route the operator should take next

## Alignment State Contract

`AlignmentStateV1` stores:

- locked project goal
- approval state
- source breakdown across `seed_template`, `profile_overlay`, `user_filled`, `scan_derived`, and `manual_required`
- per-item alignment status with severity, owner, evidence paths, and recommended route
- next recommended action for the operator

`POST /api/builder/project-status` reuses the same alignment artifact when a session id is supplied instead of recomputing an unrelated action list.

## Prompt Artifacts

Generated artifacts:

- `dev_tracker/ui/public/generated/context_pack_v1.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/prompt_context_v1.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/prompt_bundle.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/prompt_bundle.md`
- `Harness/artifacts/control/discovery_sessions/<session_id>/template_fill_map.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/template_fill_map.md`
- `Harness/artifacts/control/discovery_sessions/<session_id>/bootstrap_prompt.md`
- `Harness/artifacts/control/discovery_sessions/<session_id>/phase_plan.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/phase_plan.md`
- `Harness/artifacts/control/discovery_sessions/<session_id>/execution_prompts.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/execution_prompts.md`
- `Harness/artifacts/control/discovery_sessions/<session_id>/alignment_state.json`
- `Harness/artifacts/control/discovery_sessions/<session_id>/alignment_state.md`

Release automation note:

- interactive operator sessions still treat the discovery-session paths above as the canonical artifact contract
- `make release-check` may run those sessions in isolated temporary control roots, so the proof runners snapshot durable copies under `public_audit/release_evidence_excluded/<report_name>/` before cleanup
- release reports must reference the durable snapshot paths, not temporary control-root paths
- those retained proof bundles are manager-only evidence and are excluded from downstream harness capture

`context_pack_v1.json` is intentionally compact and stores summaries, not raw markdown bodies:

- template manifest
- service inventory summary
- route inventory summary
- active guidance anchors
- key doc anchors

## Prompt Caching

Hosted prompt caching hooks are currently applied only to the OpenAI adapter:

- `OPENAI_PROMPT_CACHE_ENABLED` default `true`
- `OPENAI_PROMPT_CACHE_RETENTION` default `24h`
- generated `prompt_cache_key` is session/model scoped

CLI providers are unchanged and do not use hosted prompt caching.

## Existing Project Contracts

### `POST /api/builder/project-scan`

Request:

- `target_repo`
- optional `session_id`
- optional `target_mode`
- optional `remote_target`
- optional `scan_limits`

Response extends `ProjectBaselineScanV1` with:

- `target_mode`
- `remote_target`
- optional artifact paths

### `POST /api/builder/deploy-existing`

Request:

- `session_id`
- `target_repo`
- `mode=sidecar`
- optional `target_mode`
- optional `remote_target`
- optional `sidecar_dir`
- optional overwrite controls
- optional critical gap policy and override fields

Response includes:

- `target_mode`
- `remote_target`
- `template_fill_map_artifact_paths`
- `status_route`

### `POST /api/builder/project-status`

Request:

- `target_repo`
- optional `session_id`
- optional `target_mode`
- optional `remote_target`

Response includes:

- `target_mode`
- `remote_target`
- `target_path`
- critical-first action queue
- domain health
- persisted history metadata

### `GET /api/builder/project-status/history`

Request:

- `target_repo`
- optional `target_mode`
- optional JSON-encoded `remote_target`
- optional `limit`

## Assistant Run Contract

`POST /api/assistant/run`

Request:

- `assistant: codex_cli | claude_code`
- `source_mode: builder | review | project_status | docs`
- `prompt`
- optional `session_id`
- optional `target_repo`

Response:

- `run_id`
- `status`
- `stdout`
- `stderr`
- `exit_code`
- artifact paths for JSON and Markdown logs

Artifacts are written under:

- `Harness/artifacts/control/assistant_runs/`

If the configured assistant command is unavailable on the Linux host, the endpoint fails with `assistant_command_missing`.

## Environment Controls

- `BUILDER_ALLOWLIST_ROOT`
- `BUILDER_CONTROL_ROOT`
- `BUILDER_DISCOVERY_DOCS_ROOT`
- `BUILDER_PATH_DISCLOSURE_MODE`
- `BUILDER_REMOTE_SSH_ENABLED`
- `BUILDER_REMOTE_SSH_ALLOWED_COMMANDS`
- `BUILDER_EXISTING_PROJECT_MODE`
- `BUILDER_SCAN_MAX_DEPTH`
- `BUILDER_SCAN_MAX_FILES`
- `BUILDER_PROJECT_STATUS_HISTORY_MAX_ENTRIES`
- `TRACKER_TRUSTED_ORIGINS`
- `TRACKER_API_TRUSTED_ORIGINS`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_PROMPT_CACHE_ENABLED`
- `OPENAI_PROMPT_CACHE_RETENTION`
- `CODEX_CLI_COMMAND`
- `CODEX_CLI_ARGS`
- `CLAUDE_CODE_COMMAND`
- `CLAUDE_CODE_ARGS`

trusted origins are enforced on every API request before builder or discovery routes execute.
