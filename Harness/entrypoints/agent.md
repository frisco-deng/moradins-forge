# Forge Agent Entrypoint

Operate Moradin's Forge as a local, consent-gated integration kit.

## Change Rules

1. Read `README.md`, `FORGE.md`, `AGENTS.md`, and
   `Harness/entrypoints/forge.md`.
2. Inspect the target repo before proposing adoption.
3. Prefer deterministic Forge commands over ad hoc shell chains.
4. Keep host tool installs request-only.
5. Preserve target root workflows unless the user explicitly approves a marked
   root patch.
6. Report changed paths, validation, install requests, and rollback.

## Public Development Rules

- Work from public `main` on feature branches.
- Keep compatibility details in contracts and manifests, not first-read docs.
- Run `make public-portability-check` before public releases.
