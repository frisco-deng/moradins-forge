---
title: "Moradin Forge Air-Gapped Tooling Suite"
status: beta
owner: platform-operations
last_reviewed: 2026-07-31
source_refs:
  - ../../install/tooling-suite.sh
  - ../../scripts/moradin_airgap_bootstrap.py
  - ../../scripts/moradin_airgap_request.py
  - ../../scripts/moradin_airgap.py
  - ../../scripts/moradin_tooling_suite.py
related_docs:
  - ../references/moradin_forge_tooling_suite_contract_v1.md
  - ../references/moradin_forge_agent_integration_contract_v1.md
  - ../references/moradin_forge_public_export_contract_v1.md
---

# Moradin Forge Air-Gapped Tooling Suite

## Purpose and Boundary

This runbook builds one complete Linux tooling kit for one selected
distribution/version, architecture, and Practical or Extended profile. It is
the only Forge interface allowed to call an offline installation complete.
The older `bundle` command remains an asset-only compatibility path and may be
partial.

The user owns workspace scope, kit transport, the out-of-band digest, stale-kit
approval, and the sudo confirmation. An agent may explain commands, inspect
sanitized records, and verify receipts; it does not enter credentials or
approve the root phase for the user.

Supported targets are Ubuntu 24.04, Debian 12, Fedora 44, and Rocky Linux 9 on
amd64 or arm64, plus a frozen Arch snapshot on amd64. Other targets fail
closed. Arch arm64 remains unsupported because upstream's official Arch
container and dated snapshot trust lane is x86-64-only; Forge does not silently
substitute an Arch Linux ARM port or an unofficial snapshot mirror.

## Round Trip

### 1. Disconnected target: create the request

```sh
./install/tooling-suite.sh airgap-request \
  --profile practical \
  --output REQUEST.json
```

Use `--profile extended` only when its complete target closure is required.
Use repeatable `--exclude <tool-id>` to explicitly remove manual-only or
unwanted entries. Rocky EPEL requires `--approve-repository epel`. Arch also
requires both a frozen `--arch-snapshot YYYY/MM/DD` and
`--approve-arch-package-inventory` because its full package inventory is part
of the synchronized rollback boundary.

`AirgapRequestV1` records selected tools, target platform, relevant installed
package state, approved repositories, and catalog/installer digests. It omits
workspace content, raw paths, credentials, prompts, hostnames, and machine
identifiers. Review it before transport.

For APT targets, relevant state includes only sanitized package solver fields:
package, version, architecture, dependency relationships, conflicts,
replacement relationships, essential status, and multi-architecture status.
It excludes descriptions, configuration, file lists, conffile hashes, and
paths. The connected builder feeds this bounded state to APT's simulator so
the sealed closure represents the target's actual additions and upgrades,
instead of upgrading dependencies that the target already satisfies.

The disconnected request generator requires only a root-owned Python 3.9+.
It emits the same strict schema as the main Python 3.11+ engine and does not
install or download anything.

### 2. Connected machine: build the sealed kit

Use a clean public Forge commit and an existing rootless Podman or rootless
Docker engine. The builder does not require sudo, Docker-group membership,
private registries, or credentials.

```sh
./install/tooling-suite.sh airgap-build \
  --request REQUEST.json \
  --output KIT.tar.gz
```

The command writes `KIT.tar.gz.lock.json` beside the kit. Rebuild from the
frozen lock when every content-addressed asset remains available:

```sh
./install/tooling-suite.sh airgap-build \
  --lock KIT.tar.gz.lock.json \
  --output KIT-REBUILT.tar.gz
```

The rebuild must be byte-identical. The kit includes a sanitized single-commit
Forge Git bundle and source snapshot, pinned uv and managed Python, standalone
binaries, Python wheels, the target's complete signed package dependency and
rollback closure, trust metadata, a portable suite plan, SPDX SBOM,
`SHA256SUMS`, and `README-AIRGAP.md`.

