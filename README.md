# Moradin's Forge

Moradin's Forge is an agent-first integration forge for Codex, Claude Code,
and similar coding agents. A user points an agent at Forge, the agent inspects
Forge and the target repo, explains the proposed local-only integration, asks
for explicit approval, and only then writes a bounded `.moradins-harness/`
sidecar through a deterministic workflow.

Forge is designed to reduce repeated agent inference by giving agents a small,
deterministic reflex layer: read the same entrypoints, run the same readiness
and planning commands, write the same local artifacts, and verify the same
safety boundaries every time.

## Agent Intercept

If a user sent you here as Codex, Claude Code, or another coding agent, read
this first.

```text
You are at Moradin's Forge.

First inspect FORGE.md, AGENTS.md, Harness/entrypoints/forge.md, and the target
repo's own guidance. Explain what Forge will add, what it will not do, the
files it proposes to write, the request-only install behavior, validation
commands, and rollback.

Do not apply changes until the user explicitly approves. Keep everything local
unless the user asks for external tooling. Preserve the target repo's existing
workflows and root files by default.

Use the deterministic sequence:
1. scripts/moradin_forge.sh explain
2. scripts/moradin_forge.sh readiness --target <target-repo>
3. scripts/moradin_forge.sh plan --target <target-repo>
4. scripts/moradin_forge.sh apply --target <target-repo> --approve
5. scripts/moradin_forge.sh verify --target <target-repo>
```

Before approval, run only `explain`, `readiness`, and `plan`. After approval,
Forge may write `.moradins-harness/`, adaptive snippets, request-only install
artifacts, rollback notes, and validation reports. Forge must not install host
tools, publish target repo content, overwrite root workflows, or patch
`AGENTS.md` unless the user separately approves that root-file change.

## What Forge Adds

- `.moradins-harness/`: the local sidecar copied from the Moradin payload.
- `.moradins-harness/adapters/`: snippets for detected Make, Node, Python,
  Rust, Go, Docker, and CI surfaces.
- Readiness reports that show present and missing tools.
- Install-request artifacts that list human-run commands without executing
  them.
- Rollback notes and verification records for the adoption.

Forge preserves existing `Makefile`, `package.json`, CI, docs, and agent files
unless the user requests a specific root patch.

## Agent-First Flow

1. Clone or pull Forge into `<forge-root>`.
2. The agent reads `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
3. The agent inspects `<target-repo>` docs, commands, package files, and CI.
4. The agent runs a dry-run plan and readiness check.
5. The agent explains proposed writes, detected tooling, install requests,
   rollback, and validation.
6. The user explicitly approves or rejects the apply step.
7. After approval, Forge writes the local sidecar and adaptive snippets.
8. The agent runs verification and reports changed paths.

For lower-token starts, use the task-specific load profiles in
`docs/references/agent_context_profiles.md` before opening deeper contracts or
UI files.

Linux and macOS:

```sh
scripts/moradin_forge.sh explain
scripts/moradin_forge.sh readiness --target <target-repo>
scripts/moradin_forge.sh plan --target <target-repo>
scripts/moradin_forge.sh apply --target <target-repo> --approve
scripts/moradin_forge.sh verify --target <target-repo>
```

Windows PowerShell:

```powershell
.\scripts\moradin_forge.ps1 explain
.\scripts\moradin_forge.ps1 readiness --target <target-repo>
.\scripts\moradin_forge.ps1 plan --target <target-repo>
.\scripts\moradin_forge.ps1 apply --target <target-repo> --approve
.\scripts\moradin_forge.ps1 verify --target <target-repo>
```

Root repo patching is off by default. To add a marked Moradin block to a target
`AGENTS.md`, the user must approve both the apply step and `--patch-agents`.

## Public Command Surface

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

`make public-portability-check` is the public release hygiene gate. It creates a
sanitized check tree, runs a sidecar smoke test, and scans both outputs for
host-specific paths, generated evidence, and portability failures.

## Optional Workbench

The browser workbench is secondary. It remains useful for diagnostics,
readiness review, repo registry views, and deploy-state inspection.

```sh
npm --prefix dev_tracker/ui install
./harness_devops.sh --port <workbench-port>
```

Use local browser access, WSL browser access, or SSH local forwarding. Keep the
workbench loopback-only unless the user explicitly asks for broader exposure.

## Key Contracts

- Moradin payload contract: `docs/references/moradin_payload_contract_v1.md`
- Agent context profiles:
  `docs/references/agent_context_profiles.md`
- Forge agent integration contract:
  `docs/references/moradin_forge_agent_integration_contract_v1.md`
- Public portability contract:
  `docs/references/moradin_forge_public_export_contract_v1.md`
- Agent handoff prompt:
  `Harness/entrypoints/forge_agent_handoff.md`
- Tooling readiness contract:
  `docs/references/tooling_readiness_install_request_contract_v1.md`
- Repo registry contract:
  `docs/references/repo_registry_adapter_contract_v1.md`
- Repo operating model:
  `docs/references/repo_operating_model_v1.md`

## Development Gates

Use the shortest repo-native gate that matches the change:

- `make test`
- `make forge-smoke`
- `make payload-validate`
- `make payload-smoke`
- `make public-portability-check`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
- `npm --prefix dev_tracker/ui audit --audit-level=moderate`

Public releases should pass all gates, GitHub Actions, and a fresh sidecar smoke
against a disposable target repo.
