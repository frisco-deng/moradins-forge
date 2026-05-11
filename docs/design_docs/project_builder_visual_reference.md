---
title: "Project Builder Visual Reference"
status: approved
owner: platform-operations
last_reviewed: 2026-03-07
source_refs: []
related_docs:
  - project_builder_control_api.md
  - docs/product_specs/project_builder_ui.md
---

# Project Builder Visual Reference

## Block Diagram

```mermaid
flowchart LR
  UI[Builder UI] --> Settings[Settings Defaults]
  UI --> DeployMap[Deploy Map]
  UI --> Discovery[Discovery Session]
  Discovery --> PromptBundle[Prompt Bundle Artifacts]
  PromptBundle --> Assistant[Assistant Action Bar]
  Discovery --> Generate[Generate Repo]
  Discovery --> Scan[Project Scan]
  Scan --> Deploy[Remote or Local Sidecar Deploy]
  Deploy --> Status[Project Status]
```

## Existing Project Sequence

```mermaid
sequenceDiagram
  participant Operator
  participant Builder
  participant ControlAPI
  participant SSH
  Operator->>Builder: choose Existing Project
  Builder->>ControlAPI: project-scan(target_mode, remote_target)
  ControlAPI->>SSH: find / inspect target repo
  SSH-->>ControlAPI: scan signals
  Operator->>Builder: complete discovery + approval
  Builder->>ControlAPI: deploy-existing(...)
  ControlAPI->>ControlAPI: build and validate sidecar locally
  ControlAPI->>SSH: tar stream sidecar
  SSH-->>ControlAPI: unpack under sidecar dir
  Builder->>ControlAPI: project-status(...)
```

## Template Fill Map

The UI now uses two visual layers:

- React Flow in `/deploy-map` and `/builder` for workflow graphs.
- Expandable tree views for baseline template paths and concrete generated output.

The fill tree groups generated files into four source buckets:

- `seed_template`
- `profile_overlay`
- `user_filled`
- `scan_derived`

Use this visual to explain what was prefilled by the base harness and what changed because of discovery or scan context.
