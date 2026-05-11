---
title: "Repo Registry And Adapter Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-05-03
source_refs:
  - dev_tracker/ui/scripts/control-api.mjs
  - scripts/domain_briefs.py
  - scripts/new_repo_onboarding.py
related_docs:
  - moradin_payload_contract_v1.md
  - ../11_ops/project_builder_runbook.md
---

# Repo Registry And Adapter Contract V1

## Purpose

The repo registry gives Moradin a deterministic portfolio summary so assistants
can reuse concise state instead of repeatedly scanning the same repos.

## API And Artifacts

- API: `GET /api/moradin/repo-registry`
- JSON artifact: `Harness/artifacts/control/repo_registry/repositories.json`
- Markdown artifact: `Harness/artifacts/control/repo_registry/repositories.md`

## Registry Rows

Each row records:

- repo id, name, scope, and disclosed path
- git and `AGENTS.md` presence
- `.moradins-harness` sidecar presence
- package-manager markers
- detected Make targets
- generated tooling adapter presence
- reusable project-status artifact link when available
- deterministic brief and rerun advice

## Adapter Expectations

Repo adapters stay thin and repo-owned. Preferred commands are:

- `make repo-brief`
- `make verify-fast`
- `make review-ready`

Moradin also provides brief targets:

- `make builder-brief`
- `make adoption-brief`
- `make release-brief`
- `make new-repo-brief`

Brief artifacts are written under `Harness/artifacts/task_lanes/**`.
