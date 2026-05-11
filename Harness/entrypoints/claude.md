# Claude Code Entrypoint

When Claude Code is sent to Moradin's Forge:

1. Read `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
2. Inspect the target repo's own guidance and validation commands.
3. Explain proposed sidecar writes, install requests, validation, and rollback.
4. Ask for explicit approval before apply.
5. Run verification after apply and summarize changed paths.

Forge remains local-only unless the user asks for external tooling.
