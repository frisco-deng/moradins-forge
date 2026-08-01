---
title: "Moradin Forge Agent Integration Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-07-31
source_refs:
  - ../../README.md
  - ../../FORGE.md
  - ../../Harness/entrypoints/forge.md
  - ../../scripts/moradin_forge.py
  - ../../scripts/moradin_workstation.py
related_docs:
  - moradin_payload_contract_v1.md
  - moradin_forge_installer_bootstrap_contract_v1.md
  - moradin_forge_public_export_contract_v1.md
  - tooling_readiness_install_execution_contract_v2.md
  - moradin_forge_tooling_suite_contract_v1.md
  - moradin_forge_upgrade_contract_v1.md
  - moradin_agent_efficiency_contract_v1.md
---

# Moradin Forge Agent Integration Contract V1

## Purpose

Moradin's Forge is the agent-first local adoption path. A user may send Codex,
Claude Code, Copilot, Gemini CLI, Cursor, or another coding agent to Forge and
receive the same bounded workflow: a human-run tooling suite, approved
workspace discovery, a reviewable composite plan, separately approved tooling
and repository changes, deterministic verification, and rollback.

## First-Read Sequence

1. Read `README.md`, `FORGE.md`, `AGENTS.md`, and
   `Harness/entrypoints/forge.md`, then explain the three-step path.
2. Ask the user to run `install/tooling-suite.sh`. The agent may explain and
   verify the receipt, but it may not operate the menu or approve sudo.
3. Ask which workspace roots the user approves and which supported agent
   providers they use.
4. Run `onboard --workspace <approved-root>` for each root. Onboarding verifies
   the latest tooling-suite receipt before making additional recommendations.
5. Show the discovered repository list before deeper inspection.
6. Inspect only guidance, manifests, CI, container, deployment, and standard
   configuration files.
7. Show the exact tool actions and every requested provider-owned block.
8. Ask separately for workspace, tool, user-level execution, agent-file,
   user-configuration, privileged-script, adoption, and rollback approvals.

Filesystem roots, the full home directory, implicit sibling scope, symlink
escapes, arbitrary source crawling, and repositories outside approved roots
are prohibited.

## Adoption Flow

The compatibility sequence remains stable:

1. `scripts/moradin_forge.sh explain`
2. `scripts/moradin_forge.sh readiness --target <target-repo>`
3. `scripts/moradin_forge.sh plan --target <target-repo>`
4. Review proposed writes, readiness gaps, agent blocks, and rollback.
5. `scripts/moradin_forge.sh apply --target <target-repo> --approve`
6. `scripts/moradin_forge.sh verify --target <target-repo>`
7. `scripts/moradin_forge.sh rollback --target <target-repo> --approve`

Readiness and plan remain read-only toward the target. Required runtime gaps
block apply. Recommended gaps remain selectable through a separate
digest-bound tooling plan.

## Write Boundary

After approval, Forge may write only:

- the target repository's `.moradins-harness/` sidecar;
- adaptive snippets under `.moradins-harness/adapters/`;
- ignored local plans, requests, receipts, counters, and verification records;
- a Moradin-owned marker block in a fixed provider path when that individual
  file is approved.

The fixed provider paths are:

- Codex: `AGENTS.md`
- Claude: `CLAUDE.md`
- Gemini CLI: `GEMINI.md`
- GitHub Copilot: `.github/copilot-instructions.md`
- Cursor: `.cursor/rules/moradin-forge.mdc`

Creating an absent canonical agent file requires both
`--approve-agent-file <name>` and `--create-agent-file <name>`. Lowercase
variants and near-miss provider paths are warnings only. Unsupported or
arbitrary instruction paths are never patched. The Cursor rule is Forge-owned
as a complete dedicated file and must not replace an existing unowned file.
`--patch-agents` remains a compatibility alias for approving `AGENTS.md`.

Forge must not overwrite source, manifests, build files, CI workflows,
deployment configuration, or unrelated agent guidance. An existing sidecar
must use the transactional upgrade interface; `--overwrite-sidecar` fails
closed.

## Agent Block Ownership

Each agent file has an independent marker block and ownership record. Plan
output shows the exact diff for each proposed path, so unrelated private
guidance is not copied into Forge artifacts. Apply stages the sidecar and
restores every approved agent file and Forge-created parent directory if any
step fails.

Verification checks the owned block digest while allowing unrelated text to
evolve. Rollback removes or restores only the owned block and refuses a
modified marker.

## Platform Entrypoints

- Linux, WSL, and macOS: `scripts/moradin_forge.sh`
- Windows PowerShell: `scripts/moradin_forge.ps1`
- Core integration implementation: `scripts/moradin_forge.py`
- Workstation and efficiency implementation: `scripts/moradin_workstation.py`

The wrappers prefer `uv` and fall back to Python 3. Forge has no dependency on
private `.templates` or Harness repositories at runtime.

The separate human-run Linux baseline is `install/tooling-suite.sh`. Agents may
offer, plan, and verify that flow but may not operate its interactive menu,
invoke sudo, enter credentials, or confirm its digest. The program may request
sudo only after the human reviews and approves the exact root transaction.

Disconnected Linux onboarding adds `--offline` only after the complete
target-specific air-gap kit has verified and applied. It performs no metadata
refresh. The older `bundle` interface is asset-only and may be partial; it is
not sufficient evidence for complete offline installation.

The reviewed paths match the providers' public conventions for
[Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions),
[Gemini context files](https://geminicli.com/docs/cli/gemini-md/), and
[Cursor project rules](https://docs.cursor.com/context/rules).

## Verification

`verify` reports missing sidecar files, forbidden host-specific references,
ownership-hash mismatches, unowned sidecar content, and owned agent-marker
mismatches. Public release validation additionally proves payload, leak,
portability, security, SBOM, fresh-clone, and context-preservation contracts.
