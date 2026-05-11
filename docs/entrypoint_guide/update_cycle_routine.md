---
title: "Update Cycle Routine"
status: approved
owner: platform-operations
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - index.md
  - ../11_ops/change_tracking_system.md
---

# Update Cycle Routine

## Steps

1. Route update work to `docs/exec_plans/updates/active/`.
2. Execute deterministic checks and sync impacted docs.
3. Archive completed update artifacts and append changelog evidence.

## Gate Requirement

- Require explicit human `continue|pause|stop` decision before cycle continuation.
- Block cycle `N+1` until cycle `N` changelog approval status is `approved`.
- Require queue reconciliation to confirm active update index contains actionable items only.
