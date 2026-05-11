# Moradin's Forge

## Agent Intercept

If a user sent you here as Codex, Claude Code, or another coding agent, read
this first. Forge is an agent-first local integration kit. Your job is to
inspect Forge and the target repo, explain the proposed integration, and ask for
explicit approval before changing anything.

Copy this prompt into the active agent session when starting from Forge:

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

Before approval, run only explain, readiness, and plan. After approval, Forge
may write `.moradins-harness/`, adaptive snippets, request-only install
artifacts, rollback notes, and validation reports. Forge must not install host
tools, publish target repo content, overwrite root workflows, or patch
`AGENTS.md` unless the user separately approves that root-file change.

Moradin's Forge is an agent-first local integration kit for coding agents. A
user points Codex, Claude Code, or another coding agent at this repo; the agent
inspects Forge and the target repo, explains the proposed integration, asks for
explicit consent, and only then applies a bounded local sidecar.

Forge is local by default. It does not install host tools, publish repo content,
replace existing workflows, or require the browser workbench.

## Agent-First Flow

1. Clone or pull Forge into a local `<forge-root>`.
2. The agent reads `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
3. The agent inspects `<target-repo>` docs, commands, package files, and CI.
4. The agent runs a dry-run plan and readiness check.
5. The agent explains proposed writes, detected tooling, install requests,
   rollback, and validation.
6. The user explicitly approves or rejects the apply step.
7. After approval, Forge writes `.moradins-harness/` and adaptive snippets under
   `.moradins-harness/adapters/`.

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

Root repo patching is off by default. To add a marked Moradin block to an
existing target `AGENTS.md`, the user must approve the apply step and the agent
must pass `--patch-agents`.

## What Forge Writes

- `.moradins-harness/`: the local sidecar copied from the Moradin payload.
- `.moradins-harness/adapters/`: adaptive snippets for detected Make, Node,
  Python, Rust, Go, Docker, and CI surfaces.
- `.moradins-harness/Harness/artifacts/control/forge_integration/`: integration
  records and rollback notes.
- Optional install-request artifacts that list human-run commands for missing
  tools without executing them.

Forge preserves existing `Makefile`, `package.json`, CI, docs, and agent files
unless the user later requests a specific root patch.

## Portable Command Surface

- `make forge-explain`
- `make forge-readiness`
- `make forge-plan TARGET=<target-repo>`
- `make forge-adopt TARGET=<target-repo> APPROVE=1`
- `make forge-verify TARGET=<target-repo>`
- `make forge-smoke`
- `make payload-validate`
- `make payload-smoke`
- `make public-export`
- `make public-portability-check`
- `make test`

Compatibility aliases such as `template-validate` and `template-smoke` remain
for one migration window, but Moradin payload language is canonical.

## Public Export

This private staging repo can generate a fresh public export without rewriting
its own history:

```sh
make public-export PUBLIC_EXPORT_DIR=<public-repo-dir>
make public-portability-check PUBLIC_EXPORT_DIR=<public-repo-dir>
```

The export pipeline writes a clean tree, strips manager-only artifacts, scans
for private path references, initializes a fresh git repo, and creates one
initial commit. Generated audit reports live under
`<public-repo-dir>/public_audit/`.

Excluded from public exports and downstream sidecars:

- prior git history,
- release evidence,
- branch waivers,
- PR hardening artifacts,
- generated discovery sessions,
- local screenshots and caches,
- manager-only migration artifacts,
- absolute local workspace paths.

## Optional Workbench

The browser workbench is secondary. It remains useful for diagnostics,
readiness review, repo registry views, and deploy-state inspection.

```sh
npm --prefix dev_tracker/ui install
./harness_devops.sh --port <workbench-port>
```

For the existing-project sandbox review path, use `make sandbox-ui`.

Use local browser access, WSL browser access, or SSH local forwarding. Keep the
workbench loopback-only unless the user explicitly asks for broader exposure.

## Key Contracts

- Moradin payload contract: `docs/references/moradin_payload_contract_v1.md`
- Forge agent integration contract:
  `docs/references/moradin_forge_agent_integration_contract_v1.md`
- Public export and portability contract:
  `docs/references/moradin_forge_public_export_contract_v1.md`
- Agent handoff prompt:
  `Harness/entrypoints/forge_agent_handoff.md`
- Tooling readiness contract:
  `docs/references/tooling_readiness_install_request_contract_v1.md`
- Repo registry contract:
  `docs/references/repo_registry_adapter_contract_v1.md`
- Assistant handoff contract:
  `docs/references/assistant_handoff_contract_v1.md`

## Development Gates

Use the shortest repo-native gate that matches the change:

- `make test`
- `make forge-smoke`
- `make payload-validate`
- `make public-portability-check`
- `make verify-fast`
- `make verify`
- `make verify-security`
- `make review-ready`
- `make release-check`

Security and review gates may require project-specific human governance before
merge or release. Public export hardening does not grant authority to bypass
those gates.
