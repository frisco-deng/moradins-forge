---
title: "Moradin Forge Release Artifact Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../Makefile
  - ../../scripts/moradin_dogfood.py
  - ../../tooling/configs/tooling-targets.json
related_docs:
  - moradin_forge_public_export_contract_v1.md
  - repo_operating_model_v1.md
  - ../releases/v0.2.0-beta.3.md
---

# Moradin Forge Release Artifact Contract V1

## Purpose

Forge has one reproducible, marker-owned output contract for core prerelease
artifacts. This contract does not authorize publication, signing, stable
production promotion, or a `prod` branch or environment.

## Command and Output Boundaries

- `make forge-dogfood-smoke` keeps disposable proof under ignored
  `artifacts/dogfood/`.
- `make forge-release-artifacts` writes the stable release set under
  `artifacts/release/`.
- Advisory `make release-build` executes that path through the generated
  tooling runner and writes its summary under
  `artifacts/tooling/release-build/`.
- `scripts/moradin_dogfood.py --release-output <path>` is the underlying
  explicit output interface.

The beta.3 release directory contains exactly:

- `moradins-forge-0.2.0-beta.3.tar.gz`
- `moradins-forge-0.2.0-beta.3.spdx.json`
- `release-manifest.json`
- `SHA256SUMS`

The hidden `.moradin-release-output.json` ownership marker is not part of the
checksummed release set.

## Ownership and Reproducibility

Forge replaces output only when the expected ownership marker is valid.
Missing, malformed, foreign, overlapping, or unowned directories cause a hard
refusal.

The archive uses sorted paths, zeroed ownership, normalized timestamps, and
Git-portable modes. Generated machine-specific evidence is validated and then
excluded. The SPDX document derives versions from lockfiles and source commit
time. The manifest records source SHA, previous release, hashes, rollback, and
dogfood evidence.

For beta.3, the previous release and normal release rollback target are
`v0.2.0-beta.1`. The sidecar ownership lineage anchor is an independent
adoption contract and remains unchanged.

The same clean source commit and lockfiles must produce byte-identical archive,
SPDX, manifest, and checksum files.

## Required Evidence

Before prerelease promotion, run:

- `make release-build` twice and compare every checksummed byte;
- `make release-gate-local`;
- `make verify-security`;
- `make public-portability-check`;
- payload, leak, path, CI, and review-ready gates;
- the Linux, macOS, and Windows universal-agent contract workflow;
- the Linux interactive tooling-suite plan, transaction, receipt, and rollback
  contract tests;
- a fresh public clone build with no private Harness dependency;
- the release-candidate advisory audit.

Download the published assets into fresh scratch and run
`sha256sum -c SHA256SUMS`. Extract the archive and rerun public portability.

## Deferred Lanes

The cross-platform workflow validates onboarding plans, wrappers, quoting, and
generated scripts. It does not activate `release_platforms`.

Signing, production readiness, release-candidate manifest, platform signing,
UI visual, CAD, GPU, and production promotion remain disabled until their own
evidence and human gates are approved.
