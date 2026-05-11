---
title: "Service Catalog"
status: approved
owner: platform-architecture
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - architecture.md
  - ../03_architecture/service_boundaries.md
---

# Service Catalog

## Catalog Table

| service | domain | responsibility | phase_target |
| --- | --- | --- | --- |
| `dev_tracker_ui` | control-plane | operator UI for governance and builder workflows | p1-s01 |
| `tracker_control_api` | control-plane | local control API for sync/builder/discovery endpoints | p1-s01 |
| `docs_governance` | governance | canonical control artifacts and cycle records | p0-s00 |
