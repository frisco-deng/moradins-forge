---
title: "Public Git Workflow"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../references/repo_operating_model_v1.md
related_docs:
  - ../references/repo_operating_model_v1.md
---

# Public Git Workflow

- Work on public branches from `main`.
- Keep `main` protected.
- Require `verify`, `security`, and `submit-dependencies` on protected `main`.
- Run portability checks before public releases.
- Do not force-push protected branches except for an explicitly approved public
  history reset.
