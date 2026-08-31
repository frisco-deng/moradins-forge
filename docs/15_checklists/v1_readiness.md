---
title: "Moradin Forge v1.0 Readiness"
status: active
owner: moradin-forge
last_reviewed: 2026-08-31
source_refs:
  - ../../SECURITY.md
  - ../references/moradin_forge_tooling_suite_contract_v2.md
  - ../references/moradin_forge_release_artifact_contract_v1.md
related_docs:
  - release_checklist.md
  - security_review.md
---

# Moradin Forge v1.0 Readiness

Version 1.0 means the public Forge interfaces are stable and supported. It
does not certify every host or repository as production-ready.

## RC Entry

- [ ] V2 catalog, doctor, plan, checkpoint, receipt, root, and air-gap records
      have a documented compatibility policy and no known contract break.
- [ ] Apache-2.0 licensing, semantic-versioning commitments, support policy,
      and private vulnerability reporting are present and reviewed.
- [ ] Archive, SPDX SBOM, provenance, and manifest are keyless Cosign-signed.
- [ ] Independent clean-machine Practical and Extended qualification passes on
      Linux/WSL, macOS, and Windows.
- [ ] A complete supported Linux air-gap kit installs, verifies, and rolls back
      with networking disabled.
- [ ] Required CodeQL has a stable signal and all high/critical findings are
      resolved or release-blocking.
- [ ] Security, dependency-readiness, dependency submission, SBOM, leak,
      payload, portability, public-clone, context-diet, and reproducible-build
      evidence is current.

## Observation and Stable Release

- [ ] Publish `v1.0.0-rc.1` only through the human release gate.
- [ ] Observe the RC for at least 14 days.
- [ ] Record no unresolved release-blocking regression during that period.
- [ ] Rebuild and verify stable artifacts from the pinned merge SHA.
- [ ] Publish `v1.0.0` only after a final human security and support review.
