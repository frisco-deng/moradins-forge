---
title: "Quick Start"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-31
source_refs:
  - ../../README.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
  - ../references/tooling_readiness_install_execution_contract_v2.md
  - ../references/moradin_forge_installer_bootstrap_contract_v1.md
  - air_gapped_tooling_suite.md
---

# Quick Start

The primary connected flow has three steps:

1. Clone Forge over HTTPS.
2. The user runs and approves the guided Linux tooling suite.
3. The agent onboards only approved workspace roots and shows each supported
   provider-file diff for separate consent.

```sh
git clone https://github.com/frisco-deng/moradins-forge.git <forge-root>
cd <forge-root>
./install/tooling-suite.sh
scripts/moradin_forge.sh onboard --workspace <approved-workspace>
```

The suite prints a copyable prompt for step 3. Use repeatable
`--agent-provider codex|claude|copilot|gemini|cursor` when an additional
provider file does not already exist.

For the compatibility start-card-only path, use
`install/bootstrap-linux.sh --target <target-repo>` on Linux,
`install/bootstrap-macos.sh --target <target-repo>` on macOS, or
`.\install\bootstrap-windows.ps1 -Target <target-repo>` in Windows PowerShell.
Those bootstraps write a sanitized start card and never adopt the target.

For a disconnected Linux target, follow the complete request/build/verify/apply
round trip, then add `--offline` to onboarding:

```sh
./install/tooling-suite.sh airgap-request --profile practical --output REQUEST.json
# Transfer REQUEST.json to a connected rootless builder.
./install/tooling-suite.sh airgap-build --request REQUEST.json --output KIT.tar.gz
# Return KIT.tar.gz and transport its digest separately.
./install/tooling-suite.sh airgap-verify --bundle KIT.tar.gz --expected-sha256 <sha256>
./install/tooling-suite.sh airgap-apply --bundle KIT.tar.gz --approve-bundle-sha256 <sha256>
scripts/moradin_forge.sh onboard --workspace <approved-workspace> --offline
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
