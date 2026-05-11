# FRONTEND

The Moradin Forge Workbench is optional diagnostics for the agent-first flow.

It should help operators inspect readiness, deploy maps, repo registry data, and
verification state. It must not become the required path for adoption, and it
must not execute host installs.

Workbench commands:

```sh
npm --prefix dev_tracker/ui run test
npm --prefix dev_tracker/ui run build
./harness_devops.sh --port <workbench-port>
```
