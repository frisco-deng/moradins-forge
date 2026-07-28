---
title: "Forge Release Acceptance Matrix"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-19
source_refs:
  - project_builder_release_checklist.md
related_docs:
  - project_builder_release_checklist.md
---

# Forge Release Acceptance Matrix

| id | capability | acceptance |
| --- | --- | --- |
| REL-001 | Public docs | First-read docs describe Forge as agent-first and local-only. |
| REL-002 | Safety | Apply requires explicit approval and root patching remains opt-in. |
| REL-003 | Portability | Repo and generated sidecar pass portability checks. |
| REL-004 | Workbench | Optional UI tests and build pass when included in the release. |
| REL-005 | Release proof | Archive, checksum, SPDX SBOM, manifest, and current-SHA evidence exist. |
| REL-006 | Rollback | `v0.1.0-public-alpha` is recorded and the disposable-target rollback passes. |
