---
title: "Upgrade Cycle Routine"
status: approved
owner: platform-operations
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - index.md
  - ../11_ops/upgrades.md
---

# Upgrade Cycle Routine

## Steps

1. Collect post-gate upgrade candidates.
2. Route each candidate as `upgrade_next_cycle`, `defer_with_risk`, or `reject`.
3. Record decision in upgrade review artifact and archive register.

## Gate Requirement

- Require explicit human routing decision for each candidate before execution.
- Do not start cycle `N+1` while approved `upgrade_next_cycle` items remain unexecuted.
- Require changelog approval reference and human-gate stats update before closeout.
