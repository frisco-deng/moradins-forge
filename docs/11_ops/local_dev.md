---
title: "Local Development"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../README.md
related_docs:
  - ../references/repo_operating_model_v1.md
---

# Local Development

Use repo-local commands:

```sh
make test
make payload-validate
make payload-smoke
make forge-smoke
make public-portability-check
```

Optional workbench:

```sh
npm --prefix dev_tracker/ui install
./harness_devops.sh --port <workbench-port>
```

Keep the workbench loopback-only unless the user explicitly asks otherwise.
