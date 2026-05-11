# Harness

`Harness/` contains Forge's local control surface:

- `entrypoints/`: agent entrypoints for Codex, Claude Code, and generic agents,
- `moradin_payload/`: the sidecar payload manifest and payload notes,
- `artifacts/`: public placeholder/control files used by the optional
  workbench and generated sidecars,
- `schemas/`: lightweight schemas used by validation and compatibility checks,
- `views/`: concise public briefs for the optional workbench.

The public product path is agent-first. The browser workbench and compatibility
files are secondary support surfaces.
