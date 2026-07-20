---
title: "Redeployable Forge Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-19
source_refs:
  - ../../FORGE.md
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
---

# Redeployable Forge Contract V1

Forge adoption must be repeatable:

- planning is safe to run without target writes,
- apply requires explicit approval,
- existing sidecars are never deleted in place; overwrite stays blocked until a
  transactional upgrade contract is approved,
- target root workflow files are preserved by default,
- verification reports the sidecar state and rollback path,
- confirmed rollback removes only hash-verified, Forge-owned content.
