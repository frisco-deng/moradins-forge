---
title: "Engineer Entrypoint"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../AGENTS.md
related_docs:
  - ../references/repo_operating_model_v1.md
---

# Engineer Entrypoint

When changing Forge itself:

1. Read `AGENTS.md`, `FORGE.md`, and the relevant contract.
2. Keep public behavior local-first and consent-gated.
3. Preserve target root workflows by default.
4. Update docs and tests with behavior changes.
5. Run the gates listed in `docs/references/repo_operating_model_v1.md`.
