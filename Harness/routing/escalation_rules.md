# Escalation Rules

- Escalate when an adoption would require changing target root workflows.
- Escalate when a target repo has conflicting agent or CI instructions.
- Escalate when readiness detects missing required tools.
- Escalate when generated sidecar verification fails.
- Investigate an unclear write set from repository evidence. Pause only the
  affected apply lane when a material target or write-scope decision cannot be
  inferred; continue unrelated validation and rollback preparation.
