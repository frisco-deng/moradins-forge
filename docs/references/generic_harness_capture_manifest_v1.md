---
title: "Forge Capture Manifest V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../Harness/moradin_payload/manifest.yaml
related_docs:
  - portability_copy_contract.md
---

# Forge Capture Manifest V1

Capture manifests define which public Forge files may be copied into a sidecar.

Only portable docs, scripts, payload manifests, adapters, tests, and optional
diagnostic assets should be captured. Local audit output and adoption history
must remain outside downstream sidecars.
