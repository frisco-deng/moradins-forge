---
title: "Moradin Forge Public Guidance"
status: public-contract
owner: moradin-forge
---

# Moradin Forge Public Guidance

## Agent Rules

| guidance_id | rule | enforcement_anchor | operator_action | status |
| --- | --- | --- | --- | --- |
| FORGE-001 | inspect Forge and the target repo before proposing changes | FORGE.md | explain the plan before apply | active |
| FORGE-002 | require explicit user approval before writing target repo files | Harness/entrypoints/forge.md | run apply only with `--approve` | active |
| FORGE-003 | keep host tool installation request-only | docs/references/tooling_readiness_install_request_contract_v1.md | write install-request artifacts instead of installing tools | active |
| FORGE-004 | preserve root workflows by default | docs/references/moradin_forge_agent_integration_contract_v1.md | write sidecar adapters before root patches | active |
| FORGE-005 | verify sidecars for portability before handoff | scripts/moradin_forge.py | run `forge verify` or `make forge-verify` | active |
| FORGE-006 | keep bootstrap separate from adoption | docs/references/moradin_forge_installer_bootstrap_contract_v1.md | run platform bootstrap only to prime Forge and write a start card | active |
| FORGE-007 | keep beta release visuals portable and local | README.md | scan SVG assets before public release | active |
