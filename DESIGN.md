# DESIGN

Forge is designed as an agent workbench, not a human-first installer.

The public design direction is quiet and operational:

- first-read docs tell the agent exactly what to inspect and explain,
- scripts perform deterministic discovery and adoption steps,
- the sidecar keeps target repo changes bounded,
- the optional browser workbench supports diagnostics instead of becoming the
  primary install path.

Design references:

- `docs/product_specs/project_builder_ui.md`
- `FRONTEND.md`
