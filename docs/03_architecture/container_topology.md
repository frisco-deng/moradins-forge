---
title: "Container Topology"
status: approved
owner: platform-architecture
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - service_boundaries.md
  - ../00_overview/service_catalog.md
---

# Container Topology

## Topology by Namespace

| namespace | containers/services | intent |
| --- | --- | --- |
| control-plane | tracker_ui, tracker_control_api | operator control, governance, and project generation |
| docs-governance | markdown artifacts, snapshots | enforce cycle state and release evidence |
