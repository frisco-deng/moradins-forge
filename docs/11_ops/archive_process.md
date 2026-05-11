---
title: "Archive Process"
status: approved
owner: platform-operations
last_reviewed: 2026-03-02
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - codex_run_loop.md
  - upgrades.md
  - docs/exec_plans/implementation/active/index.md
  - change_tracking_system.md
  - ../15_checklists/agent_cycle_gate.md
  - Harness/artifacts/control/archive_register.md
  - docs/exec_plans/index.md
---

# Archive Process

## Purpose

- Define how update and upgrade outcomes are archived in a normalized, queryable format.
- Ensure every cycle has durable historical records linked to governance artifacts.

## Archive Contract

1. Maintain canonical records under `docs/exec_plans/{implementation,updates,upgrades}/completed/`.
2. Append one row to `Harness/artifacts/control/archive_register.md` for each new archive record.
3. Use `record_type` values: `suggestion`, `update`, or `upgrade_review`.
4. Include `source_cycle` for every archived record.
5. Ensure archive paths in register rows resolve to real files.
6. Commissioned capability suggestions must move from `docs/exec_plans/implementation/active/` into archive records.

## Upgrade Review Archiving

1. At every human gate, review upgrade routing outcomes.
2. If routing is non-empty or explicitly "none", archive one `upgrade_review` record.
3. Record routing summary and evidence links in the upgrade review archive file.
4. Reference the archive record in `archive_register.md`.

## Legacy Conversion Contract

- Legacy folders may remain only as pointer docs.
- Canonical content must live under `docs/exec_plans/*/completed/`.
- Pointer docs must include links to canonical records.

## Verification Checklist

- [ ] Archive register row exists for each new archive record.
- [ ] Archive row path resolves in docs snapshot.
- [ ] Upgrade reviews are archived at each gate.
- [ ] Legacy pointers map to canonical records.

## Related Docs

- codex_run_loop.md
- upgrades.md
- docs/exec_plans/implementation/active/index.md
- change_tracking_system.md
- ../15_checklists/agent_cycle_gate.md
- Harness/artifacts/control/archive_register.md
- docs/exec_plans/index.md
