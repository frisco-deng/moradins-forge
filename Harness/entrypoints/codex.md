# Codex Entrypoint

When Codex is sent to Moradin's Forge:

1. Read `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
2. Inspect the target repo's own agent guidance and deterministic commands.
3. Run only explain/readiness/plan before approval.
4. Apply only with explicit user approval.
5. Verify the generated sidecar and report rollback.

Use the shell wrapper on Linux/macOS and the PowerShell wrapper on Windows.
