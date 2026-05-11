# RELIABILITY

Forge reliability comes from repeatable commands and narrow write boundaries.

- `plan` is dry-run oriented.
- `apply` requires `--approve`.
- `verify` checks the adopted sidecar.
- `public-portability-check` validates public release hygiene.
- Sidecar rollback is deleting `.moradins-harness/` and any separately approved
  marked root block.
