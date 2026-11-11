---
title: "Tooling Readiness And Install Request Contract V1"
status: compatibility
owner: platform-operations
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/moradin_forge.py
related_docs:
  - tooling_readiness_install_execution_contract_v2.md
  - moradin_forge_agent_integration_contract_v1.md
---

# Tooling Readiness And Install Request Contract V1

## Compatibility Status

V1 preserves the existing `readiness` response and UI install-request artifact
shape for early adopters. The canonical beta.3 execution and safety model is
[Tooling Readiness And Install Execution Contract V2](tooling_readiness_install_execution_contract_v2.md).

V1 readiness remains non-mutating. When gaps exist it writes a review artifact
and points the agent to `tooling-plan`; it never authorizes execution by
itself. Required runtime gaps block adoption, while recommended gaps remain
selectable.

The browser UI continues to create request artifacts only. Native CLI
execution requires the separately generated V2 plan and its exact approved
SHA-256.
