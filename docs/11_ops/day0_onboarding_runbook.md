---
title: "Day 0 Onboarding Runbook"
status: approved
owner: platform-operations
last_reviewed: 2026-06-09
source_refs: []
related_docs:
  - codex_run_loop.md
  - ../references/moradin_forge_installer_bootstrap_contract_v1.md
  - docs/entrypoint_guide/index.md
  - ../15_checklists/agent_cycle_gate.md
---

# Day 0 Onboarding Runbook

## Purpose

- Bring a new engineer/operator to a deterministic local-ready state for harness execution.

## Checklist

- [ ] Clone with HTTPS: `git clone https://github.com/frisco-deng/moradins-forge.git <forge-root>`.
- [ ] Run the platform bootstrap with `--target <target-repo>`; use `--dry-run --json` first when reviewing a new host.
- [ ] Review `artifacts/bootstrap/latest/agent_start.md` if bootstrap wrote one.
- [ ] Run `make repo-brief` and follow the reported Python runtime route.
- [ ] Run `make verify-fast`, `make verify-paths`, and `make public-portability-check`.
- [ ] Use `make verify-security` before a public PR, release, or security-sensitive change.
- [ ] Run `npm --prefix dev_tracker/ui run test` and `npm --prefix dev_tracker/ui run build` when UI files changed.
- [ ] Keep host installs request-only; do not run `sudo`, `brew`, `winget`, or global Git credential rewrites from Forge automation.
