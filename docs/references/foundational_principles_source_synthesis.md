---
title: "Foundational Principles Source Synthesis"
status: approved
owner: platform-operations
last_reviewed: 2026-03-27
source_refs:
  - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://openai.com/index/harness-engineering/
  - https://openai.com/index/unlocking-the-codex-harness/
related_docs:
  - ../01_principles/foundational_principles.md
  - portability_copy_contract.md
  - redeployable_harness_contract_v1.md
---

# Foundational Principles Source Synthesis

## Purpose

- Preserve the provenance for the canonical principles document.
- Record what Moradins Harness adopts directly, adapts for local governance, and rejects for current scope.

This note is explanatory, not normative. The normative principles live in `docs/01_principles/foundational_principles.md`.

## Anthropic: Effective Harnesses For Long-Running Agents

### Adopt

- Separate environment setup from incremental execution.
- Leave durable state handoffs so fresh sessions can resume without guessing.
- Verify before marking progress complete.
- End each session in a clean, reviewable state.

### Adapt

- The initializer and coding split becomes a reference pattern here: bootstrap pass, implementer pass, optional reviewer or cleanup pass, then human gate.
- Progress files and feature lists map to Moradins Harness artifacts such as execution plans, changelogs, guidance tables, and builder outputs.

### Reject

- Any reading of the article that implies automatic chaining across sessions without explicit approval.

## Anthropic: Effective Context Engineering For AI Agents

### Adopt

- Context is finite and must be treated as a scarce resource.
- The right context is the smallest high-signal set that still preserves correct behavior.
- Tools should be clear, low-overlap, and token-efficient.
- Context curation is iterative, not a one-time prompt-writing task.

### Adapt

- Moradins Harness expresses context curation through short entrypoints, canonical doc trees, read-order contracts, and deterministic command surfaces.
- "Just in time" context retrieval becomes explicit operator- and agent-routed navigation through docs, artifacts, and status surfaces.

### Reject

- Bloated prompts, sprawling tool sets, or giant operator manuals as a substitute for curation.

## OpenAI: Harness Engineering

### Adopt

- Repository knowledge should be the system of record.
- `AGENTS.md` should work as a map, not an encyclopedia.
- Agent legibility matters as much as human legibility.
- Plans and knowledge artifacts should be versioned inside the repo.
- Golden-principle cleanup and recurring drift reduction should be continuous.
- Mechanical enforcement is stronger than aspirational convention.

### Adapt

- OpenAI's repository-autonomy lessons are narrowed here into a governed manager-repo model with explicit phase, stage, cycle, and human-gate contracts.
- Human taste and invariants should be encoded into docs, checks, and control artifacts, but only within the repo's scoped governance loop.

### Reject

- Minimal blocking merge gates as a default.
- Agents merging directly to protected branches.
- "All code is agent-generated" as a repository principle.

These are rejected because Moradins Harness explicitly keeps `main` clean, routes work through feature branches into `dev`, and requires human promotion review.

## OpenAI: Unlocking The Codex Harness

### Adopt

- Long-running agent systems need durable thread lifecycle and persistence.
- The control surface should expose stable event primitives rather than force clients to reconstruct hidden state.
- Approval requests should pause work until the client or operator responds.
- Server-side continuity matters because client sessions are ephemeral.

### Adapt

- Moradins Harness applies these ideas through builder status history, discovery artifacts, prompt bundles, and explicit approval artifacts rather than by adopting the App Server protocol itself.
- Remote and browser surfaces remain loopback-safe and operator-visible, with approvals and status artifacts acting as the continuity layer.

### Reject

- Protocol-level conclusions as universal product requirements. Moradins Harness adopts the governance lesson, not the specific transport surface.

## Resulting Local Synthesis

The external articles converge on a few shared ideas:

- make repository truth explicit
- keep context and tools intentionally narrow
- leave durable artifacts for the next session
- enforce invariants mechanically
- preserve approval pauses and resumability
- treat cleanup as a first-class system function

Moradins Harness keeps those ideas and then narrows them further:

- one approved cycle per human gate
- human-triggered assistant use only
- sidecar-only mutation for existing repos
- allowlisted writes only
- current-scope release remains Linux-hosted, browser-based, and single-user

That narrowing is intentional. The repo is not trying to maximize autonomy at any cost; it is trying to maximize legibility, operator safety, and trustworthy reuse.
