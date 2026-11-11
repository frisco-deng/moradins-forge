---
title: "Codex Run Loop"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../Harness/entrypoints/codex.md
related_docs:
  - ../references/moradin_forge_agent_integration_contract_v1.md
  - ../references/moradin_agent_efficiency_contract_v1.md
---

# Codex Run Loop

1. Read the Forge entrypoints.
2. Recover approved workspace roots, onboard and inspect the target repo.
3. Run explain, readiness, and plan.
4. Ask for approval only when adopting or applying to a target repo outside
   the scope already accepted in the current task.
5. For an accepted target and plan, continue reversible apply, validation,
   rollback preparation, and review without asking again.
6. Execute only digest-approved user-level tooling; leave privileged scripts
   and interactive suite approvals with the user. Verify and summarize rollback.

## Current Working-Baseline Contract

Recover the whole-product view from existing product, architecture and plan
sources before consequential component choices: intended users, primary journey,
baseline acceptance, broader accepted outcomes, owners, critical dependencies
and operating constraints. Distinguish facts, assumptions and unknowns; investigate
what can change the next decision rather than requiring a complete blueprint.

Each slice names its product outcome, consumed/provided interfaces and integrated
acceptance. A branch/component milestone is not the whole product. Profiles are
advisory; do not invent services, storage or agent orchestration from a label.
Probe uncertain data ownership, interfaces, trust, deployment and capacity early.
On dependency change, identify affected consumers/contracts/plans and validation
evidence, update the current contract, preserve unaffected work and continue
independent lanes. Deferred accepted outcomes remain unfinished.

This is the canonical current Forge execution contract. Older process summaries
are historical where they differ; preserve their receipts and original scope.
Target-native security, approval and promotion rules remain authoritative.

For each component, establish a working slice, integrate its normal application
path, prove repeatability, automate known steps, then extend robustness and
broader hardening. Overlap stages when dependencies justify it. Record current
acceptance, essential safeguards, deferred obligations, owner and next action in
the existing plan/checkpoint. Deferred endpoints remain unfinished.

Manual, discovery and saved inputs converge on the same reviewed configuration,
trust handling, planner and executors. Test the packaged producer-to-consumer
handoff before expensive promotion: config/trust, software selection and durable
execution ownership must reach their actual consumers. Keep observations,
desired configuration, software identity and deployed state distinct. Reuse only
input-matched evidence and preserve native freshness, hash and security gates.

Scope each prerequisite to its protected operation; unselected components and
later qualification do not automatically block independent work. A native guard
still binds: change applicability only through its owning reviewed mechanism,
with negative tests. Never blindly retry an uncertain mutation.

On continuation, recover current task identity, accepted scope/method amendment,
owner and eligible next action. Goals retain outcomes, not an obsolete method.
Answer a completed side request once, then resume independent work. Do not create
or replace a Goal merely to change approach. Global latest-session lookup is an
explicit diagnostic, never the default recovery route.

Use optional shared commands only when installed. Otherwise use `make repo-brief`
and this checklist: retain every accepted endpoint, distinguish source/preparation
from installed acceptance, investigate unknowns, continue eligible work, and name
only actual operator boundaries. Do not require a Goal for ordinary execution.

For long-running commands, preserve native progress on stderr and the final
result on stdout. Successful wrappers do not prove nested completion. For known
running work use bounded waits or independent work; retain native exit evidence.
