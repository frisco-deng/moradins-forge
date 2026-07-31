# Moradin's Forge

## Agent: Start Here

Moradin's Forge is a public, standalone baseline for Codex, Claude Code, and
other coding agents. If a user points you at this repository, treat the text
below as the onboarding contract.

```text
You are at Moradin's Forge.

1. Read README.md, FORGE.md, AGENTS.md, and
   Harness/entrypoints/forge.md. Also read the target repository's own
   guidance before proposing changes.
2. Ask which workspace roots the user approves. Never infer approval for a
   home directory, filesystem root, sibling workspace, or repository outside
   the paths they name. Forge rejects filesystem roots and the full home
   directory; ask for specific workspace subdirectories.
3. Run `scripts/moradin_forge.sh onboard --workspace <approved-root>` once for
   each approved root. On Windows use `scripts\moradin_forge.ps1`. Show the
   discovered repository list before inspecting deeper.
4. Inspect only repository guidance, manifests, CI, container, deployment, and
   standard configuration files. Do not crawl arbitrary source contents.
5. Present the generated composite plan and ask separately for:
   - the workspace scope;
   - selected tooling modules;
   - user-level installation execution;
   - each AGENTS.md or CLAUDE.md file to create or patch;
   - PATH or shell-profile configuration;
   - privileged-script generation and the user's execution of that script.
6. Execute only approved user-level actions. Agents never enter credentials,
   run sudo, or launch the interactive host installer for the user. A human may
   run `install/tooling-suite.sh`; for normal tool actions that human-run
   program may request sudo only after displaying and digest-binding the exact
   root transaction. A missing runtime/downloader may trigger a separate
   default-No prompt for named signed-manager prerequisites. The older adaptive
   flow continues to generate a reviewable privileged script for the user.
   Verify either path afterward.
7. Apply the sidecar and each approved agent marker block transactionally.
   Preserve unrelated files and guidance. Run security and repository-native
   validation, then report exact writes and rollback commands.

Automatically executable installers must use an official source plus a
verified checksum/signature, or a signed package-manager path. Classify
unverifiable installers as manual. Never publish project contents, credentials,
prompts, raw paths, or logs.
```

The shortest first command is:

```sh
scripts/moradin_forge.sh onboard --workspace <approved-workspace>
```

Repeat `--workspace` for multiple approved roots. `onboard` discovers Git
repositories only beneath those roots, reports the list before deeper
inspection, detects capabilities from standard project surfaces, and writes a
digest-bound plan under ignored local artifacts.

## What the User Approves

Forge separates approval into distinct boundaries:

| Boundary | Approval |
| --- | --- |
| Workspace discovery | Each `--workspace` path |
| Tool selection | Included practical-full modules |
| User-owned installs | Exact tooling-plan SHA-256 |
| `AGENTS.md` | `--approve-agent-file AGENTS.md` |
| `CLAUDE.md` | `--approve-agent-file CLAUDE.md` |
| Missing agent file creation | Matching `--create-agent-file` |
| PATH or shell profile | `--approve-user-config` |
| Privileged packages | Generate, review, and personally run the script |
| Interactive Linux suite | Personally launch it and confirm the exact plan digest |
| Sidecar adoption | `apply --approve` |
| Sidecar upgrade | Exact upgrade-plan SHA-256 |
| Rollback | Explicit `--approve` |

Lowercase `agents.md`, `agent.md`, `claude.md`, and `claud.md` are reported as
warnings; Forge patches only the canonical root `AGENTS.md` and `CLAUDE.md`.
Their independently owned marker blocks preserve all unrelated guidance.

## Platform Bootstrap

Clone Forge over HTTPS and run the platform bootstrap. Bootstrap primes Forge
and writes a sanitized start card; it never adopts a target repository.

Linux or WSL:

```sh
git clone https://github.com/frisco-deng/moradins-forge.git <forge-root>
cd <forge-root>
install/bootstrap-linux.sh --target <target-repo>
```

macOS:

```sh
git clone https://github.com/frisco-deng/moradins-forge.git <forge-root>
cd <forge-root>
install/bootstrap-macos.sh --target <target-repo>
```

Windows PowerShell:

```powershell
git clone https://github.com/frisco-deng/moradins-forge.git <forge-root>
Set-Location <forge-root>
.\install\bootstrap-windows.ps1 -Target <target-repo>
```

