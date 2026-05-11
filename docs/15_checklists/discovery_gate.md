---
title: "Discovery Gate Checklist"
status: approved
owner: platform-operations
last_reviewed: 2026-03-02
source_refs: []
related_docs:
  - ../11_ops/discovery_loop.md
  - ../references/discovery_prompt_contract.md
---

# Discovery Gate Checklist

## Preconditions

- [ ] Discovery session exists and is accessible.
- [ ] Intake fields are complete for project goal, users, constraints, and deployment target.
- [ ] Question set generated and reviewed.

## Synthesis Quality

- [ ] Synthesis includes summary, profile recommendation, and explicit open questions.
- [ ] Product spec draft was written to `docs/product_specs/`.
- [ ] Design draft was written to `docs/design_docs/`.
- [ ] Implementation draft plan was written to `docs/exec_plans/implementation/active/`.

## Human Approval

- [ ] Approval artifact exists under `Harness/artifacts/control/discovery_sessions/<session_id>/`.
- [ ] Reviewer decision recorded (`approved` or `rejected`).
- [ ] Execution scope is blocked until approval status is `approved`.
