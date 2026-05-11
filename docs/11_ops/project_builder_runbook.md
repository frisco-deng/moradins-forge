---
title: "Forge Adoption Runbook"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../FORGE.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
---

# Forge Adoption Runbook

The public adoption path is agent-first:

1. Inspect Forge and the target repo.
2. Run readiness and plan.
3. Explain sidecar writes, adapter snippets, install requests, validation, and
   rollback.
4. Ask for explicit approval.
5. Apply only with `--approve`.
6. Verify the sidecar and report changed paths.

Forge writes `.moradins-harness/` by default and preserves target root files.
