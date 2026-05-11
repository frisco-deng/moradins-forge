---
title: "Moradin Forge Public Export And Portability Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-05-08
source_refs:
  - scripts/public_export.py
  - scripts/moradin_forge.py
  - Harness/moradin_payload/manifest.yaml
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
  - moradin_payload_contract_v1.md
  - assistant_handoff_contract_v1.md
---

# Moradin Forge Public Export And Portability Contract V1

## Purpose

Moradin's Forge is published from a sanitized export, not by exposing the
private staging repo history. The export must be deterministic, local,
auditable, and safe for an agent to clone before integrating into a user's repo.

## Public Export Rules

- Export to a separate `<public-repo-dir>`.
- Do not rewrite or publish private staging history.
- Initialize the export as a fresh git repo with one initial commit when
  `--init-git` is requested.
- Include portable Forge scripts, contracts, docs, optional workbench sources,
  tests, and release tooling that pass portability checks.
- Exclude prior git history, release evidence, branch waivers, PR hardening
  artifacts, discovery sessions, generated sidecar evidence, screenshots,
  caches, and private governance artifacts.
- Replace private paths and local assumptions with placeholders such as
  `<forge-root>`, `<target-repo>`, `<temp-dir>`, and `<workbench-port>`.

## Sidecar Portability Rules

- Default target install path is `.moradins-harness/`.
- Sidecars are copied from `Harness/moradin_payload/manifest.yaml` and sanitized
  during copy.
- Manager release evidence and private control artifacts must never be copied to
  downstream sidecars.
- Generated integration records must not preserve absolute local workspace
  paths.
- Existing root `Makefile`, `package.json`, CI files, docs, and agent files are
  preserved by default.
- Root `AGENTS.md` patching is opt-in through explicit user consent and
  `--patch-agents`.

## Portability Gate

`make public-portability-check` must:

- generate a public export,
- scan the export for forbidden private references,
- generate a disposable sidecar,
- scan the sidecar for the same forbidden references,
- verify root target files are not mutated during default sidecar apply,
- write JSON and Markdown audit reports under `public_audit/`.

Forbidden references include internal home paths, internal usernames, local
workspace placeholders, shared private tooling roots, release evidence
directories, migration report directories, branch waiver artifacts, PR hardening
artifacts, and legacy local dry-run roots.

## Authority Boundary

The export pipeline may create files only under the requested public export
directory and temporary smoke-test directory. It must not publish, push, install
host tools, or mutate target repos outside explicit Forge apply commands.
