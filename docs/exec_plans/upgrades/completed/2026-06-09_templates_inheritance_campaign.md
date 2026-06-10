---
title: ".templates Inheritance Campaign"
status: completed
owner: moradin-forge
archived_on: 2026-06-09
record_type: upgrade_review
source_cycle: templates-inheritance-2026-06-09
---

# .templates Inheritance Campaign

## Summary

Moradin Forge adopted the current shared-tooling adapter improvements while
keeping public Forge local-first, consent-gated, and free of host-origin leaks.
The campaign added request-only bootstrap entrypoints, refreshed docs and
contracts, and expanded public export and sidecar sanitizers.

## Inheritance Matrix

| shared change | decision | Forge handling |
| --- | --- | --- |
| Python runtime routing | adopted | Re-rendered adapter reports `uv run python` and discourages raw `python`. |
| Wrapper bytecode suppression | adopted | Generated tooling wrappers export `PYTHONDONTWRITEBYTECODE=1`. |
| Hardened scanner lane | adopted | `verify-security` keeps gitleaks, Trivy, actionlint, zizmor, conftest, yamllint, Semgrep, pip-audit, Syft, Grype, and OSV surfaces. |
| Rerun/session steering | adopted docs | Root guidance points to context primer, rerun advice, session supervisor, checkpoint, and investigation ledger. |
| Generated hygiene | adopted | Public export and sidecar scanners block host/user/session/path origin leaks. |
| UI reference render and visual measurement | deferred optional | Documented as opt-in until Forge has screenshot and DOM-box capture wrappers. |
| Release candidate readiness | deferred optional | Not rendered until Forge has release artifacts, SBOM/security evidence, signing or smoke evidence, and an RC manifest. |
| Windows Sandbox/native readiness | deferred optional | Documented as shared evidence lane, not a default Forge target. |
| macOS signing, WSL smoke, GPU helpers | not applicable now | Kept out of default Forge targets. |
| Dirty `.templates` generated observability reports | not imported | Forge imported only adapter/script/config behavior needed by the renderer. |

## Public Changes

- Added `scripts/forge_bootstrap.py`.
- Added `install/bootstrap-linux.sh`, `install/bootstrap-macos.sh`, and
  `install/bootstrap-windows.ps1`.
- Added `docs/references/moradin_forge_installer_bootstrap_contract_v1.md`.
- Added installer files to `Harness/moradin_payload/manifest.yaml`.
- Updated public docs and control artifacts for bootstrap, runtime routing, and
  stricter portability rules.

## Validation

Required final gates for this campaign:

- `make verify-fast`
- `make payload-smoke`
- `make public-portability-check`
- `make verify-paths`
- `make verify-security`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
