---
title: "Forge Control API"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/moradin_forge.py
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
---

# Forge Control API

Forge exposes deterministic command verbs through `scripts/moradin_forge.*`:

- `explain`: summarize Forge behavior,
- `onboard`: discover repositories below approved workspace roots,
- `tooling-plan`: create the digest-bound practical-full plan,
- `tooling-apply`: run approved verified user-level actions,
- `tooling-bundle`: create a checksummed portable offline bundle,
- `readiness`: detect required and optional tooling,
- `plan`: produce a dry-run adoption plan,
- `apply`: write the approved sidecar,
- `verify`: validate the adopted sidecar,
- `upgrade-plan`, `upgrade`, and `upgrade-rollback`: transactional replacement,
- compact context, state, brief, rerun, checkpoint, and diagnostic commands.

The browser UI remains request-only. Native CLI auto-execution is limited to
an exact approved plan digest and verified user-level actions; privileged
scripts are always user-run.

No auto-execution endpoint is exposed. This invariant applies to the browser
control API, not to the separately consented native CLI executor.
