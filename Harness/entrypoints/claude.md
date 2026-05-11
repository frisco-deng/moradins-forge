# Claude Entrypoint

Claude should start from `agent.md`, then use the same manager-repo rules:

- canonical-path refactors only
- no new legacy aliases or unbounded dual-path support
- `Harness/moradin_payload/manifest.yaml` owns downstream materialization
- `FORGE.md` and `Harness/entrypoints/forge.md` own agent-first target-repo adoption
- `scripts/moradin_forge.ps1` and `scripts/moradin_forge.sh` are the native deterministic wrappers
- `.harness_template/` remains generic and manager-safe during the compatibility window
