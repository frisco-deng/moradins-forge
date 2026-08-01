# Moradin Forge Entrypoint

## Role

Operate Moradin's Forge as an agent-first local integration kit.

The agent must use Forge to help a user adopt Moradin into an existing repo
without breaking that repo's current workflows.

## Consent-First Sequence

1. Confirm the public Forge clone and explain the README's three-step path.
2. Ask the user to run `./install/tooling-suite.sh`; the agent explains and
   verifies, while the user owns every interactive and sudo approval.
3. Read `FORGE.md`, `README.md`, and this entrypoint.
4. Ask the user which workspace roots Forge may inspect and which agent
   providers they use.
5. Run `scripts/moradin_forge.sh onboard --workspace <workspace-root>` and show
   the discovered repositories before broader inspection.
6. Inspect only standard guidance, manifest, CI, container, and deployment
   files; explain tool recommendations, sidecar writes, agent blocks, and
   rollback.
7. Show each fixed-path provider proposal and ask separately before that file
   is created or patched.
8. Ask for explicit, scoped user consent before applying tools or repository
   changes. For a complete Linux baseline, offer `install/tooling-suite.sh` and
   require the human to launch and approve it personally.
9. Run `scripts/moradin_forge.sh plan --target <target-repo>` or the PowerShell
   wrapper to produce a dry-run plan.
10. Apply only after consent with `scripts/moradin_forge.sh apply --target
   <target-repo> --approve`.
   Use `--approve-agent-file` only when the user separately approves that
   allowlisted path; absent files also require matching `--create-agent-file`.
11. Report changed paths, tooling plans and receipts, validation commands, and
   remaining manual actions.
12. Begin adopted work with `context-primer` and `repo-brief`; use
   `rerun-advice` before repeated expensive commands, and request tools only
   when they materially improve testing or diagnosis.
13. Verify the sidecar with `scripts/moradin_forge.sh verify --target
   <target-repo>` or the PowerShell wrapper.
14. When removal is requested, run `scripts/moradin_forge.sh rollback --target
   <target-repo> --approve`; never delete an unverified sidecar manually.

For disconnected Linux, use `airgap-request`, build a complete sealed kit on a
connected rootless host, verify its separately transported digest, apply it
offline, and add `--offline` to onboarding.

## Authority

Forge may write only:

- the approved target repo's `.moradins-harness/` sidecar,
- generated adapter snippets under `.moradins-harness/adapters/`,
- local tooling plans, receipts, counters, and offline bundles,
- a marked Moradin block in one of the five fixed provider paths only when that
  file is explicitly approved.

Forge agents must not:

- run an installer without an approved plan digest,
- invoke privileged installation, launch the human installer, enter
  credentials, or approve its sudo transaction,
- overwrite an existing sidecar; the compatibility overwrite flag fails closed,
- create root repo adapters when a safer snippet is enough,
- publish, upload, or expose local repo contents.

## Deterministic Entrypoints

- Linux/macOS: `scripts/moradin_forge.sh`
- Windows PowerShell: `scripts/moradin_forge.ps1`
- Python core: `scripts/moradin_forge.py`
- Human-run Linux tooling suite: `install/tooling-suite.sh`
- First-use handoff prompt: `Harness/entrypoints/forge_agent_handoff.md`
- Payload source of truth: `Harness/moradin_payload/manifest.yaml`

## Rollback

Use the explicit rollback command. It verifies the ownership manifest, refuses
modified or unowned managed content, removes only the owned sidecar, and
restores Forge-owned target agent blocks while preserving unrelated guidance.
Adaptive tooling rollback removes only receipt-owned user-local tools. The
human-run Linux suite additionally records digest-bound root receipts and can
roll back only its own package and atomic-shim transactions.
