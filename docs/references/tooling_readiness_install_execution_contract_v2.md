---
title: "Tooling Readiness And Install Execution Contract V2"
status: approved
owner: platform-operations
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/moradin_workstation.py
  - ../../scripts/moradin_forge.py
  - ../../install/bootstrap-linux.sh
  - ../../install/bootstrap-macos.sh
  - ../../install/bootstrap-windows.ps1
related_docs:
  - tooling_readiness_install_request_contract_v1.md
  - moradin_forge_agent_integration_contract_v1.md
  - moradin_forge_installer_bootstrap_contract_v1.md
---

# Tooling Readiness And Install Execution Contract V2

## Purpose

V2 turns readiness gaps into a reviewable, digest-bound workstation plan. It
allows approved user-level installation while keeping workspace inspection,
shell configuration, privilege, external sources, integrity, and rollback as
separate boundaries.

## Commands

- `onboard --workspace PATH`
- `tooling-plan --workspace PATH --profile practical-full`
- `tooling-update-plan --workspace PATH`
- `tooling-apply --plan FILE --approve-plan-sha256 SHA`
- `tooling-bundle --plan FILE --output PATH`
- `tooling-rollback --receipt FILE --approve`

`--workspace` is repeatable. Filesystem roots and the full home directory are
rejected; users approve specific workspace subdirectories. Discovery is
bounded by repository count and depth, does not follow symlinked directories,
and stops at Git repository roots.

## Inspection Boundary

Capability detection reads the presence or bounded metadata of standard
guidance, package, lock, CI, container, deployment, and configuration files.
It does not ingest arbitrary source files. The discovered repository list is
part of the plan shown before any mutation.

## Practical-Full Catalog

Forge always evaluates core CLI, Python/uv, fast search, structured-data,
shell-QA, GitHub, and pre-commit tooling.

It recommends secrets, SAST, dependency, workflow, container, SBOM, and
supply-chain scanners only when detected repository capabilities justify
them. Container, Kubernetes, UI/browser, signing, sandbox, and CAD modules are
detection-driven or explicitly selected.

Linux/WSL, macOS, and Windows use equivalent capabilities rather than
requiring identical packages.

## Resolution and Integrity

Latest stable metadata is resolved from official HTTPS APIs or signed package
manager metadata. The result is cached for 24 hours and checked only when Forge
runs. The approved plan freezes the version, source, trust evidence, available
digests, install classification, exact argv, and plan SHA-256.

Automatic execution is allowed only for:

- a version-pinned official package whose installer verifies registry or asset
  integrity; or
- a signed package-manager action that remains inside the approved user
  context.

Unresolved, unverifiable, environment-specific, or privilege-ambiguous actions
are manual. Stale cache entries may explain a recommendation but cannot
auto-execute. A changed plan invalidates the approved digest.

## Consent and Execution

The user approves these boundaries independently:

1. workspace roots;
2. selected modules;
3. the exact plan digest for user-level execution;
4. each agent file;
5. PATH or shell-profile configuration;
6. privileged-script generation and personal execution.

Forge executes installer argv directly without a shell. The executable
allowlist is limited to the supported package paths. Forge-owned Python tools
use a versioned user data prefix and user bin directory. Receipts omit raw
commands and machine paths. Every executed action is followed by its
catalog-owned verification argv; an install or verification failure still
writes the rollback receipt.

`--approve-user-config` is required before a marked PATH block may be added.
It is never implied by tooling approval.

## Privileged Scripts

Forge never invokes elevation. It generates idempotent Bash for Linux/macOS
and PowerShell for Windows. Each script:

- defaults to a dry run;
- prints the exact package list;
- requires an explicit apply flag;
- verifies selected commands after installation;
- includes reversal guidance.

The user running that script is the acceptance event. The agent then reruns
readiness and project-native verification.

## Offline Bundles

`tooling-bundle` accepts only a valid digest-bound plan. It downloads only
official HTTPS assets with a frozen SHA-256 and fails on an integrity mismatch.
Python tools require a complete wheel-only dependency closure. Offline scripts
verify `SHA256SUMS`, disable indexes and configuration discovery, and constrain
resolution to the frozen assets. The bundle includes a portable plan, scripts,
asset manifest, and `SHA256SUMS`.

Repositories, project content, credentials, prompts, logs, usernames,
hostnames, and raw machine paths are excluded. If a verified asset is
unavailable, the bundle reports `partial` and names the blocker.

## Rollback

`tooling-rollback` removes only receipt-owned user-local tools. Shared package
manager removals remain explicit native actions. An owned PATH block is
removed only when its recorded digest still matches; modified configuration is
preserved and reported. If a shared executable shim changed after the receipt,
rollback preserves that newer generation.
