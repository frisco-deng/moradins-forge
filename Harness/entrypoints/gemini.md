# Gemini CLI Entrypoint

When Gemini CLI is sent to Moradin's Forge:

1. Confirm the public Forge clone and explain the README's three-step path.
2. Ask the user to launch `./install/tooling-suite.sh` on Linux/WSL,
   `./install/tooling-suite-macos.sh` on macOS, or
   `.\install\tooling-suite.ps1` on Windows. Start with `doctor`, explain and
   later verify its V2 receipt, and leave every sudo/elevation approval to the
   user.
3. Ask for explicit workspace roots and run `scripts/moradin_forge.sh onboard`
   once with repeatable `--workspace` arguments.
4. Show discovered repositories before deeper standard-configuration
   inspection. Do not crawl arbitrary source or paths outside scope.
5. Show the exact `GEMINI.md` marker diff and every other requested provider
   diff. Ask separately before each file is created or patched.
6. Apply only digest-approved user actions and repository changes, then verify
   tools, the sidecar, provider blocks, and rollback commands.
7. Begin adopted work with the compact primer, repository brief, and rerun
   advice. Request tools only when they materially improve evidence.

For disconnected Linux targets, follow the air-gap runbook and use offline
onboarding only after the separately transported kit digest verifies.
