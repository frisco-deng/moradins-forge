---
title: "Foundational Principles"
status: approved
owner: platform-operations
last_reviewed: 2026-03-27
source_refs:
  - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - index.md
  - ../00_overview/engineer_entrypoint.md
  - ../11_ops/codex_run_loop.md
  - ../11_ops/quick_start.md
  - ../design_docs/project_builder_control_api.md
  - ../product_specs/project_builder_ui.md
  - ../references/foundational_principles_source_synthesis.md
---

# Foundational Principles

## Purpose And Scope

- Define the enduring operating principles for Moradins Harness.
- Keep the manager repo's philosophy, safety model, and release boundaries explicit and auditable.
- Provide a normative layer above runbooks and specs without replacing deeper contracts.

This document is authoritative for the manager repo. The downstream template carries only the invariant subset that can be hydrated safely inside deployed harnesses.

When this document conflicts with a deeper contract, the deeper contract wins in this order: contracts, security, tests, product/runtime specs, then principles.

## Enduring Foundational Principles

### 1. Canonical Truth Must Be In-Repo

- `docs/` is the canonical human-readable truth for operators and agents.
- `Harness/` is the control plane for routing, artifacts, and enforcement.
- `.harness_template/` is the only downstream scaffold and must remain generic.
- If knowledge is not discoverable in-repo, it is not reliably available to the harness.

### 2. Legibility Beats Cleverness

- Prefer structures that are easy for the next operator or agent to discover, verify, and extend.
- Keep `AGENTS.md` short and map-like; deeper docs carry durable detail.
- Favor stable, explicit, boring-by-design patterns over opaque magic.

### 3. Deterministic Repo-Native Work Comes First

- Prefer repo-defined `make`, `uv`, `npm`, and validation targets over ad hoc shell chains.
- Treat deterministic checks as the enforcement layer for architecture, safety, and doc quality.
- Promote repeated guidance into repo checks, scripts, or canonical docs rather than leaving it as tribal knowledge.

### 4. Human Gates Are Real Product Boundaries

- One approved cycle per human gate.
- No automatic cycle chaining.
- No hidden execution inside target repos.
- No `dev -> main` or `main -> prod` promotion without explicit human signoff.

### 5. Explainability Comes Before Execution

- The harness must explain what it discovered, what it inferred, what it filled automatically, and what still requires human approval.
- Structured intake is the default path; freeform remains advanced.
- Assistant actions stay human-triggered and operator-visible.

### 6. Mutation Must Stay Bounded And Visible

- Existing-project adoption is sidecar-only for the current product contract.
- Writes stay inside declared allowlists.
- Remote and local execution surfaces must expose approvals, status, and artifact trails.
- Safety restrictions must be mechanically enforced, not implied.

### 6.1 Tool Trust For MCP-Like Surfaces

- Trust tool annotations only from trusted servers.
- Still apply local policy evaluation.
- Treat destructive or open-world tools as approval-gated.
- Keep untrusted tools behind manual approval.
- Use the repo-local or operator-provided tool trust policy when MCP-like
  tooling enters scope.

### 7. Progress Must Be Incremental And Recoverable

- Prefer one bounded increment over broad redesigns.
- Leave the repo in a clean, reviewable state after each approved pass.
- Plans, changelogs, guidance, status artifacts, and prompt outputs are first-class handoff surfaces.
- Durable artifacts should reduce re-discovery work for the next session, not increase it.

### 8. Context Is Finite And Must Be Curated

- Give agents the smallest high-signal context set that still preserves correct behavior.
- Use progressive disclosure, stable entrypoints, and explicit references instead of giant manuals.
- Keep tools, prompts, and docs narrow enough that the next step is legible.

### 9. Scope Discipline Is A Safety Requirement

- The current-scope release remains a Linux-hosted, browser-based, single-user companion.
- Do not silently expand into public hosting, Windows-native desktop shells, PAT / HTTPS auth, multi-user controls, or unattended target-repo automation.
- New scope requires new approval.

### 10. Drift Must Be Paid Down Continuously

- Behavior changes require synchronized docs, rules, and control artifacts.
- Recurring cleanup, documentation review, and guidance refresh are part of the product, not maintenance afterthoughts.
- The repo should become more legible after each cycle, not more entropic.

## Non-Goals And Current-Scope Boundaries

Moradins Harness is not currently trying to become:

- a public internet-hosted deployment surface
- a Windows-native desktop shell
- an embedded editor or IDE clone
- an unattended multi-user orchestration platform
- a hidden automation layer that mutates target repos without approval
- a repository that optimizes for autonomous merges over explicit governance

