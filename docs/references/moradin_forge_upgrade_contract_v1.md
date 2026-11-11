---
title: "Moradin Forge Upgrade Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/moradin_forge.py
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
  - moradin_payload_contract_v1.md
---

# Moradin Forge Upgrade Contract V1

## Purpose

This contract upgrades an adopted sidecar without overwriting it in place or
losing unrelated agent guidance.

## Commands

```sh
scripts/moradin_forge.sh upgrade-plan --target <target-repo>
scripts/moradin_forge.sh upgrade \
  --target <target-repo> \
  --plan <upgrade-plan.json> \
  --approve-plan-sha256 <sha256>
scripts/moradin_forge.sh upgrade-rollback \
  --target <target-repo> \
  --upgrade-id <upgrade-id> \
  --approve
```

## Preconditions

The current sidecar must have a valid Forge V1 or V2 ownership record. Managed
sidecar content and owned agent marker blocks must match their recorded hashes.
The plan binds target identity, current ownership state, source payload
version, source payload digest, proposed agent blocks, and exact SHA-256.

Any target or source change makes the plan stale.

## Transaction

1. Revalidate the exact plan and current ownership.
2. Stage the replacement beside the live sidecar.
3. Generate adapters and managed records in staging.
4. Validate the staged payload.
5. Save the immediate Forge-owned predecessor.
6. Switch sidecars atomically.
7. Update only owned agent marker blocks.
8. Verify the live result.

An exception restores the previous sidecar and every managed block
byte-for-byte. Unrelated agent text is never replaced.

## Retention and Rollback

Forge retains one nested predecessor, identified by `upgrade_id`. A successful
later upgrade replaces the older predecessor rather than building an
unbounded chain.

`upgrade-rollback` requires explicit approval, validates the identifier and
ownership, restores the immediate predecessor, and removes the consumed backup.
It refuses modified, missing, or unowned state.

The legacy `--overwrite-sidecar` flag remains disabled and directs users to
this contract.
