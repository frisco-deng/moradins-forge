# PLANS

Active public planning should happen in public issues, pull requests, or concise
docs under `docs/`.

Durable planning rules:

- Recover the [whole-product context](docs/11_ops/codex_run_loop.md#current-working-baseline-contract),
  connect the current slice to integrated acceptance, and review downstream impact
  when a material dependency changes. Keep deferred accepted scope visible.
- keep the agent-first flow primary,
- keep host installs request-only,
- preserve target root workflows by default,
- update contracts before changing sidecar or payload behavior,
- run portability checks before public releases.
