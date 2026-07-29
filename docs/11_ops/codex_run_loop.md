---
title: "Codex Run Loop"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../Harness/entrypoints/codex.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
  - ../references/moradin_agent_efficiency_contract_v1.md
---

# Codex Run Loop

1. Read the first-read Forge entrypoints.
2. Ask for explicit workspace roots.
3. Run `onboard` and show discovered repositories.
4. Review the compact primer and repository-native commands.
5. Present tools, configuration, agent blocks, validation, and rollback.
6. Ask for each independent approval.
7. Execute digest-approved user-level tooling; give privileged scripts to the
   user and verify after they run them.
8. Apply the sidecar and approved blocks transactionally.
9. Run security and repository-native validation.
10. Record a sanitized checkpoint and report exact rollback.

Use `rerun-advice` before repeating an expensive command. Expand beyond compact
evidence when it is missing, stale, contradictory, security-sensitive, or
release-critical.
