---
title: "Day 0 Onboarding Runbook"
status: approved
owner: platform-operations
last_reviewed: 2026-03-03
source_refs: []
related_docs:
  - codex_run_loop.md
  - docs/entrypoint_guide/index.md
  - ../15_checklists/agent_cycle_gate.md
---

# Day 0 Onboarding Runbook

## Purpose

- Bring a new engineer/operator to a deterministic local-ready state for harness execution.

## Checklist

- [ ] Install Python, Node, and uv/npm dependencies.
- [ ] Run `make lint-py`, `make lint-md`, `make validate-skills`, and `make validate-capture-contract`.
- [ ] Run `npm --prefix dev_tracker/ui run test` and `npm --prefix dev_tracker/ui run build`.
- [ ] Run `npm --prefix dev_tracker/ui run sync-docs` and verify tracker snapshot generation.
- [ ] Create a scoped branch using `make branch-start PHASE=<n> STAGE=<n> SCOPE=<scope>`.
- [ ] Confirm branch naming includes routing marker and `make branch-hygiene` passes.
