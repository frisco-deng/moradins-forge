---
title: "Capability Gap Review"
status: approved
owner: platform-operations
last_reviewed: 2026-02-24
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - agent_cycle_gate.md
  - ../11_ops/agent_harness_governance.md
  - ../11_ops/change_tracking_system.md
  - Harness/artifacts/control/changelog.md
  - Harness/artifacts/control/current_guidance.md
  - Harness/artifacts/control/capability_gap_register.md
  - docs/exec_plans/tech-debt-tracker.md
  - ../00_overview/engineer_entrypoint.md
---

# Capability Gap Review

## Purpose

- Convert capability gaps into enforceable, owner-assigned engineering actions.

## Intake Checklist

- [ ] Gap statement includes impacted user outcome and affected boundaries.
- [ ] Gap classification is one of: docs, contract, service, tooling, governance, prompt.
- [ ] Missing enforcement point is identified.
- [ ] Gap explicitly answers: "What capability is missing, and how do we make it legible and enforceable?"

## Resolution Checklist

- [ ] Legibility artifact is defined (docs, ADR, glossary, runbook, prompt template).
- [ ] Enforcement mechanism is defined (lint, contract rule, CI gate, checklist stop condition).
- [ ] Owner and target milestone are assigned.
- [ ] Validation evidence requirements are listed.
- [ ] Rollback or mitigation path is documented.

## Closure Checklist

- [ ] Capability implemented and merged.
- [ ] Acceptance evidence linked.
- [ ] Monitoring signal added for regression detection.
- [ ] Harness upgrade backlog entry updated if tooling or governance was changed.
- [ ] Changelog and guidance reports updated when policy behavior changed.
- [ ] Gap register entry moved to closed with closure date.

## Related Docs

- agent_cycle_gate.md
- ../11_ops/agent_harness_governance.md
- ../11_ops/change_tracking_system.md
- Harness/artifacts/control/changelog.md
- Harness/artifacts/control/current_guidance.md
- Harness/artifacts/control/capability_gap_register.md
- docs/exec_plans/tech-debt-tracker.md
- ../00_overview/engineer_entrypoint.md
