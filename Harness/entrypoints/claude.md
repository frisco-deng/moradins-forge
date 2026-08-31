# Claude Code Entrypoint

When Claude Code is sent to Moradin's Forge:

1. Confirm the public Forge clone, then explain the three-step README path.
2. Ask the user to run `./install/tooling-suite.sh` on Linux/WSL,
   `./install/tooling-suite-macos.sh` on macOS, or
   `.\install\tooling-suite.ps1` on Windows. Start with `doctor`, verify the V2
   receipt, and do not approve or operate sudo/elevation for them.
3. Read `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
4. Ask which workspace roots may be inspected and discover repositories only
   below those roots.
5. Explain proposed sidecar writes, tooling actions, and every allowlisted
   provider block. Request independent create/patch approval per file.
6. Ask for digest-bound approval before user-level installs or repository
   changes. Give adaptive privileged scripts to the user. For a complete Linux
   baseline, offer the matching native suite, but never operate its menu or
   elevation boundary for the user. Complete air-gap kits remain Linux-only.
7. Use the compact primer and repository brief before broad reads, and rerun
   advice before repeating expensive checks. Request only materially useful
   testing or diagnostic tools.
8. Run verification after apply and summarize changed paths and tooling
   receipts.

For a disconnected target, follow the air-gap runbook and pass `--offline` to
onboarding after the complete kit verifies.

Forge remains local-only unless the user asks for external tooling.
