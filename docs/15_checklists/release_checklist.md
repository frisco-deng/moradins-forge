---
title: "Release Checklist"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../references/repo_operating_model_v1.md
related_docs:
  - project_builder_release_checklist.md
  - ../references/moradin_forge_release_artifact_contract_v1.md
---

# Release Checklist

- [ ] `make test`
- [ ] `make verify-ci`
- [ ] `make verify-security`
- [ ] `make payload-validate`
- [ ] `make payload-smoke`
- [ ] `make forge-smoke`
- [ ] `make release-build`
- [ ] `make public-portability-check`
- [ ] `make verify-paths`
- [ ] `tpl-release-candidate-audit --repo moradins-forge --format md`
- [ ] `install/bootstrap-linux.sh --dry-run --json`
- [ ] SVG assets pass the forbidden-content scan.
- [ ] UI tests, build, and audit if the workbench ships.
- [ ] A fresh public clone reproduces `artifacts/release/SHA256SUMS` without
      access to a private Harness repository.
- [ ] GitHub Actions pass on protected `main`.
