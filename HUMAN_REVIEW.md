# HUMAN_REVIEW

Human review is required before Forge mutates a target repo.

Before approving apply, confirm:

- the agent inspected Forge and the target repo,
- proposed writes are limited to approved paths,
- each user-level install is bound to the reviewed tooling-plan digest,
- privileged tools remain in a generated script for the user to run,
- PATH or shell-profile changes have separate consent,
- rollback is clear,
- target root workflows remain preserved by default.

For public repo changes, require the release gates in
`docs/references/repo_operating_model_v1.md`.
