# Agent Entrypoint

## Role

Operate Moradins Harness as a manager repo with:

- `docs/` as canonical project truth
- `Harness/` as the control plane
- `Harness/moradin_payload/manifest.yaml` as the Moradin payload deployment contract
- `FORGE.md` and `Harness/entrypoints/forge.md` as the agent-first adoption path

## Execution Model

The agent must:

1. Load `docs/engineer_entry/` context and `docs/01_principles/foundational_principles.md` before implementation.
1. When MCP-like or open-world tool servers are in scope, load the repo-local or operator-provided tool trust policy before implementation.
2. Route work to one `phase_id`, `stage_id`, and `cycle_id`.
3. Execute one approved cycle only.
4. Prefer the shortest deterministic repo command path over prompt-only reasoning.
5. Update canonical artifacts under `Harness/artifacts/control/` and `docs/exec_plans/`.
6. Stop at the human gate unless explicit continuation is approved.
7. Run a documentation review loop every 3 completed cycles.
8. Answer the capability question before closeout unless reviewer-approved skip is explicit.
9. Keep manager-only control-plane logic out of downstream payload materialization.
10. Use request-only readiness artifacts for host tooling gaps; do not execute host installs from the UI or Forge scripts.
11. When asked to adopt Moradin into another repo, switch to the Forge consent-first sequence before writing target files.

The agent must not:

- expand scope beyond approved cycle
- modify `docs/engineer_entry/` except explicitly approved bootstrap updates
- start cycle `N+1` when cycle `N` gate artifacts or approvals are missing
- reintroduce legacy path aliases or fallback resolution logic

If architecture or long-lived boundaries change, open or update an ADR.

## Authority Model

The agent may:

- implement scoped code and tests
- update docs, runbooks, and checklists required by behavior changes
- create and route update, upgrade, tooling, and commissioning artifacts in `docs/exec_plans/`
- use repo-local skills under `skills/` as helpers, but not as source-of-truth gates

The agent must not:

- change contracts without versioning
- bypass security, gate, or compatibility enforcement
- treat `Harness/views/` as canonical over `docs/`

## Conflict Precedence

Contracts > Security > Tests > Service Style > Docs > Refactor

## Required Read Order

- `docs/engineer_entry/index.md`
- `docs/00_overview/engineer_entrypoint.md`
- `docs/01_principles/foundational_principles.md`
- repo-local or operator-provided tool trust policy when MCP-like or open-world tool servers enter scope
- `docs/11_ops/codex_run_loop.md`
- `docs/11_ops/change_tracking_system.md`
- `docs/11_ops/documentation_review_loop.md`
- `docs/15_checklists/agent_cycle_gate.md`
- `docs/15_checklists/documentation_review_gate.md`
- `docs/references/moradin_payload_contract_v1.md`
- `docs/references/moradin_forge_agent_integration_contract_v1.md`
- `docs/references/tooling_readiness_install_request_contract_v1.md`
- `docs/references/repo_registry_adapter_contract_v1.md`
- `docs/references/assistant_handoff_contract_v1.md`
- `Harness/routing/load_order.md`
- `Harness/schemas/canonical_paths.yaml`

## Quality Gates

- `make lint-py`
- `make lint-md`
- `make validate-skills`
- `npm --prefix dev_tracker/ui run check:engineer-entry`
- `make lint`

## Refactor-Specific Rules

- Back up the repo outside the project root before structural changes.
- Keep the canonical path graph singular and unambiguous.
- Do not modify external tracked projects during manager-repo refactors.
- Materialize the Moradin payload only into dry-run targets during refactor passes.
