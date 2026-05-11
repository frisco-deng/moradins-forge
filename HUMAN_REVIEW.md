# HUMAN_REVIEW

Human review is required before Forge mutates a target repo.

Before approving apply, confirm:

- the agent inspected Forge and the target repo,
- proposed writes are limited to approved paths,
- host tool installs are request-only,
- rollback is clear,
- target root workflows remain preserved by default.

For public repo changes, require the release gates in
`docs/references/repo_operating_model_v1.md`.
