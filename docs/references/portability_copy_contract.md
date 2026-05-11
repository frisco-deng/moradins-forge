---
title: "Portability Copy Contract"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../Harness/moradin_payload/manifest.yaml
related_docs:
  - moradin_payload_contract_v1.md
---

# Portability Copy Contract

Sidecar copy behavior is governed by `Harness/moradin_payload/manifest.yaml`.

The payload should include only public Forge files needed for local adoption,
validation, rollback, and optional diagnostics. Generated local evidence,
caches, and prior adoption records must be excluded.
