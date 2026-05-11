# ARCHITECTURE

Moradin's Forge has three public layers:

- Agent entrypoints: `README.md`, `FORGE.md`, `AGENTS.md`, and
  `Harness/entrypoints/forge.md`.
- Deterministic integration scripts: `scripts/moradin_forge.*` and the payload
  manifest at `Harness/moradin_payload/manifest.yaml`.
- Optional diagnostics: the workbench under `dev_tracker/ui/` and generated
  sidecar/readiness artifacts in the target repo.

The default integration footprint is a local `.moradins-harness/` sidecar.
Target root files are preserved unless the user explicitly approves a marked
root patch.

Canonical references:

- `docs/00_overview/architecture.md`
- `docs/03_architecture/index.md`
- `docs/design_docs/index.md`
