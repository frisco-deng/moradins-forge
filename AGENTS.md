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
- Ask for explicit user consent before mutating a target repo.
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

- Stop at the dry-run plan and ask the user before applying changes.
- If a change affects long-lived architecture or path contracts, update the
  appropriate contract before treating the behavior as stable.

<!-- tpl:portable-guidance -->

<!-- tpl:repo-followthrough:start -->

## Scoped Execution And Completion

Policy version: `repo-completion-v8-2026-09-24`.
Repository-specific security, data, integration, and promotion restrictions
remain authoritative within the task.

- Treat action requests as work to finish, not an acknowledgment of capability;
  honor planning-only requests. Keep accepted outcomes across side questions
  and checkpoints. An intermediate milestone, tests, or a review packet is not
  proof of a requested practical run; require observed acceptance evidence.
- Accepted-plan implementation includes reversible gate repair, preservation,
  and review publication without renewed questions. Native gates still apply.
- For a multi-step task or accepted plan, check the full outcome list before
  voluntary closeout. Use the installed deck's completion/handoff check when
  available; otherwise use this file's outcome checklist.
  Continue authorized work behind scoped blockers; investigate unknown inputs
  before asking the user.
- Before promising a live run, identify its exact approvals and their current
  evidence. Prepare the reviewable decision first. A plan does not itself grant
  live-action authority; preserve project security and promotion gates.
- If no authorized useful action remains, report the exact affected outcome,
  missing input or rule, attempted versus proposed alternatives, owner, next
  action, and completion proof. Do not invent approvals or retry uncertain
  mutations. Higher-priority instructions and native rules win over a skill.
- Reuse unchanged evidence. Add or repeat a check only for a native gate,
  changed behavior, or a named uncertainty; do not add generic stopping points.
- In a standalone copy, do not depend on a sibling `.templates` checkout.
  Before handoff, list every accepted outcome, its evidence, remaining
  authorized work, and any exact operator dependency.

<!-- tpl:quality-review-v1 -->

- For consequential changes, inspect assumptions and use independent outcome
  evidence plus one bounded false-pass check. Unknown review coverage is not
  success; project profiles are review candidates, not automatic gates.
- Start or resume in the owning project root and reread its effective policy
  after a policy change. Linked Markdown is not automatically loaded by Codex.
  Keep hooks retired; do not delegate unless I explicitly request it in the
  current prompt.

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
