# RELIABILITY

Forge reliability comes from repeatable commands and narrow write boundaries.

- `plan` is dry-run oriented.
- `apply` requires `--approve`.
- `verify` checks the adopted sidecar.
- `public-portability-check` validates public release hygiene.
- Use `scripts/moradin_forge.sh rollback --target <target-repo> --approve`.
  Transactional rollback verifies ownership and exact managed contents, refuses
  drift or unowned files, and restores the Forge-owned root change exactly.
  Never substitute manual sidecar or root-block deletion.
