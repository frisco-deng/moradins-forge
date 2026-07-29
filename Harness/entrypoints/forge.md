# Moradin Forge Entrypoint

## Role

Operate Moradin's Forge as an agent-first local integration kit.

The agent must use Forge to help a user adopt Moradin into an existing repo
without breaking that repo's current workflows.

## Consent-First Sequence

1. Read `FORGE.md`, `README.md`, and this entrypoint.
2. Ask the user which workspace roots Forge may inspect.
3. Run `scripts/moradin_forge.sh onboard --workspace <workspace-root>` and show
   the discovered repositories before broader inspection.
4. Inspect only standard guidance, manifest, CI, container, and deployment
   files; explain tool recommendations, sidecar writes, agent blocks, and
   rollback.
5. Ask for explicit, scoped user consent before applying tools or repository
   changes.
6. Run `scripts/moradin_forge.sh plan --target <target-repo>` or the PowerShell
   wrapper to produce a dry-run plan.
7. Apply only after consent with `scripts/moradin_forge.sh apply --target
   <target-repo> --approve`.
   Use `--approve-agent-file AGENTS.md` and/or `--approve-agent-file CLAUDE.md`
   only when the user separately approves each marked block.
8. Report changed paths, tooling plans and receipts, validation commands, and
   remaining manual actions.
9. Begin adopted work with `context-primer` and `repo-brief`; use
   `rerun-advice` before repeated expensive commands, and request tools only
   when they materially improve testing or diagnosis.
10. Verify the sidecar with `scripts/moradin_forge.sh verify --target
   <target-repo>` or the PowerShell wrapper.
11. When removal is requested, run `scripts/moradin_forge.sh rollback --target
   <target-repo> --approve`; never delete an unverified sidecar manually.

## Authority

Forge may write only:

- the approved target repo's `.moradins-harness/` sidecar,
- generated adapter snippets under `.moradins-harness/adapters/`,
- local tooling plans, receipts, counters, and offline bundles,
- a marked Moradin block in target `AGENTS.md` or `CLAUDE.md` only when that
  file is explicitly approved.

Forge must not:

- run an installer without an approved plan digest,
- invoke privileged installation or elevation automatically,
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
restores Forge-owned target agent blocks while preserving unrelated guidance.
Tooling rollback removes only receipt-owned user-local tools; privileged
package-manager changes remain explicit user operations.
