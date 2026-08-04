---
title: "Engineer Entry Index"
status: generated-reference
owner: docs-build-pipeline
last_reviewed: 2026-07-31
source_refs: []
related_docs:
  - ../00_overview/engineer_entrypoint.md
  - ../11_ops/engineer_entry_authoring_runbook.md
  - ../11_ops/tooling_pipeline.md
generated: true
generation_source: engineer-entry-index-generator
generation_owner: docs-build-pipeline
---

# Engineer Entry Index

## Purpose

- Provide the generated directory index for engineer-entry context.
- Separate generated navigation from human-owned operator instructions.

## Human-Owned Context Contract

- `docs/00_overview/engineer_entrypoint.md` is treated as human-owned context for the tracker classification model.
- Any markdown file under `docs/engineer_entry/` except this index is human-owned context.
- Human-owned engineer-entry docs must use `owner: person:<slug>` and are blocked from agent-side writes.

## Current Human-Owned Files

- No human-owned files under `docs/engineer_entry/` yet.

## Required First Reads

1. [Engineer Entrypoint](../00_overview/engineer_entrypoint.md)
2. [Engineer Entry Authoring Runbook](../11_ops/engineer_entry_authoring_runbook.md)
3. [Tooling Pipeline](../11_ops/tooling_pipeline.md)

## Generation Notes

- Regenerate this index after changing any human-owned engineer-entry file.
- Canonical generator: `npm --prefix dev_tracker/ui run sync:engineer-entry`.

