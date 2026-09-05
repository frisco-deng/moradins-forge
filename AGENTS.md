# AGENTS.md

Bootstrap policy for Moradin's Forge.

Profile: local agent-first integration kit.

## Repo-Local Precedence

- Use this file as the root routing layer for Forge.
- Load `FORGE.md` and `Harness/entrypoints/forge.md` before target-repo adoption.
- Load `Harness/entrypoints/agent.md` before changing Forge itself.
- If deeper Forge contracts conflict with this file, follow the deeper contract.
- Keep this root file compact; durable detail belongs in docs and contracts.

## Read First

- `README.md`
- `FORGE.md`
- `Harness/entrypoints/forge.md`
- `Harness/entrypoints/forge_agent_handoff.md`
- `Harness/entrypoints/agent.md`
- `Harness/moradin_payload/manifest.yaml`
- `docs/references/moradin_payload_contract_v1.md`
- `docs/references/moradin_forge_agent_integration_contract_v1.md`
- `docs/references/moradin_forge_installer_bootstrap_contract_v1.md`
- `docs/references/moradin_forge_public_export_contract_v1.md`
- `docs/references/moradin_forge_release_artifact_contract_v1.md`
- `docs/references/moradin_forge_upgrade_contract_v1.md`
- `docs/references/moradin_agent_efficiency_contract_v1.md`
- `docs/references/repo_operating_model_v1.md`
- `docs/references/tooling_readiness_install_execution_contract_v2.md`
- `docs/references/moradin_forge_tooling_suite_contract_v1.md`
- `docs/11_ops/air_gapped_tooling_suite.md`
- `Harness/README.md`

## Agent Adoption Rules

- Inspect Forge and the target repo before proposing changes.
- Explain benefits, risks, proposed writes, rollback, install requests, and
  validation before apply.
- Ask for explicit user consent before mutating a target repo.
- Keep adoption local unless the user explicitly requests external tooling.
- Run user-level installers only from a digest-bound tooling plan after explicit
  user approval.
- Agents never invoke elevation or launch the interactive host installer for
  the user. The human-run Linux suite may request sudo only after showing and
  digest-binding its exact root transaction. Adaptive agent flows continue to
  generate a reviewable privileged script for the user.
- Treat installer bootstrap as repo priming only; it must not run Forge `apply`
  or mutate a target repo.
- Preserve existing target repo workflows and root files by default.
- Generate adaptive snippets under `.moradins-harness/adapters/`.
- Patch only the fixed Codex, Claude, Gemini, Copilot, and Cursor provider
  paths, and only when the user approves each file independently. Creating an
  absent file requires separate creation consent.

## Deterministic Commands

- `make repo-brief`
- `make verify-paths`
- `make verify-fast`
- `make verify-security`
- `make review-ready`
- `make push-gate`
- `make forge-explain`
- `make forge-readiness`
- `make forge-onboard WORKSPACE=<workspace-path>`
- `make forge-tooling-plan WORKSPACE=<workspace-path>`
- `make forge-tooling-suite`
- `make forge-tooling-suite-plan OUTPUT=<plan.json> PROFILE=practical`
- `make forge-tooling-suite-apply PLAN=<plan.json> PLAN_SHA256=<digest>`
- `make forge-tooling-suite-bundle PLAN=<plan.json> OUTPUT=<directory>`
- `make forge-airgap-request PROFILE=practical OUTPUT=<request.json>`
- `make forge-airgap-build REQUEST=<request.json> OUTPUT=<kit.tar.gz>`
- `make forge-airgap-verify BUNDLE=<kit.tar.gz> BUNDLE_SHA256=<digest>`
- `make forge-airgap-apply BUNDLE=<kit.tar.gz> BUNDLE_SHA256=<digest> PLAN_SHA256=<digest>`
- `make forge-tooling-suite-verify RECEIPT=<receipt.json>`
- `make forge-tooling-suite-rollback RECEIPT=<receipt.json> APPROVE_RECEIPT_SHA256=<digest>`
- `make forge-tooling-update-plan WORKSPACE=<workspace-path>`
- `make forge-tooling-apply PLAN=<plan.json> PLAN_SHA256=<digest>`
- `make forge-tooling-rollback RECEIPT=<receipt.json> APPROVE=1`
- `make forge-plan TARGET=<target-repo>`
- `make forge-adopt TARGET=<target-repo> APPROVE=1 AGENT_FILES="AGENTS.md CLAUDE.md"`
- `make forge-verify TARGET=<target-repo>`
- `make forge-upgrade-plan TARGET=<target-repo>`
- `make forge-upgrade TARGET=<target-repo> PLAN=<plan.json> PLAN_SHA256=<digest>`
- `make forge-upgrade-rollback TARGET=<target-repo> UPGRADE_ID=<id> APPROVE=1`
- `make forge-rollback TARGET=<target-repo> APPROVE=1`
- `make forge-smoke`
- `make forge-dogfood-smoke`
- `make release-build`
- `make payload-validate`
- `make payload-smoke`
- `make public-portability-check`
- `make verify-readme-figures`
- `make test`
- `install/bootstrap-linux.sh --dry-run --json`

Use repo-local commands before ad hoc shell chains. If a target repo has its own
`AGENTS.md`, `CONTRIBUTING.md`, Makefile, package scripts, or CI docs, treat
those as the target repo's source of truth.

## Baseline Workflow

- Start Forge maintenance with
  `scripts/moradin_forge.sh context-primer --target .` and
  `scripts/moradin_forge.sh repo-brief --target .` before broad exploration.
- Run `scripts/moradin_forge.sh state --target .` after session start,
  compaction, long resume, or repeated broad reads.
