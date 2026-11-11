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
| FORGE-003 | execute only digest-approved, verified user-level tooling actions | docs/references/tooling_readiness_install_execution_contract_v2.md | review the exact plan digest before `tooling-apply` | active |
| FORGE-004 | preserve root workflows by default | docs/references/moradin_forge_agent_integration_contract_v1.md | write sidecar adapters before root patches | active |
| FORGE-005 | verify sidecars for portability before handoff | scripts/moradin_forge.py | run `forge verify` or `make forge-verify` | active |
| FORGE-006 | keep bootstrap separate from adoption | docs/references/moradin_forge_installer_bootstrap_contract_v1.md | run platform bootstrap only to prime Forge and write a start card | active |
| FORGE-007 | keep beta release visuals portable and local | README.md | scan SVG assets before public release | active |
| FORGE-008 | inspect only explicitly approved workspace roots | docs/references/tooling_readiness_install_execution_contract_v2.md | show discovered repositories before capability inspection | active |
| FORGE-009 | require independent approval for each agent file and user configuration change | docs/references/moradin_forge_agent_integration_contract_v1.md | show the owned block and request each consent separately | active |
| FORGE-010 | agents never invoke elevation or approve a human confirmation | docs/references/moradin_forge_tooling_suite_contract_v1.md | the user launches the suite and approves its sealed sudo phase | active |
| FORGE-011 | bind upgrades to an exact plan and retain one predecessor | docs/references/moradin_forge_upgrade_contract_v1.md | stage, validate, switch, or restore byte-for-byte | active |
| FORGE-012 | store sanitized efficiency counters only | docs/references/moradin_agent_efficiency_contract_v1.md | omit prompts, source, commands, paths, and logs | active |
| FORGE-013 | call an offline installation complete only when its target-specific package, trust, runtime, tool, and rollback closure is sealed | docs/11_ops/air_gapped_tooling_suite.md | use `airgap-build`; label compatibility `bundle` output partial | active |
