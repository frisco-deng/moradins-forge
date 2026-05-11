# Architecture Brief

Forge uses a simple public structure:

- `FORGE.md` and `AGENTS.md` route agents,
- `scripts/moradin_forge.*` run the deterministic adoption flow,
- `Harness/moradin_payload/manifest.yaml` defines the sidecar payload,
- `.moradins-harness/` is the default target-side footprint.