The current release contract is intentionally narrower:

- Linux host runs the harness.
- Browser is the primary control surface.
- Localhost, WSL browser access, or SSH local port forwarding are the supported access modes.
- Single-user companion workflows are in scope.

## Reference Operating Pattern

The repo allows a reference operating pattern inspired by the external source set, but it is not a mandatory topology and it never overrides the human-gate model.

1. Initializer or bootstrap pass: ground the task, load repo truth, prepare the environment, and establish the next bounded increment.
2. Implementer pass: execute one scoped change, verify it with repo-native commands, and leave durable progress artifacts.
3. Reviewer or cleanup pass: tighten docs, invariants, or cleanup only when explicitly routed and approved.
4. Human gate: review artifacts, approve continuation, or stop.

Guardrails on this pattern:

- It is a reference pattern, not permission for automatic chaining.
- It cannot bypass one-cycle-per-approval governance.
- It cannot replace explicit approvals for deploy, generate, or target-repo mutation.
- If a specialized sub-pass is used, it must strengthen explainability and cleanup, not hide work.

## Principle-To-Enforcement Map

| Principle | Primary Enforcement Anchors | Practical Effect |
| --- | --- | --- |
| canonical repo truth | `AGENTS.md`, `Harness/entrypoints/agent.md`, `docs/index.md` | agents and operators route from stable docs instead of prompt-only memory |
| deterministic repo-native work | `AGENTS.md`, `README.md`, `Makefile` | `make` and repo-defined checks outrank ad hoc workflows |
| one cycle per approval | `docs/11_ops/codex_run_loop.md`, `Harness/artifacts/control/current_guidance.md` | cycle `N+1` blocks until cycle `N` is explicitly approved |
| explainability before execution | `docs/product_specs/project_builder_ui.md`, `docs/design_docs/project_builder_control_api.md` | discovery, fill maps, prompts, and approvals remain operator-visible |
| bounded mutation | `docs/design_docs/project_builder_control_api.md`, `docs/11_ops/project_builder_runbook.md` | writes stay allowlisted and existing-project adoption stays sidecar-only |
| MCP-like tool trust | repo-local or operator-provided tool trust policy, `Harness/entrypoints/agent.md`, approval artifacts | trusted servers still pass local policy and risky tools stay approval-gated |
| context curation and progressive disclosure | `Harness/entrypoints/agent.md`, `README.md`, `docs/11_ops/quick_start.md` | stable read order beats monolithic instructions |
| docs and rules sync | `docs/11_ops/codex_run_loop.md`, `docs/11_ops/change_tracking_system.md` | behavior shifts require synchronized docs and control artifacts |
| current-scope boundary discipline | `docs/00_overview/engineer_entrypoint.md`, `docs/11_ops/quick_start.md`, `Harness/artifacts/control/current_guidance.md` | release scope cannot drift without a new approval |
| recurring cleanup and drift control | `docs/11_ops/documentation_review_loop.md`, `Harness/artifacts/control/loop_processes.md` | entropy reduction is part of normal operations |

## Adopt, Adapt, Reject

### Adopt Directly

- Repository-local knowledge should be the durable system of record.
- Agents perform better with progressive disclosure and stable entrypoints than with one giant instruction blob.
- Long-running work needs durable handoff artifacts, explicit state continuity, and clean session closeout.
- Context is finite, so prompts, tools, and examples should stay high-signal and intentionally curated.
- Approval pauses, durable event history, and resumable status are core long-running harness features.
- Recurring cleanup and drift management should be built into the operating model.

### Adapt For Moradins Harness

- "Humans steer, agents execute" becomes a stricter contract here: humans approve each cycle, each deploy/generate handoff, and each release promotion.
- Initializer/implementer or generator/checker splits are allowed only as a reference pattern and only when they preserve explicit human gates.
- Feature lists, progress notes, and event histories are adapted into canonical `docs/exec_plans/`, `Harness/artifacts/control/`, builder artifacts, and status history rather than arbitrary local files.
- Mechanized taste and architectural invariants are welcome, but they must route through repo-native checks and documented contracts.

### Reject For Current Scope

- Minimal blocking merge gates as a default repository philosophy.
- Agents merging their own work directly to protected branches.
- "Zero human-written code" as a success metric.
- Hidden execution, unattended target-repo mutation, or silent approval bypasses.
- Scope growth into public hosting, desktop shells, multi-user control planes, or expanded auth modes without new approval.

When external guidance conflicts with Moradins Harness governance, Moradins Harness governance wins.
