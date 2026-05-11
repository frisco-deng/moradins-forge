# Moradin Forge Agent Handoff

Use this prompt when a user sends an agent to Moradin's Forge for the first
time.

```text
You are at Moradin's Forge.

First inspect FORGE.md, AGENTS.md, Harness/entrypoints/forge.md, and the target
repo's own guidance. Explain what Forge will add, what it will not do, the
files it proposes to write, the request-only install behavior, validation
commands, and rollback.

Do not apply changes until the user explicitly approves. Keep everything local
unless the user asks for external tooling. Preserve the target repo's existing
workflows and root files by default.

Use the deterministic sequence:
1. scripts/moradin_forge.sh explain
2. scripts/moradin_forge.sh readiness --target <target-repo>
3. scripts/moradin_forge.sh plan --target <target-repo>
4. scripts/moradin_forge.sh apply --target <target-repo> --approve
5. scripts/moradin_forge.sh verify --target <target-repo>
```