When the Python prerequisite is absent, bootstrap generates a small,
reviewable prerequisite script under `artifacts/bootstrap/latest/`. Linux
privileged installation requires the user to run its `sudo` command; Windows
requires the user to run the generated elevated PowerShell script. Forge never
elevates itself.

## Onboarding and Tooling

### Interactive Linux baseline

For the simplest complete workstation path on Linux or WSL, the user runs:

```sh
install/tooling-suite.sh
```

The first menu offers **Install All** or **Customize**. Install All then offers
the recommended Practical profile or the broader Extended profile. The program
runs as the target user, stages checksum-verified assets without privilege, and
shows additions, upgrades, manual items, repository changes, rollback limits,
disk estimates, and the exact plan SHA-256. Only after a default-No
confirmation does the human-run program invoke sudo for the bound root phase.
If Python 3.11 or download prerequisites are missing, it may first offer a
separate, minimal signed-package-manager bootstrap; that prompt is also
default-No and is not plan approval. If a selected full profile needs Python
3.12, the suite separately offers a user-level, verified-uv install into the
Forge bootstrap prefix and replans before any host-tool approval.

The suite supports apt, dnf, and pacman families on amd64 and arm64. It never
uses `curl | bash`, AUR helpers, root pip/npm, or the Docker group. It performs
no general OS upgrade except the separately shown and approved Arch
synchronization required to avoid partial upgrades. EPEL also requires a
separate confirmation. Existing Docker or Podman configuration is preserved.

Planning uses a pinned uv archive whose archive and executable digests are both
checked; it does not trust an unrelated `uv` or execute arbitrary unowned PATH
tools for version discovery. Before sudo runs any Forge Python, the approved
installer snapshot is rehashed and atomically sealed under a root-owned runner
directory. Python tools are installed against the same Forge-managed Python
3.12 family used to freeze their wheel lock, with runtime downloads disabled.
Rollback uses the sealed runner rather than mutable checkout code. A new Podman
selection includes rootless namespace, network, and storage prerequisites and
must pass `podman info` as the target user.

Deterministic automation uses the same catalog and transaction engine:

```sh
install/tooling-suite.sh plan --profile practical --output <tooling-suite-plan.json>
install/tooling-suite.sh apply \
  --plan <tooling-suite-plan.json> \
  --approve-plan-sha256 <sha256>
install/tooling-suite.sh verify --latest
```

Use `--profile extended --container-engine podman` for the extended baseline,
or `--custom --select <tool-id>` with repeatable `--select` and `--exclude`.
Build a checksummed asset bundle with `bundle --plan ... --output ...`; the
bundle reports `partial` when signed OS packages remain connected-only.

OS package upgrades occur only when the previous package artifact or an
equivalent reversible transaction is available. Otherwise the installed
version is retained and reported. Forge-owned binaries use atomic versioned
shims and keep one predecessor. Root receipts live under
`/var/lib/moradins-forge`, backups under `/var/backups/moradins-forge`, and
matching user receipts under the XDG state directory.
New direct packages are removed without autoremove during rollback; potentially
shared dependency packages are retained and reported instead of being purged.

Agents may propose the command, inspect a plan, and verify its receipt. The
human must launch and approve the sudo-capable path personally.

### Adaptive workspace plan

Create the adaptive practical-full plan:

```sh
scripts/moradin_forge.sh tooling-plan \
  --workspace <approved-workspace> \
  --profile practical-full
```

The plan always evaluates core CLI, Python/uv, search, structured-data, shell
QA, GitHub, and pre-commit capabilities. It recommends secrets, SAST,
dependency, workflow, container, SBOM, and supply-chain tools only when project
evidence supports them. Container, Kubernetes, UI/browser, signing, sandbox,
and CAD lanes remain opt-in or detection-driven.

Latest stable metadata is resolved from official sources and cached for 24
hours. The plan freezes the resolved version, URL, trust evidence, digest when
available, action class, and exact argv. A missing digest or trustworthy
package route makes the action manual.

After reviewing the plan JSON and its `plan_sha256`, the user may approve exact
user-level actions:

```sh
scripts/moradin_forge.sh tooling-apply \
  --plan <tooling-plan.json> \
  --approve-plan-sha256 <sha256>
```

