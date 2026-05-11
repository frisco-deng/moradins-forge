---
title: "Moradin Forge Workbench"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../FRONTEND.md
related_docs:
  - ../11_ops/quick_start.md
  - ../design_docs/project_builder_control_api.md
---

# Moradin Forge Workbench

## Goal

Keep the browser surface useful as optional diagnostics while the primary
adoption path remains native agent scripts.

The workbench should help operators inspect:

- readiness state,
- target repo selection,
- deploy maps,
- sidecar verification,
- generated install requests,
- repo registry summaries.

## Primary Routes

- `/home`
- `/deploy/quick-start`
- `/deploy/readiness`
- `/deploy/map`
- `/deploy/builder`
- `/deploy/status`
- `/payload`

`/template` may remain as a temporary redirect during the compatibility window,
but visible navigation should use Moradin payload language.

## Boundaries

- The workbench must not execute host installs.
- The workbench must not publish target repo content.
- The workbench must preserve the same consent gate as the native scripts.
- Root workflow patching remains opt-in.
