# Support and Compatibility

Moradin's Forge is prerelease software through the `v0.x` beta and release
candidate lines. Maintainers provide best-effort issue triage for the current
public beta; there is no response-time or host-availability SLA.

## Compatibility Policy

- Public V2 tooling records are additive during beta.4. A breaking schema or
  command change requires a new record version and a migration note.
- V1 tooling plans expire normally and cannot authorize V2 mutations. Existing
  V1 Linux receipts remain verifiable and rollback-capable through their sealed
  runner.
- From v1.0 onward, Forge follows semantic versioning. Incompatible public CLI
  or record changes require a major version. Additive interfaces use a minor
  version; compatible fixes use a patch version.
- Forge owns only its documented sidecar, marker blocks, versioned tool
  prefixes, checkpoints, and receipts. Unrelated repository and host state is
  outside the compatibility contract.

## Supported Surfaces

Connected V2 installation targets Linux/WSL, macOS, and Windows. Complete
air-gap kits target only the Linux distributions and architectures listed in
the air-gap runbook. Unsupported platforms and provider combinations fail
closed or produce a manual handoff.

Use GitHub issues for reproducible non-security defects. Use the private
process in [SECURITY.md](SECURITY.md) for vulnerabilities. Version 1.0 support
begins only after the published RC observation and release gates in the
[v1.0 readiness checklist](docs/15_checklists/v1_readiness.md).
