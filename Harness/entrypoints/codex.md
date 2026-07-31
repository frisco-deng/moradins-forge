# Codex Entrypoint

When Codex is sent to Moradin's Forge:

1. Read `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
2. Inspect the target repo's own agent guidance and deterministic commands.
3. Ask which workspace roots may be inspected, then run onboard and tooling
   plan before any mutation.
4. Show tool actions and exact owned agent blocks.
5. Apply user-level tools or repository changes only with explicit,
   digest-bound approval. Give adaptive privileged scripts to the user. For a
   complete Linux baseline, offer `install/tooling-suite.sh`; the user must
   launch it and approve its sudo phase personally.
6. Use the compact primer, repository brief, and rerun advice before broad
   reads or repeated checks. Request tools only when they materially improve
   testing or diagnosis.
7. Verify the generated sidecar, tools, and agent blocks; report rollback.

Use the shell wrapper on Linux/macOS and the PowerShell wrapper on Windows.
