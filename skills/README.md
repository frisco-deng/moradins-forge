# Repo Skills

Repo-local skills are versioned, optional execution helpers.

## Contract

- Skill root: `skills/`
- Registry: `skills/index.md`
- Skill folder contract: `skills/<skill_name>/SKILL.md`
- Optional per-skill assets: `scripts/`, `templates/`, `references/`

## Governance Mode

- Mode: `optional_approved`
- Skills may assist planning/execution.
- Deterministic repository commands remain source-of-truth gates.

## Validation

- Run `make validate-skills` for structural/frontmatter checks.
- `make lint` includes `validate-skills`.
