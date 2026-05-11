# Codex Entrypoint

Codex should start from `agent.md`, then prefer deterministic repo tooling and canonical paths only.
When the user asks Codex to adopt Moradin into another repo, load `FORGE.md`
and `forge.md` before proposing target-repo edits.

- Treat `docs/` as canonical.
- Treat `Harness/` as summaries, routing, and automation.
- Treat `Harness/moradin_payload/manifest.yaml` as the downstream deployment contract.
- Treat `scripts/moradin_forge.sh` and `scripts/moradin_forge.py` as the local agent-first integration path.
- Treat `.harness_template/` as a compatibility scaffold only.
