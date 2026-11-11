---
title: "Forge Code Review"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../AGENTS.md
related_docs:
  - references/repo_operating_model_v1.md
---

# Forge Code Review

Use code review to protect the public agent-first contract.

Before merging a public change, confirm:

- the change keeps target repo mutation consent-gated,
- tooling execution requires an exact approved plan digest,
- elevation is never invoked automatically,
- workspace discovery and agent-file approvals remain bounded,
- offline bundles contain no project content or machine paths,
- upgrades restore the prior managed state transactionally,
- root workflow patching remains opt-in,
- generated sidecars verify cleanly,
- public docs avoid host-specific paths and generated local evidence.

Recommended gates:

```sh
make test
make payload-validate
make payload-smoke
make forge-smoke
make public-portability-check
```
