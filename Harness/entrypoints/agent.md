# Forge Agent Entrypoint

Operate Moradin's Forge as a local, consent-gated integration kit.

## Three-Step Handoff

1. Clone Forge over HTTPS, or confirm the user already cloned it.
2. Explain the native tooling suite: `./install/tooling-suite.sh` on Linux/WSL,
   `./install/tooling-suite-macos.sh` on macOS, or
   `.\install\tooling-suite.ps1` on Windows. The user launches it and
   personally approves sudo/elevation. Verify the resulting V2 receipt.
3. Ask for workspace scope, run `onboard`, show each allowlisted provider-file
   patch, and obtain separate create/patch consent per file.

For disconnected Linux targets, route to
`docs/11_ops/air_gapped_tooling_suite.md`; use `airgap-request`, build the kit
on a connected rootless host, verify the separately transported digest, then
run onboarding with `--offline`.

## Change Rules

1. Read `README.md`, `FORGE.md`, `AGENTS.md`, and
   `Harness/entrypoints/forge.md`.
2. Inspect the target repo before proposing adoption.
3. Prefer deterministic Forge commands over ad hoc shell chains.
4. Build an adaptive tooling plan from user-approved workspace roots.
5. Run verified user-level installers only after plan-digest approval; generate
   adaptive privileged scripts for user execution. Offer the matching native
   tooling suite when requested, but never operate its menu or elevation
   boundary for the user. Start with its network-free `doctor` and use
   `status` before repeating work; complete air-gap kits remain Linux-only.
6. Preserve target root workflows unless the user independently approves an
   allowlisted Codex, Claude, Gemini, Copilot, or Cursor guidance patch.
7. Start adopted work with the compact primer and repository brief. Request
   tools only when they materially improve testing or diagnosis, and consult
   rerun advice before repeating expensive commands.
8. Report changed paths, tooling receipts, validation, and rollback.

## Public Development Rules

- Work from public `main` on feature branches.
- Keep compatibility details in contracts and manifests, not first-read docs.
- Run `make public-portability-check` before public releases.
