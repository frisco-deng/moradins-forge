---
title: "Forge Beta Acceptance Matrix"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-19
source_refs:
  - project_builder_beta_checklist.md
related_docs:
  - project_builder_beta_checklist.md
---

# Forge Beta Acceptance Matrix

| id | capability | acceptance |
| --- | --- | --- |
| BETA-001 | Agent intercept | Agent can explain Forge before apply. |
| BETA-002 | Sidecar adoption | Approved apply writes `.moradins-harness/` only by default. |
| BETA-003 | Verification | `forge verify` reports pass on a clean sidecar. |
| BETA-004 | Portability | `make public-portability-check` passes. |
| BETA-005 | Transactionality | Apply stages before cutover and never deletes an existing sidecar. |
| BETA-006 | Rollback | Confirmed rollback refuses changed content and restores target hashes. |
