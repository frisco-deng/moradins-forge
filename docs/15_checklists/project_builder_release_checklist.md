---
title: "Forge Release Checklist"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../README.md
related_docs:
  - ../references/repo_operating_model_v1.md
---

# Forge Release Checklist

- [ ] Public docs describe Forge as agent-first and local-only.
- [ ] `make test` passes.
- [ ] `make payload-validate` passes.
- [ ] `make payload-smoke` passes.
- [ ] `make forge-smoke` passes.
- [ ] `make public-portability-check` passes.
- [ ] UI tests, build, and moderate audit pass when the workbench ships.
- [ ] Fresh sidecar smoke against a disposable target repo passes.
