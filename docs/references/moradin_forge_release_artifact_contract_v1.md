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
  - ../releases/v0.2.0-beta.1.md
---

# Moradin Forge Release Artifact Contract V1

## Purpose

Forge has one reproducible, marker-owned output contract for stable core
release artifacts. This contract does not enable publication, signing,
release-candidate promotion, or cross-platform readiness.

## Command And Output Boundaries

- `make forge-dogfood-smoke` keeps disposable proof and a nested release copy
  under ignored `artifacts/dogfood/`.
- `make forge-release-artifacts` keeps operator evidence under
  `artifacts/dogfood/` and writes the stable release set directly under
  `artifacts/release/`.
- Advisory `make release-build` runs `make forge-release-artifacts` through the
  generated tooling runner and writes its build summary under
  `artifacts/tooling/release-build/`.
- `scripts/moradin_dogfood.py --release-output <path>` is the underlying
  explicit output interface.

The stable release directory contains:

- `moradins-forge-0.2.0-beta.1.tar.gz`
- `moradins-forge-0.2.0-beta.1.spdx.json`
- `release-manifest.json`
- `SHA256SUMS`

The hidden `.moradin-release-output.json` file records Forge ownership and is
not part of the checksummed release set.

## Ownership And Replacement

- Forge replaces an existing dogfood directory only when
  `.moradin-dogfood-output.json` has the expected schema and owner.
- Forge replaces an existing stable release directory only when
  `.moradin-release-output.json` has the expected schema and owner.
- Missing, malformed, or foreign markers cause a hard refusal without deleting
  operator-owned content.
- A separate release output must not equal, contain, or be contained by the
  dogfood output.

## Reproducibility

- Promotable release evidence requires a clean Git worktree.
- The archive uses sorted paths, zeroed ownership, normalized timestamps, and
  Git-portable executable or non-executable modes.
- Generated local portability reports are validated, then excluded from the
  archive so time- and machine-specific audit metadata cannot affect its hash.
- The SPDX document uses the source commit timestamp and exact Python and npm
  lockfile versions.
- The manifest records the source SHA, previous release, archive and SBOM
  hashes, public-export file count, rollback command, and operator-evidence
  link.
- Rebuilding the same commit and lockfiles produces byte-identical archive,
  SPDX, manifest, and checksum files. Ownership-marker timestamps are excluded
  from that guarantee.

## Required Evidence

Before promotion, run:

- `make release-build`
- `make verify-security`
- `make public-portability-check`
- `make verify-paths`
- `tpl-release-candidate-audit --repo moradins-forge --format md`
- the remaining gates in `repo_operating_model_v1.md`

Reproduce the release from a fresh public clone and compare `SHA256SUMS`. The
lock-derived SPDX document complements, but does not replace, the generated
security scanner and SBOM evidence.

## Deferred Lanes

`release_platforms` remains empty. Signing, cross-platform release candidates,
Windows native readiness, macOS signing, WSL smoke, UI visual review, and CAD
lanes remain disabled until their own evidence and human promotion gates are
approved.
