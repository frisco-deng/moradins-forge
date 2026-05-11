---
title: "Tooling Pipeline"
status: approved
owner: platform-operations
last_reviewed: 2026-03-29
source_refs:
  - https://openai.com/index/harness-engineering/
related_docs:
  - codex_run_loop.md
  - agent_harness_governance.md
  - git_workflow_gitlab.md
  - engineer_entry_authoring_runbook.md
  - docs/exec_plans/tooling/completed/tooling_review_2026-02-24_harness_and_branching.md
  - ../engineer_entry/index.md
  - ../13_style_guides/doc_style.md
  - ../../AGENTS.md
---

# Tooling Pipeline

## Purpose

- Define deterministic tooling checks for docs, formatting, and linting.
- Ensure engineer-entry context remains legible and frontmatter compliant.

## Pipeline Stages

1. Run branch hygiene gate: `make branch-hygiene`.
2. Run markdown lint for repository policy: `make lint-md`.
3. Run engineer-entry guard: `make engineer-entry-guard`.
4. Run repository lint and compatibility gate: `make lint`.
5. Run integration quality pass when needed: `npm --prefix dev_tracker/ui run qa:pass`.
6. Block continuation when guard, branch, lint, or compatibility checks fail.
7. Record update, upgrade, and tooling review outcomes before cycle continuation.

## Branch Hygiene Waiver

- Normal policy is to resolve branch hygiene findings before handoff.
- A human-approved waiver may clear only listed stale, local-branch, or
  remote-branch findings when deleting shared refs would be riskier than
  starting the scoped migration.
- The waiver contract is `Harness/artifacts/control/branch_hygiene_exception.json`.
- Waivers must expire, name the active branch, and leave cleanup required before
  `dev -> main` promotion unless explicitly renewed.
- Waivers never cover protected-branch dirty state, protected-branch divergence,
  current-branch naming failures, or new unlisted branch findings.

## Lean Command Policy

- Prefer short repo-native commands over long ad hoc command bundles to reduce prompt/context token usage and operator error.
- Prefer `make` entrypoints when they exist before spelling out raw `uv` or `npm` chains.
- Prefer native shell commands such as `mv` and `rg` for simple file moves and discovery rather than verbose scripted substitutes.

### Recommended Short Commands

- `make sync-engineer-entry`
- `make sync-docs`
- `make ui-test`
- `make ui-test-browser`
- `make ui-build`
- `make ui-review-screenshots`
- `make ui-playwright-mcp-doctor`
- `make payload-validate`
- `make payload-smoke`
- `make builder-brief`
- `make adoption-brief`
- `make release-brief`
- `make alpha-validate`
- `make migration-start`
- `make pr-hardening`
- `make quick-check`
- `make alpha-check`

### Raw Command Fallbacks

- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py alpha-validate`
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/manage_moradin_payload.py smoke-test`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run test:browser`
- `npm --prefix dev_tracker/ui run build`
- `node ./dev_tracker/ui/scripts/capture-review-screenshots.mjs`
- `node ./dev_tracker/ui/scripts/playwright-mcp-doctor.mjs`

## Engineer-Entry Trigger Rule

- When any file under `docs/engineer_entry/` is detected in working-tree changes:
- Require full frontmatter validation for each engineer-entry markdown file.
- Require `docs/engineer_entry/index.md` to remain generated and up to date with the directory summary.
- Require non-index engineer-entry docs to use `owner: person:<slug>`.
- Fail the cycle if agent-side writes are detected in engineer-entry files outside approved bootstrap scope.
- Auto-open a capability gap row when engineer-entry guard fails.

## Generated QA Signals

- `dev_tracker/ui/public/generated/qa_signals_v1.json` stores latest guardrail statuses.
- `engineer_entry_guard.status`: pass/fail plus command detail.
- `branch_hygiene.status`: pass/fail plus stale-branch, routing-marker, naming, and remote-cleanup diagnostics.
- `documentation_review.status`: pass/warn/fail based on `documentation_review_status.md` contract checks.
- Tracker Settings page must surface all guardrail statuses for operators.

## Verification Checklist

- [ ] `make branch-hygiene` completed successfully.
- [ ] `make lint-md` completed successfully.
- [ ] Engineer-entry guard completed successfully.
- [ ] Frontmatter requirements passed for engineer-entry docs.
- [ ] `qa_signals_v1.json` includes current guardrail statuses.
- [ ] Documentation-review QA signal is present and not failed.
- [ ] Failed checks were resolved before human gate approval.

## Related Docs

- codex_run_loop.md
- agent_harness_governance.md
- git_workflow_gitlab.md
- engineer_entry_authoring_runbook.md
- docs/exec_plans/tooling/completed/tooling_review_2026-02-24_harness_and_branching.md
- ../engineer_entry/index.md
- ../13_style_guides/doc_style.md
- ../../AGENTS.md
