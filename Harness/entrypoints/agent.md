# Forge Agent Entrypoint

Operate Moradin's Forge as a local, consent-gated integration kit.

## Change Rules

1. Read `README.md`, `FORGE.md`, `AGENTS.md`, and
   `Harness/entrypoints/forge.md`.
2. Inspect the target repo before proposing adoption.
3. Prefer deterministic Forge commands over ad hoc shell chains.
4. Build an adaptive tooling plan from user-approved workspace roots.
5. Run verified user-level installers only after plan-digest approval; generate
   adaptive privileged scripts for user execution. Offer the human-run Linux
   tooling suite when requested, but never operate its menu or sudo boundary
   for the user.
6. Preserve target root workflows unless the user independently approves a
   marked `AGENTS.md` or `CLAUDE.md` patch.
7. Start adopted work with the compact primer and repository brief. Request
   tools only when they materially improve testing or diagnosis, and consult
   rerun advice before repeating expensive commands.
8. Report changed paths, tooling receipts, validation, and rollback.

## Public Development Rules

- Work from public `main` on feature branches.
- Keep compatibility details in contracts and manifests, not first-read docs.
- Run `make public-portability-check` before public releases.
