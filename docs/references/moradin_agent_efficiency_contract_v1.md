---
title: "Moradin Agent Efficiency Contract V1"
status: approved
owner: moradin-forge
last_reviewed: 2026-07-28
source_refs:
  - ../../scripts/moradin_workstation.py
related_docs:
  - moradin_forge_agent_integration_contract_v1.md
---

# Moradin Agent Efficiency Contract V1

## Purpose

Forge provides a portable subset of the shared `.templates` context workflow
without depending on private tooling.

## Commands

- `context-primer --target PATH`
- `state --target PATH`
- `repo-brief --target PATH`
- `rerun-advice --target PATH -- COMMAND...`
- `session-checkpoint --target PATH --outcome OUTCOME -- COMMAND...`
- `diagnostic-brief`

The context primer is capped at 6 KiB and contains exactly one next-action
section. State and brief commands prefer repository guidance, Git state,
standard capabilities, and repository-native deterministic commands.

## Generated Agent Guidance

Owned `AGENTS.md` and `CLAUDE.md` blocks direct agents to:

- begin with the compact primer and repository brief;
- use repository-native commands;
- consult fresh summaries before raw logs;
- request tools that materially improve testing or diagnosis;
- ask before changing the repository or installing tools;
- consult rerun advice before repeating expensive commands;
- expand context when evidence is missing, stale, contradictory,
  security-sensitive, or release-critical.

## Local Metrics

Forge records:

- primer runs and summarized byte counts;
- rerun checks and avoided reruns;
- evidence reuse;
- pass and fail outcome counts;
- hashes of command argv and repository state.

It does not record prompts, source text, raw commands, raw paths, logs,
usernames, hostnames, or repository contents. Efficiency artifacts are local,
ignored, and excluded from payload and public export.

These counters support evidence-backed comparisons over time; they are not a
claim that every session will use fewer tokens.
