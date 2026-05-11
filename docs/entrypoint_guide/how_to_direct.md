---
title: "How To Direct"
status: approved
owner: platform-operations
last_reviewed: 2026-03-17
source_refs: []
related_docs:
  - index.md
  - ../11_ops/quick_start.md
  - ../11_ops/codex_run_loop.md
---

# How To Direct

## Operator Prompt Pattern

- State one phase/stage/cycle objective.
- Provide acceptance checks and required artifacts.
- Require a human-gate stop before continuation.

## Builder Prompt Patterns

### New Project

```text
Review the current Builder state for a new project.
Use the prompt bundle and linked artifacts only.
Recommend the next operator action to move from discovery to generated repo output.
Do not apply changes automatically.
```

### Existing Project

```text
Review the current Builder state for an existing-project sidecar deploy.
Focus on scan gaps, SSH target safety, approval status, sidecar readiness, and whether phase-planning prompts are now available.
Recommend the next guarded action only.
Do not apply changes automatically.
```

### Build Project Phases

```text
Review the latest deploy artifacts for this target repo.
Use the phase plan, execution prompts, and template fill map only.
Recommend the next human-triggered phase action.
Do not execute Codex or mutate repo state automatically.
```

### Implement Phase 1

```text
Review the generated phase 1 execution prompt and linked artifacts.
Suggest the smallest safe implementation slice that should happen next.
Keep human approval checkpoints explicit and do not auto-apply changes.
```

## Review Prompt Pattern

```text
Review the current Moradins Harness queues and approval surfaces.
Summarize blockers first, then the next reviewer action.
Reference the linked docs or artifacts when relevant.
Do not mutate repository state.
```

## Project Status Prompt Pattern

```text
Review the current project-status report and status history.
Prioritize critical and high-severity actions.
Explain which action should happen next and why.
Do not apply changes automatically.
```

## Harness Artifact Direction

- When directing Codex or Claude, name the artifact path explicitly.
- Prefer:
  - prompt bundle
  - prompt context
  - project scan summary
  - template fill map
  - assistant run log
- Tell the assistant whether the requested output is:
  - recommendation only
  - prompt refinement
  - docs expansion
  - implementation plan

## Companion Reminder

- The harness UI is the browser-side control surface.
- Assistant commands execute on the Linux host that launched the harness.
- Use `/deploy/map` before `/deploy/builder` when the operator needs to understand what the harness will fill.
- Use `/deploy/status` after guarded deploy or follow-on planning work when the operator needs the next action queue.
