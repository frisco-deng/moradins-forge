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
validation, install requests, and rollback before mutating a target repo.

## Local First

Forge writes local sidecars and local artifacts. It does not publish target repo
contents or install host tools.

## Preserve Existing Workflows

Target `Makefile`, package scripts, CI, docs, and agent files remain unchanged by
default. Root patches require explicit approval.

## Deterministic Reflexes

Forge gives agents predictable commands and contracts so common adoption steps
do not require repeated inference.

## Portable By Default

Public docs and generated sidecars use generic placeholders such as
`<forge-root>`, `<target-repo>`, and `<temp-dir>`.
