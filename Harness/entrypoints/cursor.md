# Cursor Entrypoint

When Cursor is sent to Moradin's Forge:

1. Confirm the public Forge clone and explain the README's three-step path.
2. Ask the user to launch `./install/tooling-suite.sh`; explain and verify it,
   but do not operate or approve its sudo phase for the user.
3. Ask for explicit workspace roots, run onboarding, and show discovered
   repositories before deeper standard-configuration inspection.
4. Show the exact dedicated `.cursor/rules/moradin-forge.mdc` proposal and
   every other requested provider diff. Ask separately per file.
5. Refuse to replace an existing Cursor rule at that path unless it already
   contains the Forge ownership marker. Never patch arbitrary rule paths.
6. Apply only approved user-level tools and repository changes, then verify
   tools, owned blocks, the sidecar, and rollback.
7. Use the compact primer, repository brief, and rerun advice before broader
   context ingestion or repeated commands.

For disconnected Linux targets, follow the complete air-gap runbook and use
offline onboarding after exact bundle verification.
