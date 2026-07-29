---
title: "Quick Start"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../README.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
  - ../references/tooling_readiness_install_execution_contract_v2.md
  - ../references/moradin_forge_installer_bootstrap_contract_v1.md
---

# Quick Start

Clone over HTTPS and prime Forge:

```sh
git clone https://github.com/frisco-deng/moradins-forge.git <forge-root>
cd <forge-root>
install/bootstrap-linux.sh --target <target-repo>
```

Use `install/bootstrap-macos.sh` on macOS or
`.\install\bootstrap-windows.ps1 -Target <target-repo>` in Windows PowerShell.
Bootstrap writes a sanitized start card and never adopts the target.

Ask the user for an approved workspace and create the composite plan:

```sh
scripts/moradin_forge.sh onboard --workspace <approved-workspace>
```

Review the discovered repositories, tool actions, user configuration,
privileged scripts, and exact agent blocks. Apply user-level tooling only with
the displayed plan digest.

Then use the compatibility adoption sequence:

```sh
scripts/moradin_forge.sh readiness --target <target-repo>
scripts/moradin_forge.sh plan --target <target-repo>
scripts/moradin_forge.sh apply --target <target-repo> --approve
scripts/moradin_forge.sh verify --target <target-repo>
```

Use the explicit `rollback` or transactional `upgrade-*` commands instead of
manually deleting the sidecar.
