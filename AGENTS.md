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

Use repo-local commands before ad hoc shell chains. If a target repo has its own
`AGENTS.md`, `CONTRIBUTING.md`, Makefile, package scripts, or CI docs, treat
those as the target repo's source of truth.

## Baseline Workflow

- Start Forge maintenance with `make repo-brief` before broad exploration.
- Run `tpl context-primer --latest-session --repo moradins-forge` after session
  start, compaction, long resume, or repeated broad reads.
- Run `tpl session-supervisor --live --latest-session --repo moradins-forge`
  when a session starts polling, rereading the same evidence, or patching
  through the same failure.
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
- Do not add release-platform readiness until Forge has a stable release
  artifact path, build summary, SBOM/security evidence, signing or smoke
  evidence, and release-candidate manifest.
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
