---
title: "Moradin Forge Linux Tooling Suite Contract V1"
status: approved
owner: platform-operations
last_reviewed: 2026-07-31
source_refs:
  - ../../install/tooling-suite.sh
  - ../../scripts/moradin_tooling_suite.py
  - ../../catalog/workstation-tools.toml
related_docs:
  - tooling_readiness_install_execution_contract_v2.md
  - moradin_forge_installer_bootstrap_contract_v1.md
  - moradin_forge_agent_integration_contract_v1.md
---

# Moradin Forge Linux Tooling Suite Contract V1

## Purpose

The tooling suite gives a human one safe Linux entrypoint for the broad Forge
workstation baseline. It complements the adaptive agent workflow; it does not
change repository adoption permissions or allow an agent to approve privilege
on the user's behalf.

## Human and Agent Boundary

- The user launches `install/tooling-suite.sh` as the target non-root account.
- Agents may explain the catalog, generate a plan, and verify receipts.
- Agents must not operate the interactive menu, invoke sudo, enter credentials,
  or confirm the user's plan digest.
- For ordinary suite actions, the human-run program may invoke sudo only after
  showing the exact plan and receiving a default-No confirmation.
- When Python 3.11, a certificate store, or the downloader is unavailable, the
  entrypoint may first offer a separately displayed minimal transaction from
  the configured signed package manager. It is default-No, installs only the
  named prerequisites, and is not a tooling-plan approval.
- Planning and apply use Forge's pinned, archive- and binary-digest-verified uv
  bootstrap runtime. An unrelated `uv` or other unowned executable found on
  PATH is never executed as trusted discovery evidence.
- If a selected profile needs Python 3.12, interactive mode offers a separate
  default-No user-level install into the Forge bootstrap prefix through that
  verified uv runtime, then replans and freezes the resulting exact version.
- Python tool application points uv at that Forge-owned runtime directory,
  requires managed Python 3.12, and disables runtime downloads so installation
  cannot diverge from the approved Python 3.12 wheel closure.
- Bootstrap, onboarding, and adaptive `tooling-apply` retain their existing
  no-elevation behavior.

## Profiles and Commands

The interactive menu offers Install All, Customize, Verify, Rollback, and Exit.
Install All offers Practical and Extended profiles. Customize first selects
categories, then individual tools, and shows every manual/service
classification.

Deterministic commands are:

- `tooling-suite.sh plan --profile practical|extended --output FILE`
- `tooling-suite.sh plan --custom --select ID --output FILE`
- `tooling-suite.sh apply --plan FILE --approve-plan-sha256 SHA`
- `tooling-suite.sh bundle --plan FILE --output PATH`
- `tooling-suite.sh verify --receipt ID` or `tooling-suite.sh verify --latest`
- `tooling-suite.sh rollback --receipt FILE --approve-receipt-sha256 SHA`

Non-interactive planning requires an explicit profile or non-empty custom
selection. Extended planning requires an explicit rootless engine choice when
Docker or Podman is absent. Missing TTY input never selects a default.

## Platform and Trust

- Supported families are Debian/Ubuntu with apt, Fedora/RHEL-compatible with
  dnf, and Arch with pacman.
- Supported architectures are amd64 and arm64. Missing verified assets fail
  closed per tool.
- Latest metadata uses the existing 24-hour official-source cache. The plan
  freezes versions, package candidates, URLs, digests, trust class, selection,
  host fingerprint hash, target UID, catalog hash, and installer manifest hash.
- Standalone assets are staged without privilege and verified before sudo.
- The sudo command first seals the manifest-bound installer files into a
  root-owned, non-writable runner. No Python module from the user-writable
  checkout is executed as root; later rollback uses the same sealed runner.
- The entrypoint needs Python 3.11+ to plan; the Practical and Extended
  contracts fail closed until Python 3.12+ is actually available.
- Root network access is restricted to the selected signed package manager.
- EPEL is a separate digest-bound repository-bootstrap transaction followed by
  replanning. Arch package work requires separately approved full
  synchronization; partial upgrades are prohibited.
- `curl | bash`, AUR helpers, root pip/npm, `eval`, Docker-group membership,
  shared privileged sockets, and unverified installers are prohibited.

## Transaction and Ownership

Forge-owned global binaries use
`/opt/moradins-forge/tools/<tool>/<version>` and atomic `/usr/local/bin` links.
User tools use an XDG versioned prefix and atomic `~/.local/bin` links. Existing
unowned files or links are never replaced. Existing Docker and Podman state is
protected. A newly selected Podman engine also selects UID-map, unprivileged
network, and overlay-storage prerequisites, then must pass a target-user
rootless `podman info` check.

Selected OS packages are installed at the frozen signed candidate. Existing OS
packages upgrade only when the previous package artifact or an equivalent
reversible transaction is available at apply time. Otherwise Forge retains the
installed version and records the skip. Rollback never purges configuration or
performs an ambiguous autoremove. When a newly installed direct package is
removed, any now-ambiguous dependency packages are retained and explicitly
reported as drift.

Root receipts and backups live under `/var/lib/moradins-forge` and
`/var/backups/moradins-forge`. User receipts and path-sanitized approved-plan
copies live under the XDG state directory. Rollback requires the exact receipt
digest and preserves a shim changed by a newer generation.

## Privacy and Offline Bundles

The suite has no telemetry and uploads no workspace contents. Local plans may
contain approved workspace paths needed for discovery; portable bundles replace
them with placeholders and remove the target UID and host fingerprint.

Bundles contain only verified tool assets, frozen Python wheels, portable plan
metadata, manifests, and checksums. They report `partial` when signed OS package
assets remain connected-only. Repositories, source content, prompts,
credentials, logs, usernames, hostnames, and machine paths are excluded.
