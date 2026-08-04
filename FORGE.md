# Moradin's Forge

Moradin's Forge is the agent-first entrypoint for this repo.

The public handoff has three steps: clone Forge, ask the user to run the guided
Linux tooling suite, then onboard only user-approved workspace roots. The agent
explains and verifies the suite; the user operates its menu and approves sudo.
Onboarding shows exact provider diffs and requires separate consent per file.

If the user sent you here as Codex, Claude Code, or another coding agent:

1. Inspect this repo before proposing changes.
2. Inspect the user's target repo before proposing integration.
3. Explain what Moradin will add:
   - a local `.moradins-harness/` sidecar,
   - adaptive snippets under `.moradins-harness/adapters/`,
   - deterministic readiness, brief, and validation commands,
   - an adaptive tooling plan for approved workspaces,
   - independently approved Codex, Claude, Gemini, Copilot, and Cursor marker
     blocks at the fixed public paths.
4. Explain what Moradin will not do:
   - it will not publish or phone home,
   - it will not replace existing repo workflows,
   - it will not patch root workflow files by default,
   - it will not inspect outside approved workspace roots,
   - an agent will not invoke privileged installation or enter credentials.
5. Ask the user for explicit consent before running any apply command.
6. After consent, Forge may execute verified user-level installers. Adaptive
   privileged work is emitted as a reviewable script for the user to run. The
   separate human-run Linux suite may request sudo only after the user reviews
   and confirms its exact digest-bound transaction.

If the user wants a low-token first pass, run the platform bootstrap first:

```sh
install/bootstrap-linux.sh --target <target-repo>
install/bootstrap-macos.sh --target <target-repo>
```

On Windows PowerShell:

```powershell
.\install\bootstrap-windows.ps1 -Target <target-repo>
```

Bootstrap only clones or primes Forge and writes a sanitized start card under
`artifacts/bootstrap/latest/`; it never installs host tools, patches a target
repo, or runs `apply`.

For a complete Linux workstation baseline, ask the user to personally run:

```sh
install/tooling-suite.sh
```

Agents may explain, plan, and verify this flow but must not select menu options,
confirm its digest, invoke sudo, or supply credentials for the user.

For a disconnected Linux target, follow
`docs/11_ops/air_gapped_tooling_suite.md`. Generate a sanitized request on the
target, build the complete kit on a connected rootless host, return the kit and
its digest through separate channels, then verify/apply with network sources
disabled and onboard with `--offline`.

Use this deterministic path:

```sh
scripts/moradin_forge.sh explain
scripts/moradin_forge.sh onboard --workspace <workspace-root>
scripts/moradin_forge.sh tooling-plan --workspace <workspace-root>
scripts/moradin_forge.sh readiness --target <target-repo>
scripts/moradin_forge.sh plan --target <target-repo>
scripts/moradin_forge.sh apply --target <target-repo> --approve \
  --approve-agent-file AGENTS.md
scripts/moradin_forge.sh verify --target <target-repo>
```

For Forge repo maintenance, start with:

```sh
make repo-brief
make verify-paths
make verify-fast
make review-ready
```

Use `tpl context-primer --repo moradins-forge --concern auto --detail compact`
after a new session, compaction, long resume, or repeated broad reads. Prefer
current summaries and named artifacts before reopening source or long logs. Use
`tpl session-supervisor --mode steering-advisory --watch --live --latest-session --repo moradins-forge`
when work starts looping, and `tpl rerun-advice moradins-forge -- <command>`
before repeating long deterministic commands. Use the Python route reported by
`make repo-brief`; Forge is a `uv` repo and raw `python` is not the runtime
contract.

For release maintenance, use `make release-build`, then inspect
`artifacts/tooling/release-build/summary.md` and
`artifacts/release/release-manifest.json`. This core contract does not authorize
publication, signing, or platform-lane activation.

On Windows PowerShell, use:

```powershell
.\scripts\moradin_forge.ps1 explain
.\scripts\moradin_forge.ps1 readiness --target <target-repo>
.\scripts\moradin_forge.ps1 plan --target <target-repo>
.\scripts\moradin_forge.ps1 apply --target <target-repo> --approve
.\scripts\moradin_forge.ps1 verify --target <target-repo>
```

After apply, report the sidecar path, adapter status, install-request artifacts,
validation commands, rollback path, and any action the user must take manually.

Agent guidance is opt-in. Use `--approve-agent-file` only after showing the
owned block and receiving explicit approval for that fixed provider path; use
the matching `--create-agent-file` for an absent file. The allowlist is
`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, and
`.cursor/rules/moradin-forge.mdc`. `--patch-agents` remains a compatibility
alias for `AGENTS.md`.

Forge is a public-candidate repo. Public docs, sidecars, exports, and release
evidence must not contain raw home paths, usernames, hostnames, Windows user
paths, WSL UNC paths, Codex session paths, SSH clone URLs, raw temp paths, or
machine-origin markers. Use placeholders such as `<forge-root>`,
`<target-repo>`, `<temp-dir>`, and `<workbench-port>`.