Transport the kit and its printed SHA-256 digest through separate trusted
channels. Do not place a digest beside an untrusted kit and treat that as
out-of-band verification.

### 3. Disconnected target: verify and apply

```sh
./install/tooling-suite.sh airgap-verify \
  --bundle KIT.tar.gz \
  --expected-sha256 <separately-transported-sha256>

./install/tooling-suite.sh airgap-apply \
  --bundle KIT.tar.gz \
  --approve-bundle-sha256 <separately-transported-sha256>
```

Interactive apply displays additions, upgrades, disk bytes, repository
behavior, rollback limits, and the newly host-bound plan digest before a
default-No confirmation. Non-interactive apply also requires
`--approve-offline-plan-sha256 <displayed-plan-sha256>`.

Kits older than 30 days remain usable, but require a second exact
`--approve-stale-bundle-sha256` value. An unchanged, already receipted kit
performs verification without mutation.

After installation, onboard approved repositories without metadata refresh:

```sh
scripts/moradin_forge.sh onboard \
  --workspace <approved-workspace> \
  --offline \
  --agent-provider codex
```

Repeat `--agent-provider` for Claude, Copilot, Gemini, or Cursor as applicable.
Onboarding shows exact diffs and never implies consent to create or patch them.

## Trust and Network Controls

- The builder uses a digest-pinned target image through an existing rootless
  engine.
- APT packages are tied to Packages indexes covered by verified InRelease
  signatures. A target-bound APT simulation determines the exact transaction
  before download; RPM and Pacman package signatures are verified natively.
- The lock binds every payload path, byte size, digest, target, profile,
  catalog, installer, package state, and rollback asset.
- The kit materializes uv-managed Python links into regular files and binds
  every runtime file, mode, size, digest, and executable. Python 3.9/3.10
  targets use a narrow verifier to launch that Python 3.12.8 runtime; the sudo
  boundary then copies the same manifest exactly into a root-owned runtime
  store before executing privileged Forge code.
- Target extraction rejects traversal, duplicate members, links, devices,
  oversized files, unknown schemas, platform mismatch, and package-state
  drift.
- Offline apply disables APT source lists and proxies, disables all DNF repos,
  and gives Pacman only local package files. Python installation uses
  `--offline`, `--no-index`, and `--no-python-downloads`.
- The sealed sudo phase uses the same atomic shims, receipts, rollback, fixed
  environment, and argv allowlists as connected installation.
- No telemetry or upload occurs. Plans, locks, kits, and receipts contain no
  workspace content, credentials, prompts, raw machine identity, or private
  Forge history.

## Provider Integration

Forge recognizes only these repository paths:

- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`
- `.cursor/rules/moradin-forge.mdc`

Lowercase or near-miss paths are warnings. The dedicated Cursor rule refuses
an existing unowned file. Every create or patch requires its own
`--approve-agent-file`; creation additionally requires the matching
`--create-agent-file`.

These conventions correspond to the providers' documented repository
instruction surfaces: [GitHub Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions),
[Gemini `GEMINI.md`](https://geminicli.com/docs/cli/gemini-md/), and
[Cursor project rules](https://docs.cursor.com/context/rules).

## Failure and Recovery

If build fails, its temporary tree is removed and no complete status is
written. If target validation fails before sudo, no installation occurs. A
partial apply automatically rolls back safely reversible root, user, uv, and
managed-Python changes; ambiguous shared package dependencies are retained and
reported instead of autoremove or configuration purge.

Never move or rewrite an approved lock to hide missing assets. Create a new
request when the target package state, distro, architecture, profile, catalog,
or installer changes.

Git bundle behavior follows the official
[Git bundle documentation](https://git-scm.com/docs/git-bundle). Native package
trust follows [APT secure archives](https://manpages.debian.org/testing/apt/apt-secure.8.en.html),
[DNF repository synchronization](https://dnf-plugins-core.readthedocs.io/en/stable/reposync.html),
and [Pacman](https://man.archlinux.org/man/pacman.8.en).
