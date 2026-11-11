---
title: "Foundational Principles"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../FORGE.md
  - ../../AGENTS.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
---

# Foundational Principles

## Consent First

Forge plans before it applies. Agents must explain proposed writes, risks,
validation, tooling actions, agent-file blocks, user configuration, privileged
scripts, and rollback before mutation.

## Local First

Forge writes local sidecars and local artifacts. It does not publish target
repository contents. It may execute verified user-level tooling actions only
after exact digest approval and never invokes elevation.

## Preserve Existing Workflows

Target `Makefile`, package scripts, CI, docs, and agent files remain unchanged by
default. Each `AGENTS.md` or `CLAUDE.md` owned block requires independent
approval and preserves unrelated guidance.

## Bounded Discovery

Forge discovers repositories only below explicitly approved workspace roots.
It reports the repository list before inspecting standard project surfaces and
does not crawl arbitrary source contents.

## Deterministic Reflexes

Forge gives agents predictable commands and contracts so common adoption steps
do not require repeated inference.

## Portable By Default

Public docs and generated sidecars use generic placeholders such as
`<forge-root>`, `<target-repo>`, and `<temp-dir>`.
