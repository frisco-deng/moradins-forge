# RELIABILITY

Forge reliability comes from repeatable commands and narrow write boundaries.

- `plan` is dry-run oriented.
- `apply` requires `--approve`.
- `verify` checks the adopted sidecar.
- `public-portability-check` validates public release hygiene.
- `tooling-apply` binds execution to an exact plan digest and writes a rollback
  receipt even when an approved installer fails.
- `upgrade` stages and validates a replacement before switching.
- Sidecar and upgrade rollback remove only Forge-owned files and marker blocks;
  modified or unrelated guidance is preserved and reported for manual review.
