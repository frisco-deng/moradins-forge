---
title: "Moradin Forge Public Portability Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/public_export.py
related_docs:
  - moradin_forge_release_artifact_contract_v1.md
  - repo_operating_model_v1.md
---

# Moradin Forge Public Portability Contract V1

## Purpose

Public Forge releases must be portable, local-only, and free of host-specific
paths or generated local evidence.

## Requirements

- Public docs use placeholders such as `<forge-root>`, `<target-repo>`, and
  `<temp-dir>`.
- Public docs, sidecars, and audit reports must not contain raw Linux home
  paths, macOS user paths, Windows user paths, WSL UNC paths, Codex session
  paths, SSH clone URLs, hostnames, usernames, or raw temp paths.
- Generated sidecars must not include local caches, audit output, install
  request history, or previous adoption records.
- Bootstrap start cards under `artifacts/bootstrap/` are local generated
  evidence and must not be included in public exports or sidecar payloads.
- `make public-portability-check` must pass before release.
- Fresh clones must be able to run `make forge-smoke`,
  `make public-portability-check`, and `make release-build` without a private
  repository dependency.
