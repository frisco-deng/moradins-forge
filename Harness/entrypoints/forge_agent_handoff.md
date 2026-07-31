# Moradin Forge Agent Handoff

Use this prompt when a user sends an agent to Moradin's Forge.

```text
You are at Moradin's Forge.

Read README.md, FORGE.md, AGENTS.md, and Harness/entrypoints/forge.md.
Ask which workspace roots the user approves. Run onboard once per approved
root, then show the discovered repository list before inspecting standard
guidance, manifests, CI, container, deployment, and configuration files. Do
not inspect arbitrary source or any path outside the approved roots.

Present the generated plan and request separate consent for workspace scope,
selected tools, user-level execution, each AGENTS.md or CLAUDE.md change,
PATH/shell configuration, privileged-script generation and user execution,
sidecar adoption, and rollback.

Run only digest-approved, verified user-level installers. Never invoke sudo,
enter credentials, or operate the interactive installer for the user. Offer
`install/tooling-suite.sh` when the user wants the complete Linux baseline;
the user launches it and confirms its exact digest-bound root transaction.
Adaptive privileged scripts remain user-run. Verify either path afterward.

Apply only approved marker blocks and the local sidecar. Preserve unrelated
agent guidance and repository workflows. Finish with security, portability,
and repository-native validation plus exact rollback commands.

After adoption, start with the compact context primer and repository brief.
Prefer fresh summaries over raw logs, request tools only when they materially
improve testing or diagnosis, and use rerun advice before repeating expensive
commands.

Start with:
scripts/moradin_forge.sh onboard --workspace <approved-workspace>
```
