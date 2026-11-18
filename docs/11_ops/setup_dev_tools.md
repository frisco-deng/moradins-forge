# Developer Tool Setup

Forge carries the shared developer-tool catalog and runtime checks as a standalone
payload. The source manifest at `catalog/templates-tooling-source.json` binds its
upstream revision and exact hashes. The templates deck is not a runtime dependency.

Run as your normal user:

```sh
setup-dev-tools --review
setup-dev-tools --upgrade
```

The no-argument command also reviews tools. Review shows a compact installed and
available version table, source channel, owner and action. Unknown freshness is
explicit; external ownership never means up to date. JSON is opt-in through
`--review --json`; the offline `doctor --json` remains available.

Upgrade installs missing Practical tools, updates eligible Forge-managed tools
and repairs dependencies of existing registered UI environments. It shows the
changes, asks once, then creates plans, supplies exact hashes, applies and verifies
internally. No receipt copying or long command sequence is needed. The native
sealed phase requests sudo only for necessary system changes; do not run the
launcher with sudo. Externally managed tools and unrelated optional services are
not adopted. This command does not perform an Ubuntu-wide upgrade.

State and interrupted execution remain in the existing private directory. The
next invocation checks the explicitly indexed run and its bound receipts before
new application. Unknown mutations, external drift and concurrent execution are
named conflicts; failed or partial work cannot report success. Independent
eligible components continue behind scoped blockers.

Install or refresh the user launcher once through:

```sh
scripts/setup-dev-tools install-launcher
```

The advanced `plan`, `apply`, `verify`, `rollback`, `ui-plan`, `ui-apply`,
`ui-verify`, `ui-rollback` and explicit `guided` interfaces remain compatible.
Normal use requires only the two commands above.

`laneweaver` pins Node 24.19.0, Playwright 1.62.0, Vitest/provider 4.1.10 and
axe 4.14.0. `moradin_legacy` preserves Playwright 1.58.2 and Vitest/provider
4.1.12. Both select matching Chromium/headless Chromium, Firefox, WebKit and
FFmpeg. These are separate tool environments; repository lockfiles and global
runtime choices are preserved.

The exact Node checksum and npm dependency lock are bound before application.
Private receipts record stage checkpoints; activation requires actual browser,
Vitest, axe and FFmpeg controls. The simple upgrade flow plans catalog-owned UI dependencies through the native
sealed package installer, then requires actual browser acceptance before
activation. Ubuntu 24.04 amd64/arm64 dependency lists carry exact Playwright
provenance; other dependency platforms remain unverified. User-owned Node code
is never executed as root. Missing or partial execution is not readiness. Rollback preserves failed-generation evidence and
refuses unexpected destination drift.

Managed fleets can qualify a pinned Forge commit using their own release intake
and approval process. A developer branch is suitable for review and testing.
