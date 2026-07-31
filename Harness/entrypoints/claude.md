# Claude Code Entrypoint

When Claude Code is sent to Moradin's Forge:

1. Read `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
2. Ask which workspace roots may be inspected and discover repositories only
   below those roots.
3. Explain proposed sidecar writes, tooling actions, `AGENTS.md` and
   `CLAUDE.md` owned blocks, validation, and rollback.
4. Ask for digest-bound approval before user-level installs or repository
   changes. Give adaptive privileged scripts to the user. For a complete Linux
   baseline, offer `install/tooling-suite.sh`, but never operate its menu or
   sudo boundary for the user.
5. Use the compact primer and repository brief before broad reads, and rerun
   advice before repeating expensive checks. Request only materially useful
   testing or diagnostic tools.
6. Run verification after apply and summarize changed paths and tooling
   receipts.

Forge remains local-only unless the user asks for external tooling.