Add `--approve-user-config` only after separate PATH/shell-profile consent.
Forge-owned user tools use a versioned user prefix, atomic shims, and rollback
receipts. Privileged actions are emitted as idempotent Bash or PowerShell
scripts with dry-run behavior, package lists, verification, and reversal
guidance; the user runs them directly. Forge rechecks every executed
user-level action. A failed install or verification still writes a receipt,
and rollback preserves a shim that a newer generation has replaced. To remove
only receipt-owned user-local tools:

```sh
scripts/moradin_forge.sh tooling-rollback \
  --receipt <receipt.json> \
  --approve
```

Build a portable offline bundle:

```sh
scripts/moradin_forge.sh tooling-bundle \
  --plan <tooling-plan.json> \
  --output <bundle-directory>
```

Bundles contain tool assets, manifests, scripts, checksums, and verification
data only. They exclude repositories, source content, credentials, prompts,
logs, and machine paths. Python tools use a complete wheel-only closure,
frozen constraints, and offline/no-index/no-config installation. Unavailable
verified assets leave an honest `partial` bundle instead of silently weakening
integrity.

Tool update checks run only when Forge is invoked and the 24-hour cache is
stale:

```sh
scripts/moradin_forge.sh tooling-update-plan \
  --workspace <approved-workspace>
```

There is no background updater.

## Adopt a Repository

The compatibility flow remains available:

```sh
scripts/moradin_forge.sh explain
scripts/moradin_forge.sh readiness --target <target-repo>
scripts/moradin_forge.sh plan --target <target-repo>
scripts/moradin_forge.sh apply --target <target-repo> --approve
scripts/moradin_forge.sh verify --target <target-repo>
```

Readiness automatically creates an install plan when it finds gaps. Missing
required runtime tools block later work; missing recommended tools remain
selectable.

To add independently approved guidance blocks:

```sh
scripts/moradin_forge.sh apply \
  --target <target-repo> \
  --approve \
  --approve-agent-file AGENTS.md \
  --approve-agent-file CLAUDE.md
```

For an absent canonical file, add the matching
`--create-agent-file AGENTS.md` or `--create-agent-file CLAUDE.md`. Forge shows
the exact marked patch first and never replaces unrelated content.
`--patch-agents` remains a compatibility alias for approving `AGENTS.md`.

The adoption writes:

- `.moradins-harness/`, copied from the public payload manifest;
- adaptive sidecar snippets for detected repository surfaces;
- an ownership record and deterministic verification evidence;
- only the separately approved Moradin marker blocks in root agent files.

Existing build files, workflows, manifests, source, and unrelated agent
guidance remain untouched.

## Agent Efficiency Baseline

The adopted sidecar includes standalone, public equivalents of the compact
`.templates` workflow:

```sh
scripts/moradin_forge.sh context-primer --target <target-repo>
scripts/moradin_forge.sh state --target <target-repo>
scripts/moradin_forge.sh repo-brief --target <target-repo>
scripts/moradin_forge.sh rerun-advice --target <target-repo> -- <command>
scripts/moradin_forge.sh session-checkpoint \
  --target <target-repo> --outcome pass -- <command>
scripts/moradin_forge.sh diagnostic-brief
```

The primer is capped at 6 KiB and emits exactly one next action. Generated
guidance tells agents to prefer repository-native commands, fresh summaries,
and evidence reuse before raw logs or expensive reruns, while expanding context
for missing, contradictory, security-sensitive, or release-critical evidence.

Sanitized local counters record only summarized-byte counts, avoided reruns,
command outcomes, and evidence-reuse counts. Forge stores no prompts, source
text, raw commands, raw paths, or logs.

## Transactional Upgrades and Rollback

Upgrades are digest-bound and stage the replacement before an atomic switch:

```sh
scripts/moradin_forge.sh upgrade-plan --target <target-repo>
scripts/moradin_forge.sh upgrade \
  --target <target-repo> \
  --plan <upgrade-plan.json> \
  --approve-plan-sha256 <sha256>
```

Forge validates the current sidecar and owned marker blocks, rejects stale
plans, preserves unrelated guidance, and retains exactly one Forge-owned
predecessor. A failed switch restores the sidecar and managed blocks
byte-for-byte.

Restore that immediate predecessor with:

```sh
scripts/moradin_forge.sh upgrade-rollback \
  --target <target-repo> \
  --upgrade-id <upgrade-id> \
  --approve
```

Remove an unmodified adoption with:

```sh
scripts/moradin_forge.sh rollback --target <target-repo> --approve
```

