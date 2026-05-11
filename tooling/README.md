# Tooling Adapter

This directory contains portable Forge tooling adapters and security/check
configuration.

- `repo_id`: `moradins-forge`
- `archetype`: `uv-forge`
- `containerized`: `false`

Primary public gates:

- `make test`
- `make payload-validate`
- `make payload-smoke`
- `make forge-smoke`
- `make public-portability-check`

Optional workbench gates:

- `npm --prefix dev_tracker/ui run test`
- `npm --prefix dev_tracker/ui run build`
- `npm --prefix dev_tracker/ui audit --audit-level=moderate`

Use `make public-portability-check` to scan the public tree and generated
sidecar before releases.
