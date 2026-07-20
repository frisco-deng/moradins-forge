# Moradin Forge Entrypoint

## Role

Operate Moradin's Forge as an agent-first local integration kit.

The agent must use Forge to help a user adopt Moradin into an existing repo
without breaking that repo's current workflows.

## Consent-First Sequence

1. Read `FORGE.md`, `README.md`, and this entrypoint.
2. Inspect the target repo's `AGENTS.md`, `README.md`, `Makefile`, package files,
   and deterministic validation commands.
3. Explain the proposed sidecar, adapter edits, readiness gaps, and rollback path.
4. Ask for explicit user consent before applying changes.
5. Run `scripts/moradin_forge.sh plan --target <target-repo>` or the PowerShell
   wrapper to produce a dry-run plan.
6. Apply only after consent with `scripts/moradin_forge.sh apply --target
   <target-repo> --approve`.
   Use `--patch-agents` only when the user separately approves a marked root
   `AGENTS.md` block.
7. Report changed paths, install-request artifacts, validation commands, and
   remaining manual actions.
8. Verify the sidecar with `scripts/moradin_forge.sh verify --target
   <target-repo>` or the PowerShell wrapper.
9. When removal is requested, run `scripts/moradin_forge.sh rollback --target
   <target-repo> --approve`; never delete an unverified sidecar manually.

## Authority

Forge may write only:

- the approved target repo's `.moradins-harness/` sidecar,
- generated adapter snippets under `.moradins-harness/adapters/`,
- request-only install artifacts under Moradin control artifacts.
- a marked Moradin block in an existing target `AGENTS.md` only when
  `--patch-agents` is explicitly approved.

Forge must not:

- run host install commands,
- overwrite an existing sidecar; the compatibility overwrite flag fails closed,
- create root repo adapters when a safer snippet is enough,
- publish, upload, or expose local repo contents.

## Deterministic Entrypoints

- Linux/macOS: `scripts/moradin_forge.sh`
- Windows PowerShell: `scripts/moradin_forge.ps1`
- Python core: `scripts/moradin_forge.py`
- First-use handoff prompt: `Harness/entrypoints/forge_agent_handoff.md`
- Payload source of truth: `Harness/moradin_payload/manifest.yaml`

## Rollback

Use the explicit rollback command. It verifies the ownership manifest, refuses
modified or unowned managed content, removes only the owned sidecar, and
restores a Forge-owned target `AGENTS.md` change exactly. No host tool
installation is performed by Forge.
