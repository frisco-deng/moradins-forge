---
title: "Moradin Forge Repo Operating Model V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../README.md
  - ../../AGENTS.md
related_docs:
  - moradin_forge_public_export_contract_v1.md
  - moradin_forge_agent_integration_contract_v1.md
  - tooling_readiness_install_request_contract_v1.md
---

# Moradin Forge Repo Operating Model V1

## Purpose

Moradin's Forge is now maintained from the public product repository. Normal
features, fixes, documentation updates, tests, and release work happen on public
branches in this repo.

## Public Work Rules

- Create public branches from `main` for normal product work.
- Keep `main` protected with required `verify`, `security`, and
  `submit-dependencies` checks.
- Keep dependency graph, Dependabot security updates, secret scanning, and push
  protection enabled.
- Run portability and sidecar leak checks before every public PR or release.
- Keep public docs generic; use `<forge-root>`, `<target-repo>`, `<temp-dir>`,
  and `<workbench-port>` placeholders.

## Private Control Boundary

- Private staging/control history is provenance only, not product source.
- Do not copy private commits, branches, release evidence, generated sessions,
  or local governance artifacts into this repo.
- Do not paste private host paths, usernames, private branch names, or internal
  evidence into public docs, issues, PRs, releases, or generated sidecars.
- If a change appears to require private staging context, write a public,
  generic description of the behavior instead of importing the private artifact.

## Required Public Gates

Use these gates before public PRs and releases:

- `make test`
- `make payload-validate`
- `make payload-smoke`
- `make forge-smoke`
- `make public-portability-check`
- `npm --prefix dev_tracker/ui ci`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
- `npm --prefix dev_tracker/ui audit --audit-level=moderate`

For adoption behavior changes, also run a fresh sidecar smoke against a
disposable target repo and verify the target root files are preserved by
default.

## Archive Timing

Private staging/control should remain private and read-only for provenance
until Forge has completed follow-up public releases without relying on private
export machinery. Do not delete private provenance while public release and
rollback history still depends on it.
