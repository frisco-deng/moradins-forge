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
- Ask for explicit user consent only before adopting or mutating a target repo
  outside the target scope already accepted in the current task. Once the target
  and plan are accepted, continue authorized reversible work through validation
  and review.
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

- Stop at the dry-run plan only when cross-repository target adoption remains
  unapproved. For an accepted target and plan, continue authorized reversible
  apply, validation, rollback preparation, and review work.
- If a change affects long-lived architecture or path contracts, update the
  appropriate contract before treating the behavior as stable.

<!-- tpl:repo-followthrough:start -->

## Scoped Execution And Completion

Policy version: `repo-completion-v9-2026-09-25`.
Repository-specific security, data, integration, and promotion restrictions
remain authoritative within the task.

- Action requests mean finish, not acknowledgment of capability; honor
  planning-only requests. Keep accepted outcomes across checkpoints. An
  intermediate milestone or tests do not prove a requested
  practical run; require observed acceptance evidence.
- Accepted plans include reversible gate repair, preservation, and review-branch
  publication. For multi-step work run the installed completion/handoff check,
  or use the linked policy's manual checklist, before voluntary closeout.
- If effective user policy activates a native Goal, bind its ignored v3 manifest
  before mutation and keep it active across turns and compaction. Continue
  independent authorized work behind scoped blockers; investigate unknowns.
- A plan does not itself grant live-action authority. Prepare exact approvals
  for live, security, and promotion gates while continuing other work.
- Whole-task blocked wait requires the same exact blocker across three Goal
  turns, every remaining outcome affected, and no independent action left.
  Otherwise continue. A justified wait names the outcome, evidence, owner,
  alternatives, next action, and completion proof. Do not invent approvals.
- Reuse unchanged evidence. Add or repeat a check only for a native gate,
  changed behavior, or a named uncertainty; do not add generic stopping points.
- Native security and promotion gates bind. Higher-priority instructions beat a
  skill. Delegation stays off unless I explicitly request it in the
  current prompt.

<!-- tpl:quality-review-v1 -->

- Consequential changes need inspected assumptions, independent evidence, and
  one bounded false-pass check. Profiles are review candidates, not gates.
- Reread effective policy after a policy change. Compaction is continuity, not
  completion. Keep hooks retired and delegation request-only.

First policy/state route (from the project root):
`../../.templates/scripts/tpl context-primer --policy-refresh --repo-root .`.
Shared policy reference:
`../../.templates/docs/observability/task_completion_policy.md`.

<!-- tpl:repo-followthrough:end -->
