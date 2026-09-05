---
title: "Moradin Forge Repo Operating Model V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-08-31
source_refs:
  - ../../README.md
  - ../../AGENTS.md
related_docs:
  - moradin_forge_public_export_contract_v1.md
  - moradin_forge_agent_integration_contract_v1.md
  - moradin_forge_installer_bootstrap_contract_v1.md
  - moradin_forge_release_artifact_contract_v1.md
  - tooling_readiness_install_request_contract_v1.md
  - tooling_readiness_install_execution_contract_v2.md
  - moradin_forge_tooling_suite_contract_v1.md
  - moradin_forge_tooling_suite_contract_v2.md
  - moradin_forge_upgrade_contract_v1.md
---

# Moradin Forge Repo Operating Model V1

## Purpose

Moradin's Forge is maintained from the public product repository. Normal
features, fixes, documentation updates, tests, and release work happen on public
branches in this repo.

## Public Work Rules

- Create public branches from `main` for normal product work.
- Keep `main` protected with required `verify`, `security`, and
  `dependency-readiness` checks. Dependency submission remains a protected
  `main` post-merge operation because its write permission cannot run on pull
  requests.
- Keep dependency graph, Dependabot security updates, secret scanning, and push
  protection enabled.
- Run portability and sidecar leak checks before every public PR or release.
- Keep public docs generic; use `<forge-root>`, `<target-repo>`, `<temp-dir>`,
  and `<workbench-port>` placeholders.
- Use HTTPS clone examples in public docs. SSH remotes are local operator
  configuration and must not appear in public guidance or generated evidence.
- Keep optional UI visual, release-candidate promotion, platform signing and
  smoke, CAD, and GPU helper lanes out of default Forge targets until each lane
  has approved evidence and a human promotion gate.
- Keep dependency submission enabled for the public repository, including the
  `uv.lock` detector.
- Keep scheduled dependency/security auditing enabled even when hosted
  Dependabot reports no open alerts.
- Run the universal agent contract on Linux, macOS, and Windows CI runners.
  This platform test matrix does not activate signing or production promotion.

## Required Public Gates

Use these gates before public PRs and releases:

- `make test`
- `make verify-ci`
- `make verify-security`
- `make dependency-readiness`
- `make payload-validate`
- `make payload-smoke`
- `make forge-smoke`
- `make release-build`
- `make public-portability-check`
- `install/bootstrap-linux.sh --dry-run --json`
- `install/tooling-suite.sh plan --custom --select git --output <temp-dir>/plan.json`
- `install/tooling-suite-macos.sh doctor --output json`
- `install/tooling-suite.ps1 doctor --output json`
- ShellCheck and shfmt for `install/tooling-suite.sh`
- native Linux, macOS, and Windows onboarding/installer contract CI
- `npm --prefix dev_tracker/ui ci`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
- `npm --prefix dev_tracker/ui audit --audit-level=moderate`
- SVG asset scan for `script`, `http`, `file:`, raw home paths, hostnames,
  usernames, and SSH remotes.
- `tpl-release-candidate-audit --repo moradins-forge --format md`

For adoption behavior changes, also run a fresh sidecar smoke against a
disposable target repo and verify the target root files are preserved by
default. For release changes, reproduce `make release-build` from a fresh
public clone and compare `artifacts/release/SHA256SUMS`.
