---
title: "Quick Start"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../README.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
---

# Quick Start

Use Forge from an agent session:

```sh
scripts/moradin_forge.sh explain
scripts/moradin_forge.sh readiness --target <target-repo>
scripts/moradin_forge.sh plan --target <target-repo>
```

After the user approves:

```sh
scripts/moradin_forge.sh apply --target <target-repo> --approve
scripts/moradin_forge.sh verify --target <target-repo>
```

Rollback is deleting `.moradins-harness/` and any separately approved marked
root block.
