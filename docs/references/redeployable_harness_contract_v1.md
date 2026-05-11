---
title: "Redeployable Forge Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../FORGE.md
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
---

# Redeployable Forge Contract V1

Forge adoption must be repeatable:

- planning is safe to run without target writes,
- apply requires explicit approval,
- existing sidecars are not overwritten unless requested,
- target root workflow files are preserved by default,
- verification reports the sidecar state and rollback path.
