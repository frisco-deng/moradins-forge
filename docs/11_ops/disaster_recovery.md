---
title: "Disaster Recovery"
status: approved
owner: platform-architecture
last_reviewed: 2026-02-23
source_refs:
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
  - https://medium.com/@DataDo/building-production-grade-agentic-rag-a-technical-deep-dive-part-1-beyond-fixed-windows-9879cf3cc7b1
related_docs:
  - index.md
  - ../00_overview/engineer_entrypoint.md
---

# Disaster Recovery

## Purpose

- Define runbooks and environment controls for safe, repeatable operations.
- This document defines executable expectations for `disaster_recovery`.

## Scope

- In scope: decisions, interfaces, risks, and checks that can be validated.
- Out of scope: speculative implementation detail without contract or runbook impact.

## Topic Decisions

- Disaster recovery defines backup, restore, and failover policy.
- Recovery objectives include RTO, RPO, and communication paths.
- Operational procedures require deterministic command evidence.
- Run-loop governance enforces one-cycle execution and human continuation gates.
- Recovery and rollback plans are required for all production-impacting changes.

## Interfaces / Dependencies

- Disaster interfaces connect recovery steps to service ownership.
- Recovery interfaces define primary/secondary operating procedures.
- Ops artifacts coordinate deployment, upgrades, and incident execution.
- Ops decisions are validated by checklists and generated run reports.

## Failure Modes / Risks

- Untested recovery paths increase outage duration.
- Unclear recovery ownership delays restoration.
- Runbook drift causing inconsistent operator response.
- Cycle execution without clear continuation decision.

## Verification Checklist

- [ ] Recovery drills and evidence are tracked.
- [ ] Recovery objectives are tested against runbook scenarios.
- [ ] Runbook steps are deterministic and operator-ready.
- [ ] Escalation and rollback paths are explicit.

## Related Docs

- index.md
- ../00_overview/engineer_entrypoint.md
