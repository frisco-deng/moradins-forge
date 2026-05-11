---
title: "Service Boundaries"
status: approved
owner: platform-architecture
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - container_topology.md
  - ../00_overview/service_catalog.md
---

# Service Boundaries

## Boundary Map

| service | primary role | owns | does not own | key contracts |
| --- | --- | --- | --- | --- |
| tracker_control_api | local control orchestration | builder/discovery endpoints, safe filesystem operations | downstream app runtime logic | project_builder_control_api.md |
| dev_tracker_ui | operator UX | phase/cycle visibility, deploy-map explainability, and builder workflows | backend execution scheduling | TrackerSnapshotV6, Builder APIs |
| docs_governance | process governance | changelog, loop state, capability registers, plan indexes | runtime service contracts | codex_run_loop.md, agent_cycle_gate.md |
