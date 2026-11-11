---
title: "Upgrades"
status: approved
owner: platform-architecture
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/moradin_forge.py
related_docs:
  - ../references/moradin_forge_upgrade_contract_v1.md
  - ../references/moradin_forge_agent_integration_contract_v1.md
---

# Upgrades

## Sidecar Upgrade Runbook

Create a read-only plan:

```sh
scripts/moradin_forge.sh upgrade-plan --target <target-repo>
```

Review the current and proposed payload versions, target/source fingerprints,
owned agent blocks, validation, rollback identifier, and exact plan SHA-256.
Apply only that plan:

```sh
scripts/moradin_forge.sh upgrade \
  --target <target-repo> \
  --plan <upgrade-plan.json> \
  --approve-plan-sha256 <sha256>
```

Forge revalidates the current V1 or V2 sidecar, stages and verifies the new
payload, retains one predecessor, switches atomically, and updates only its
owned marker blocks. A stale plan or modified managed file fails closed.

Restore the immediate predecessor:

```sh
scripts/moradin_forge.sh upgrade-rollback \
  --target <target-repo> \
  --upgrade-id <upgrade-id> \
  --approve
```

Failed upgrades restore the prior sidecar and managed blocks byte-for-byte.
Use the explicit rollback command rather than deleting files manually.

## Tool Updates

Run `tooling-update-plan --workspace <approved-workspace>` when an update is
wanted. Forge checks only during invocation and only when its 24-hour metadata
cache is stale. Review and approve the new digest like an initial install.
There is no background updater.

## Release Boundary

Sidecar or tool upgrade success does not authorize production promotion.
Signing, production readiness, release-candidate manifest, and environment
promotion remain separate human gates.
