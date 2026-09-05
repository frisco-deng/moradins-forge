# Engineer Entrypoint

Use this when changing Forge itself.

- Keep public docs generic and agent-first.
- Keep target repo adoption consent-gated.
- Keep user-level execution bound to an exact approved plan digest.
- Agents never invoke elevation. Adaptive flows generate privileged scripts;
  the human-run Linux/WSL, macOS, or Windows V2 suite acts only after exact
  plan review and digest confirmation. Complete air-gap support is Linux-only.
- Preserve independently approved agent blocks and user configuration.
- Preserve target root files by default.
- Update contracts before changing payload or sidecar behavior.
- Keep Linux, macOS, and Windows capability paths equivalent.
- Run the relevant gates from `docs/references/repo_operating_model_v1.md`.
