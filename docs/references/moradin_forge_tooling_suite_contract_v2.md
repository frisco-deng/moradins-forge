---
title: "Moradin Forge Tooling Suite Contract V2"
status: beta
owner: platform-operations
last_reviewed: 2026-08-31
source_refs:
  - ../../install/tooling-suite.sh
  - ../../install/tooling-suite-macos.sh
  - ../../install/tooling-suite.ps1
  - ../../scripts/moradin_tooling_suite.py
  - ../../scripts/moradin_tooling_suite_native.py
  - ../../catalog/workstation-tools.toml
related_docs:
  - moradin_forge_tooling_suite_contract_v1.md
  - tooling_readiness_install_execution_contract_v2.md
  - moradin_forge_agent_integration_contract_v1.md
  - ../11_ops/air_gapped_tooling_suite.md
---

# Moradin Forge Tooling Suite Contract V2

## Purpose and Human Boundary

V2 is the connected workstation contract for Linux/WSL, macOS, and Windows.
It provides equivalent verified capabilities without pretending the native
package ecosystems are identical. The human launches the platform entrypoint,
reviews the exact plan, and owns every elevation decision. An agent may run
`doctor`, prepare a plan, explain it, and verify a receipt; it must not launch
the installer, approve a digest, enter credentials, or trigger elevation.

| Platform | Human entrypoint | Connected provider | Complete air gap |
| --- | --- | --- | --- |
| Linux/WSL | `./install/tooling-suite.sh` | signed apt/dnf/pacman, official assets, isolated uv tools | yes, supported Linux targets |
| macOS | `./install/tooling-suite-macos.sh` | Homebrew, official assets, isolated uv tools | no |
| Windows | `.\install\tooling-suite.ps1` | WinGet, official assets, isolated uv tools | no |

All connected entrypoints provide `doctor`, `status`, `plan`, `apply`,
`verify`, and `rollback`. Linux alone provides `airgap-request`,
`airgap-build`, `airgap-verify`, and `airgap-apply`.

## V2 Records

New transactions use these public records:

- `MoradinForgeToolCatalogV2`
- `MoradinForgeToolingDoctorV1`
- `MoradinForgeToolingSuitePlanV2`
- `MoradinForgeToolingCheckpointV1`
- `MoradinForgeToolingSuiteReceiptV2`
- `MoradinForgeRootToolingReceiptV2`
- `MoradinForgeAirgapRequestV2`
- `MoradinForgeAirgapLockV2`
- `MoradinForgeAirgapBundleV2`

The plan SHA-256 binds the aggregate doctor, catalog and installer manifests,
runtime, platform backend and its verified absolute path, target identity
hash, resolved assets, package simulation, transition matrix, protected-state
digest, and rollback closure. Protected state covers existing container
engines, the native provider and absolute path, target identity, PATH digest,
and kernel/OS release digest. A 24-hour plan cannot authorize a different
host, user, provider, catalog, installer, or asset.

`doctor` is network-free and returns all detected blockers in one result.
Resolution and staging occur only after doctor. Progress goes to stderr; a
non-interactive command emits one JSON result on stdout. Plans and receipts do
not contain prompts, source, workspace contents, credentials, hostnames, raw
user identity, or telemetry.

When isolated Python tools are selected before `uv` is installed, planning
stages an official digest-verified platform uv archive in user-owned state,
rehashes and extracts it on every use, and binds both archive and executable
digests into the plan. This planner runtime freezes the wheel closure; it does
not pre-approve installation or replace the selected native `uv` package.

## Transactions, Checkpoints, and Compatibility

Assets are staged without elevation and verified against the approved plan.
Each completed component receives a digest-bound checkpoint. A retry during
the plan lifetime validates and resumes completed components. A fresh plan
after expiry detects already-current components and does not redownload them.
Reapplying a completed plan verifies its receipt without mutation.

Missing native packages receive an uninstall rollback closure before apply.
An older macOS or Windows package is reported as `preserved` when its provider
cannot freeze an exact prior artifact; Forge does not trade rollback safety for
an automatic upgrade.

Linux package managers are resolved to root-owned, non-writable absolute
paths. The sealed Linux root phase uses a fixed environment, allowlisted argv,
atomic Forge prefixes, root receipts, and bounded rollback. macOS executes
approved user-level Homebrew and uv actions. Windows emits an exact WinGet
PowerShell script for the human to review and run; the agent and native engine
do not hide elevation. Windows rollback likewise emits a bound uninstall
script and reports `awaiting-human` until the elevated packages are absent;
it never reports a completed rollback while that phase remains outstanding.

V1 plans expire normally and cannot authorize V2 work. Existing
`MoradinForgeToolingSuiteReceiptV1` and
`MoradinForgeRootToolingReceiptV1` records remain digest-readable and
rollback-capable. The V1 contract remains the compatibility reference and is
not the contract for new installations.

## Profiles

Practical remains the recommended daily baseline. Extended includes Practical
plus containers, Kubernetes, UI/test support, archive tooling, Ruff, Pyright,
OpenTofu, TFLint, terraform-docs, Ansible, Argo CD, rclone, Velero, Skopeo,
crane, ClamAV, YARA, ModelScan, cargo-audit, and cargo-deny where a verified
provider exists.

Terraform and Packer are visibly classified as BUSL and remain manual. VMware,
Sonar services, OpenJDK, browsers, hardened clusters, CAD, STIG/RKE2, and
facility services remain evidence-driven or manual. Unsupported provider or
architecture combinations fail closed or become explicit manual handoffs.

Existing Docker/Podman, GPU/kernel, package-manager, PATH, and unrelated
configuration are protected. Forge never uses remote shell installers, root
pip/npm, AUR helpers, Docker-group membership, or hidden elevation.

## Release Acceptance

V2 changes require fake-backend transaction tests, native macOS and Windows
contract tests, disposable Linux lifecycle and air-gap tests, V1 receipt
coverage, malicious-path and digest checks, security/SBOM/leak gates, public
portability, context preservation, reproducible release builds, and human
review. Beta.4 remains a prerelease even when these gates pass.
