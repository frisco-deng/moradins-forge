# GitHub Copilot Entrypoint

When a Copilot-capable agent is sent to Moradin's Forge:

1. Confirm the public Forge clone and explain the README's three-step path.
2. Ask the user to launch `./install/tooling-suite.sh` on Linux/WSL,
   `./install/tooling-suite-macos.sh` on macOS, or
   `.\install\tooling-suite.ps1` on Windows. Start with `doctor`, explain and
   verify the V2 receipt, and leave sudo/elevation approval to the user.
3. Ask for explicit workspace roots, run onboarding, and show discovered
   repositories before inspecting standard project configuration.
4. Show the exact `.github/copilot-instructions.md` marker diff plus any other
   requested provider diff. Ask separately before each create or patch.
5. Preserve all unrelated Copilot instructions and repository guidance.
6. Apply only digest-approved user-level tooling and repository changes, then
   verify tools, owned blocks, the sidecar, and rollback.
7. Prefer compact summaries and rerun advice before broad logs or repeated
   commands; request only materially useful tools.

For disconnected Linux targets, use the complete air-gap workflow and pass
`--offline` to onboarding after bundle verification.
