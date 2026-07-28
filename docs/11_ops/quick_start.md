---
title: "Quick Start"
status: approved
owner: moradin-forge
last_reviewed: 2026-06-09
source_refs:
  - ../../README.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
  - ../references/moradin_forge_installer_bootstrap_contract_v1.md
---

# Quick Start

Use Forge from an agent session:

```sh
git clone https://github.com/frisco-deng/moradins-forge.git <forge-root>
cd <forge-root>
install/bootstrap-linux.sh --target <target-repo>
```

Use `install/bootstrap-macos.sh` on macOS and
`.\install\bootstrap-windows.ps1 -Target <target-repo>` on Windows PowerShell.
Bootstrap writes a sanitized start card and never installs host tools or mutates
the target repo.

Then run the adoption dry-run sequence:

```sh
scripts/moradin_forge.sh explain
scripts/moradin_forge.sh readiness --target <target-repo>
scripts/moradin_forge.sh plan --target <target-repo>
```

After the user approves:

```sh
scripts/moradin_forge.sh apply --target <target-repo> --approve
scripts/moradin_forge.sh verify --target <target-repo>
```

Rollback is deleting `.moradins-harness/` and any separately approved marked
root block.
