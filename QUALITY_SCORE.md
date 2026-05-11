# QUALITY_SCORE

Forge quality is measured by deterministic behavior:

- dry-run planning writes no target repo files,
- apply requires explicit approval,
- generated sidecars verify cleanly,
- root files are preserved by default,
- install requests are written but not executed,
- public portability checks pass for the repo and sidecar.

Quality gates:

- `make test`
- `make payload-validate`
- `make payload-smoke`
- `make forge-smoke`
- `make public-portability-check`
- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
