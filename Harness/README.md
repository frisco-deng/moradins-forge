# Harness Control Plane

`Harness/` contains the Moradins Harness manager control plane.

- `docs/` remains the canonical source of truth for human-readable project knowledge.
- `Harness/` owns routing, orchestration, summaries, validation, automation, and control-plane artifacts.
- `FORGE.md` and `Harness/entrypoints/forge.md` own agent-first local adoption.
- `Harness/moradin_payload/manifest.yaml` defines the Moradin payload that Builder materializes into new repos and sidecars.
- `.harness_template/` remains as a compatibility scaffold for one release window.

## Key Areas

- `entrypoints/`: agent bootstrap, Forge adoption, and assistant-specific entry guidance
- `routing/`: load order, route maps, escalation rules
- `views/`: compact summaries that point back to canonical docs
- `automation/`: checks, upgrade automation, scripts, and CLI scaffolding
- `moradin_payload/`: payload manifest and compatibility notes
- `schemas/`: control-plane and payload validation schemas
- `artifacts/`: canonical manager-side control-plane artifact destination

## Alpha Model

- Moradin payload names are canonical for operator-facing routes and docs.
- The manager repo uses canonical snake_case paths only.
- `.harness_template/` compatibility shims remain available for one release window.
