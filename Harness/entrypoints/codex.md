# Codex Entrypoint

When Codex is sent to Moradin's Forge:

1. Confirm Forge was cloned over HTTPS. Explain the three-step README path.
2. Ask the user to run the native suite: `./install/tooling-suite.sh` on
   Linux/WSL, `./install/tooling-suite-macos.sh` on macOS, or
   `.\install\tooling-suite.ps1` on Windows. Start with `doctor`; never approve
   sudo/elevation for them, and verify its V2 receipt afterward.
3. Read `FORGE.md`, `AGENTS.md`, and `Harness/entrypoints/forge.md`.
4. Inspect the target repo's own agent guidance and deterministic commands.
5. Ask which workspace roots may be inspected, then run onboard and tooling
   plan before any mutation.
6. Show tool actions and exact owned provider blocks. Ask separately before
   each allowlisted file is created or patched.
7. Apply user-level tools or repository changes only with explicit,
   digest-bound approval. Give adaptive privileged scripts to the user. For a
   complete baseline, offer the matching native suite; the user must launch it
   and approve its elevation personally. Only Linux exposes complete air-gap
   commands.
8. Use the compact primer, repository brief, and rerun advice before broad
   reads or repeated checks. Request tools only when they materially improve
   testing or diagnosis.
9. Verify the generated sidecar, tools, and agent blocks; report rollback.

Use `--offline` for onboarding after the complete air-gap workflow in
`docs/11_ops/air_gapped_tooling_suite.md`.

Use the shell wrapper on Linux/macOS and the PowerShell wrapper on Windows.
