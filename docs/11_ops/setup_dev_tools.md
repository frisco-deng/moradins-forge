# Developer Tool Setup

Forge carries the shared developer-tool catalog and runtime checks as a standalone
payload. The source manifest at `catalog/templates-tooling-source.json` binds its
upstream revision and exact hashes. The templates deck is not a runtime dependency.

```sh
scripts/setup-dev-tools doctor --json
scripts/setup-dev-tools install-launcher
~/dev/tooling/scripts/setup-dev-tools
```

The terminal command audits before offering the existing host installer or an
isolated UI cohort. Noninteractive execution returns its audit without prompting.
Host `plan`, `apply`, `verify` and `rollback` retain the existing tooling-suite
arguments and approvals. No root invocation is added.

```sh
scripts/setup-dev-tools ui-plan --ui-profile laneweaver \
  --output artifacts/tooling/ui-plan.json
scripts/setup-dev-tools ui-apply --plan artifacts/tooling/ui-plan.json \
  --approve-plan-sha256 <displayed-plan-digest>
scripts/setup-dev-tools ui-verify --receipt <displayed-receipt>
scripts/setup-dev-tools ui-rollback --receipt <displayed-receipt> \
  --approve-receipt-sha256 <receipt-digest>
```

`laneweaver` pins Node 24.19.0, Playwright 1.62.0, Vitest/provider 4.1.10 and
axe 4.14.0. `moradin_legacy` preserves Playwright 1.58.2 and Vitest/provider
4.1.12. Both select matching Chromium/headless Chromium, Firefox, WebKit and
FFmpeg. These are separate tool environments; repository lockfiles and global
runtime choices are preserved.

The exact Node checksum and npm dependency lock are bound before application.
Private receipts record stage checkpoints; activation requires actual browser,
Vitest, axe and FFmpeg controls. Native host-library requirements remain explicit;
the UI path never invokes sudo or installs OS dependencies. Missing or partial
execution is not readiness. Rollback preserves failed-generation evidence and
refuses unexpected destination drift.

GB10's local control plane and frozen release intake remain owner-controlled.
Pulling this review branch alone does not change a vendored release or authorize
privileged activation. Publish verified commits and digests for that session's
native intake.
