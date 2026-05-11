---
title: "Optional Workbench Topology"
status: approved
owner: moradin-forge
last_reviewed: 2026-05-11
source_refs:
  - ../../FRONTEND.md
related_docs:
  - index.md
---

# Optional Workbench Topology

The workbench is a local diagnostics surface for readiness, deploy maps, and
verification state. It is not required for agent-first adoption.

| Surface | Purpose | Boundary |
| --- | --- | --- |
| Forge scripts | explain, readiness, plan, apply, verify | local process |
| Workbench UI | diagnostics and review | loopback browser |
| Target sidecar | adopted Forge payload | target repo only |