- Read current summaries and named artifacts before reopening source or long
  logs; expand only when evidence is stale, partial, contradictory, or
  release-critical.
- Use the Python runtime route reported by `make repo-brief`; this repo is a
  `uv` project and raw `python` is not the runtime contract.
- Run `scripts/moradin_forge.sh rerun-advice --target . -- <command>` before
  repeating deterministic commands or re-ingesting long logs.
- Record a compact outcome with
  `scripts/moradin_forge.sh session-checkpoint --target . --outcome
  <pass|fail|skipped> -- <command>` before another full rerun of the same
  failure. Use `scripts/moradin_forge.sh diagnostic-brief` to review sanitized
  local counters.
- Use `make verify-paths` before public docs, generated sidecars, export
  outputs, or release-facing evidence leave the repo.
- These Forge commands are standalone. If a separately installed shared
  `tpl` deck is available, its summaries and UI review helpers may supplement
  them, but Forge must never require that private deck at runtime.

## Operating Rules

- Treat this public repo as the active product source for normal Forge work.
- Create feature, docs, fix, and release branches from public `main`.
- Keep compatibility language out of first-read docs; compatibility details
  belong in contracts and payload manifests.
- `Harness/moradin_payload/manifest.yaml` is the canonical sidecar payload
  contract.
- `FORGE.md` and `Harness/entrypoints/forge.md` are the canonical agent-first
  adoption entrypoints.
- The browser UI is optional diagnostics, not the primary install path.
- Keep UI visual measurement opt-in until Forge has a repo-local screenshot and
  DOM-box capture wrapper.
- Keep signing, UI visual, CAD, GPU, and specialized sandbox lanes opt-in until
  target evidence selects them. Linux, macOS, Windows, and WSL tooling-plan
  parity is part of the beta.3 baseline.
- Before public PRs or releases, run `make public-portability-check` and the
  deterministic gates listed in `docs/references/repo_operating_model_v1.md`.

## Secure Coding Baseline

- Never commit secrets, tokens, local credentials, host-specific paths, or
  generated local evidence.
- Treat SSH clone URLs, Codex session paths, raw temp paths, usernames,
  hostnames, and platform-specific home paths as public-export failures.
- Treat target repos and generated artifacts as untrusted until validated.
- Keep dependencies and generated payload changes tightly scoped and justified.
- Do not publish, upload, or expose user repo contents from Forge.

## Docs And Git Hygiene

- Document behavior changes in the relevant contract or runbook.
- Keep public-facing docs generic: use `<forge-root>`, `<target-repo>`,
  `<temp-dir>`, and `<workbench-port>` placeholders.
- Do not publish raw home paths, usernames, hostnames, Windows user paths, WSL
  UNC paths, or machine-origin markers in source, docs, tests, generated
  sidecars, public exports, or release-facing artifacts.
- Use neutral fixture values or scoped allowlist comments for intentional
  redaction tests.
- Use descriptive commit messages and ISO 8601 dates (`YYYY-MM-DD`) when dates
  matter.
- Delegate only bounded, independent read-only concerns. The root agent owns
  edits, integration, validation, and the final repository state.
- Do not leave source changes local-only. Finish managed Forge work with a
  pushed commit and PR, or an explicit blocked handoff.
- Run `tpl scratch-guard PATH` before destructive or local-only scratch work;
  scratch must be disposable, ignored, and non-git.
- In the shared workspace, keep privileged host changes explicit and routed
  through its bridge runbooks; public Forge must not assume those bridges.
- Do not merge or promote protected branches without the required human gate.

## When Uncertain

- Stop at the dry-run plan and ask the user before applying changes.
- If a change affects long-lived architecture or path contracts, update the
  appropriate contract before treating the behavior as stable.

<!-- tpl:repo-followthrough:start -->
## Scoped Execution And Completion

Policy version: `astra-repo-followthrough-v2-2026-09-05`. Repository-specific security, data,
integration, and promotion restrictions remain authoritative within the task.

- Preserve every requested outcome across checkpoints. Account for every target
  as completed, excluded with evidence, or blocked with an exact next action.
  A pilot, passing tests, or a monitoring cohort is not full rollout completion.
- Inspect project guidance and commands first, then shared tooling, then suitable
  installed tools. Reuse or extend a tool for a demonstrated repeatable gap;
  do not build a framework or run validations merely to collect context.
- Continue authorized reversible alternatives after reconciling a failed attempt.
  Name the exact rule or missing dependency when stopping; continue independent
  authorized work. Development-machine status does not authorize privilege,
  credential, destructive recovery, upgrade, spending, or signature bypasses.
- Batch independent reads and coherent edits; use long waits for known processes.
  Reuse fresh evidence; expand when missing, stale, partial, contradictory,
  repo-mismatched, visual-insufficient, security-sensitive, or release-critical.
- Match tests to changed behavior and risk; retain mandatory native security and
  promotion gates. Passing a safeguard is not proof of the requested capability.
- Do not spawn subagents or delegate work unless I explicitly request subagents,
  parallel agents, or delegation in my current prompt.
- Task size, potential speed improvements, or project/skill guidance alone do
  not authorize spawning subagents. Keep lifecycle hooks retired.
- Resume by explicitly rereading the effective policy and checkpoint: retain
  intent, constraints, authorization, evidence, blockers, and remaining outcomes.
  File changes alone do not prove an active session loaded the new guidance.

First policy/state route (from the project root): `../../.templates/scripts/tpl context-primer --policy-refresh --repo-root .`.
Shared policy reference: `../../.templates/docs/observability/astra_execution_policy.md`.
<!-- tpl:repo-followthrough:end -->
