---
title: "Tooling Pipeline"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../Makefile
related_docs:
  - ../references/repo_operating_model_v1.md
---

# Tooling Pipeline

Use the public gates for product work:

```sh
make test
make payload-validate
make payload-smoke
make forge-smoke
make public-portability-check
```

Optional workbench gates:

```sh
npm --prefix dev_tracker/ui run test
npm --prefix dev_tracker/ui run build
npm --prefix dev_tracker/ui audit --audit-level=moderate
```
