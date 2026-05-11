---
title: "Forge Control API"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../scripts/moradin_forge.py
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
---

# Forge Control API

Forge exposes deterministic command verbs through `scripts/moradin_forge.*`:

- `explain`: summarize Forge behavior,
- `readiness`: detect required and optional tooling,
- `plan`: produce a dry-run adoption plan,
- `apply`: write the approved sidecar,
- `verify`: validate the adopted sidecar.

Host tool installation remains request-only.

No auto-execution endpoint is exposed.
