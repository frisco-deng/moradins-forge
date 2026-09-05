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
- `docs/references/repo_operating_model_v1.md`
- `docs/references/tooling_readiness_install_request_contract_v1.md`
- `Harness/README.md`

## Agent Adoption Rules

- Inspect Forge and the target repo before proposing changes.
- Explain benefits, risks, proposed writes, rollback, install requests, and
  validation before apply.
- Ask for explicit user consent before mutating a target repo.
- Keep adoption local unless the user explicitly requests external tooling.
- Do not run host install commands; write request-only install artifacts instead.
- Treat installer bootstrap as repo priming only; it must not run Forge `apply`
  or mutate a target repo.
- Preserve existing target repo workflows and root files by default.
- Generate adaptive snippets under `.moradins-harness/adapters/`.
- Patch a target root `AGENTS.md` only when the user approves `--patch-agents`.

## Deterministic Commands

- `make repo-brief`
- `make verify-paths`
- `make verify-fast`
- `make verify-security`
- `make review-ready`
- `make push-gate`
- `make forge-explain`
- `make forge-readiness`
- `make forge-plan TARGET=<target-repo>`
- `make forge-adopt TARGET=<target-repo> APPROVE=1`
- `make forge-verify TARGET=<target-repo>`
- `make forge-smoke`
- `make payload-validate`
- `make payload-smoke`
- `make public-portability-check`
- `make test`
- `install/bootstrap-linux.sh --dry-run --json`

Use repo-local commands before ad hoc shell chains. If a target repo has its own
`AGENTS.md`, `CONTRIBUTING.md`, Makefile, package scripts, or CI docs, treat
those as the target repo's source of truth.

## Baseline Workflow

- Start Forge maintenance with `make repo-brief` before broad exploration.
- Run `tpl context-primer --latest-session --repo moradins-forge` after session
  start, compaction, long resume, or repeated broad reads.
- Use the Python runtime route reported by `make repo-brief`; this repo is a
  `uv` project and raw `python` is not the runtime contract.
- Run `tpl session-supervisor --live --latest-session --repo moradins-forge`
  when a session starts polling, rereading the same evidence, or patching
  through the same failure.
- Use `tpl session-checkpoint` and `tpl investigation-ledger` before another
  patch/full rerun when the same failure repeats.
- Run `tpl rerun-advice moradins-forge -- <command>` before repeating
  deterministic commands or re-ingesting long logs.
- Run `tpl-ui-review-brief --repo moradins-forge --mode auto --prompt <prompt>`
  before UI page creation, component additions, existing-surface refinements,
  screenshot critiques, or formatting/readability fixes.
- Use `make verify-paths` before public docs, generated sidecars, export
  outputs, or release-facing evidence leave the repo.

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
- Keep release candidate, Windows Sandbox/native readiness, macOS signing, WSL
  smoke, and GPU helper lanes documented but not rendered as default Forge
  targets until Forge has real release artifacts and evidence contracts.
- Do not add release-platform readiness until Forge has a stable release
  artifact path, build summary, SBOM/security evidence, signing or smoke
  evidence, and release-candidate manifest.
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
