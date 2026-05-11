---
title: "Release Checklist"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../references/repo_operating_model_v1.md
related_docs:
  - project_builder_release_checklist.md
---

# Release Checklist

- [ ] `make test`
- [ ] `make payload-validate`
- [ ] `make payload-smoke`
- [ ] `make forge-smoke`
- [ ] `make public-portability-check`
- [ ] UI tests, build, and audit if the workbench ships.
- [ ] GitHub Actions pass on protected `main`.
