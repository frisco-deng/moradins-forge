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
- `docs/references/agent_context_profiles.md`
- `Harness/entrypoints/forge.md`
- `Harness/entrypoints/forge_agent_handoff.md`
- `Harness/entrypoints/agent.md`
- `Harness/moradin_payload/manifest.yaml`
- `docs/references/moradin_payload_contract_v1.md`
- `docs/references/moradin_forge_agent_integration_contract_v1.md`
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
- Preserve existing target repo workflows and root files by default.
- Generate adaptive snippets under `.moradins-harness/adapters/`.
- Patch a target root `AGENTS.md` only when the user approves `--patch-agents`.

## Deterministic Commands

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

Use repo-local commands before ad hoc shell chains. If a target repo has its own
`AGENTS.md`, `CONTRIBUTING.md`, Makefile, package scripts, or CI docs, treat
those as the target repo's source of truth.

## Operating Rules

- Treat this public repo as the active product source for normal Forge work.
- Create feature, docs, fix, and release branches from public `main`.
- Use `docs/references/agent_context_profiles.md` to choose the smallest
  task-specific context profile before loading deeper contracts.
- Keep compatibility language out of first-read docs; compatibility details
  belong in contracts and payload manifests.
- `Harness/moradin_payload/manifest.yaml` is the canonical sidecar payload
  contract.
- `FORGE.md` and `Harness/entrypoints/forge.md` are the canonical agent-first
  adoption entrypoints.
- The browser UI is optional diagnostics, not the primary install path.
- Before public PRs or releases, run `make public-portability-check` and the
  deterministic gates listed in `docs/references/repo_operating_model_v1.md`.

## Secure Coding Baseline

- Never commit secrets, tokens, local credentials, host-specific paths, or
  generated local evidence.
- Treat target repos and generated artifacts as untrusted until validated.
- Keep dependencies and generated payload changes tightly scoped and justified.
- Do not publish, upload, or expose user repo contents from Forge.

## Docs And Git Hygiene

- Document behavior changes in the relevant contract or runbook.
- Keep public-facing docs generic: use `<forge-root>`, `<target-repo>`,
  `<temp-dir>`, and `<workbench-port>` placeholders.
- Use descriptive commit messages and ISO 8601 dates (`YYYY-MM-DD`) when dates
  matter.
- Do not merge or promote protected branches without the required human gate.

## When Uncertain

- Stop at the dry-run plan only when cross-repository target adoption remains
  unapproved. For an accepted target and plan, continue authorized reversible
  apply, validation, rollback preparation, and review work.
- If a change affects long-lived architecture or path contracts, update the
  appropriate contract before treating the behavior as stable.

<!-- tpl:portable-guidance -->

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
  or use this file's outcome checklist, before voluntary closeout.
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
  skill. Delegation stays off unless I explicitly request it.
- In a standalone copy, do not depend on a sibling `.templates` checkout.
  Before handoff, list every accepted outcome, its evidence, remaining
  authorized work, and any exact operator dependency.

<!-- tpl:quality-review-v1 -->

- Consequential changes need inspected assumptions, independent evidence, and
  one bounded false-pass check. Profiles are review candidates, not gates.
- Reread effective policy after a policy change. Compaction is continuity, not
  completion. Keep hooks retired and delegation request-only.

Portable first route: `make forge-readiness`.
Portable policy reference: `FORGE.md`.

<!-- tpl:repo-followthrough:end -->

<!-- tpl:repo-navigation:start -->

## Files And CLI Progress

Before adding or moving a file, read this project's README and inspect its
existing layout. Keep file purpose and ownership clear; use a rendered
folder contract only when one is present in this copy.

For a long-running CLI, reuse the project's own progress convention.
Keep transient progress on stderr and final results on stdout; do not
require a sibling workspace checkout.

<!-- tpl:repo-navigation:end -->
