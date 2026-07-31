# Engineer Entrypoint

Use this when changing Forge itself.

- Keep public docs generic and agent-first.
- Keep target repo adoption consent-gated.
- Keep user-level execution bound to an exact approved plan digest.
- Agents never invoke elevation. Adaptive flows generate privileged scripts;
  the separate human-run Linux suite may request sudo only after exact plan
  review and digest confirmation.
- Preserve independently approved agent blocks and user configuration.
- Preserve target root files by default.
- Update contracts before changing payload or sidecar behavior.
- Keep Linux, macOS, and Windows capability paths equivalent.
- Run the relevant gates from `docs/references/repo_operating_model_v1.md`.