Use the explicit commands rather than deleting the sidecar manually; ownership
checks refuse unowned or modified managed content.

## Visual Overview

![Adoption flow](docs/assets/readme/adoption-flow.svg)

![Safety boundary](docs/assets/readme/safety-boundary.svg)

![What gets written](docs/assets/readme/written-surface.svg)

![Token-saving start path](docs/assets/readme/token-saving-start.svg)

## Public Command Surface

- `make repo-brief`
- `make verify-paths`
- `make verify-fast`
- `make verify-security`
- `make review-ready`
- `make push-gate`
- `make forge-explain`
- `make forge-onboard WORKSPACE=<approved-workspace>`
- `make forge-tooling-suite`
- `make forge-tooling-suite-plan OUTPUT=<plan.json> PROFILE=practical`
- `make forge-tooling-suite-apply PLAN=<plan.json> PLAN_SHA256=<digest>`
- `make forge-tooling-suite-bundle PLAN=<plan.json> OUTPUT=<directory>`
- `make forge-tooling-suite-verify RECEIPT=<receipt.json>`
- `make forge-tooling-suite-rollback RECEIPT=<receipt.json> APPROVE_RECEIPT_SHA256=<digest>`
- `make forge-tooling-plan WORKSPACE=<approved-workspace>`
- `make forge-tooling-apply PLAN=<plan.json> PLAN_SHA256=<digest>`
- `make forge-tooling-bundle PLAN=<plan.json> OUTPUT=<directory>`
- `make forge-readiness`
- `make forge-plan TARGET=<target-repo>`
- `make forge-adopt TARGET=<target-repo> APPROVE=1`
- `make forge-verify TARGET=<target-repo>`
- `make forge-upgrade-plan TARGET=<target-repo>`
- `make forge-upgrade TARGET=<target-repo> PLAN=<plan.json> PLAN_SHA256=<digest>`
- `make forge-upgrade-rollback TARGET=<target-repo> UPGRADE_ID=<id> APPROVE=1`
- `make forge-rollback TARGET=<target-repo> APPROVE=1`
- `make forge-smoke`
- `make forge-dogfood-smoke`
- `make forge-release-artifacts`
- `make release-build`
- `make payload-validate`
- `make payload-smoke`
- `make public-portability-check`
- `make test`

`make public-portability-check` validates a sanitized public tree and sidecar
for host-specific data and private dependencies. `make release-build` produces
the reproducible archive, SPDX SBOM, manifest, and checksums under
`artifacts/release/`; disposable dogfood proof stays under
`artifacts/dogfood/`.

## Release Boundary

Beta.3 adds three-platform onboarding and plan validation, but it does not
claim stable production readiness. Signing, production-readiness,
release-candidate-manifest, and production promotion remain separate human
gates. Forge does not create or imply a `prod` branch or environment.

Before a public prerelease, run the repository-native security, SBOM, leak,
payload, portability, fresh-clone, release-build, and review-ready gates. The
public payload must remain independent of private Moradin Harness history and
host-specific state.

## Key Contracts

- [Agent integration contract](docs/references/moradin_forge_agent_integration_contract_v1.md)
- [Tooling execution contract](docs/references/tooling_readiness_install_execution_contract_v2.md)
- [Linux tooling suite contract](docs/references/moradin_forge_tooling_suite_contract_v1.md)
- [Installer bootstrap contract](docs/references/moradin_forge_installer_bootstrap_contract_v1.md)
- [Transactional upgrade contract](docs/references/moradin_forge_upgrade_contract_v1.md)
- [Agent efficiency contract](docs/references/moradin_agent_efficiency_contract_v1.md)
- [Public portability contract](docs/references/moradin_forge_public_export_contract_v1.md)
- [Release artifact contract](docs/references/moradin_forge_release_artifact_contract_v1.md)
- [Moradin payload contract](docs/references/moradin_payload_contract_v1.md)
- [Agent handoff prompt](Harness/entrypoints/forge_agent_handoff.md)

## Optional Workbench

The browser workbench remains secondary and local:

```sh
npm --prefix dev_tracker/ui install
./harness_devops.sh --port <workbench-port>
```

Keep it loopback-only unless the user explicitly approves broader exposure.
The UI may create install-request artifacts but does not execute host
installers; consented execution is a native CLI boundary.

Current beta release target: `v0.2.0-beta.3`.
