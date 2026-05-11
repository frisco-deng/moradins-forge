---
title: "Engineer Entry Authoring Runbook"
status: approved
owner: platform-operations
last_reviewed: 2026-02-24
source_refs:
  - https://openai.com/index/harness-engineering/
related_docs:
  - ../engineer_entry/index.md
  - tooling_pipeline.md
  - codex_run_loop.md
  - ../15_checklists/agent_cycle_gate.md
  - ../../AGENTS.md
---

# Engineer Entry Authoring Runbook

## Purpose

- Provide a deterministic authoring routine for `docs/engineer_entry/`.
- Keep engineer-owned direction legible and enforceable by harness checks.

## Authoring Workflow

1. Start from `main` and create a docs branch: `docs/<scope>`.
2. Edit only non-index `docs/engineer_entry/` files intended for operator direction.
3. Use `owner: person:<slug>` for every human-owned engineer-entry doc.
4. Ensure frontmatter keys exist: `title`, `status`, `owner`, `last_reviewed`, `source_refs`, `related_docs`.
5. Include at least one top-level heading and explicit stop conditions.
6. Regenerate the index:
   - `npm --prefix dev_tracker/ui run sync:engineer-entry`
5. Run checks:
- `make lint-md`
- `npm --prefix dev_tracker/ui run check:engineer-entry`
7. Update changelog and guidance artifacts when policy wording changes.
8. Open MR and attach check output.

## Prompt Pattern for Operators

```text
Update engineer entry context for objective <id>.
Keep scope bounded to <phase/stage>.
List acceptance checks and stop conditions.
After update, run engineer-entry guard and report pass/fail.
```

## Failure Handling

- If frontmatter check fails, fix fields before any cycle execution.
- If the index is stale, regenerate it before running the guard again.
- If disallowed write is detected, stop cycle and route to capability gap review.
- If guard failure repeats, escalate via `docs/exec_plans/tech-debt-tracker.md`.

## Verification Checklist

- [ ] Frontmatter is complete and valid.
- [ ] Top-level heading exists.
- [ ] Guard and markdown lint checks pass.
- [ ] MR includes evidence and reviewer approval.

## Related Docs

- ../engineer_entry/index.md
- tooling_pipeline.md
- codex_run_loop.md
- ../15_checklists/agent_cycle_gate.md
- ../../AGENTS.md
