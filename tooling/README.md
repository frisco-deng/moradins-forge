# Tooling Adapter

This directory is generated from the workspace tooling control plane.

- `repo_id`: `moradins-forge`
- `archetype`: `uv-harness`
- `containerized`: `false`

Primary entrypoints:

- `make repo-brief`
- `make verify-fast`
- `make verify`
- `make verify-security`
- `make review-ready`
- `make verify-ci`
- `make ci-local`

Optional readiness entrypoints:

- `make bootstrap-ci`
- `make bootstrap-security`
- `make verify-paths`
- `make fix-paths-safe`
- `make push-gate`
- `make release-gate-local`
- `make sonarqube-local`
- `make verify-ui-cli`
- `make forge-explain`
- `make payload-validate`
- `make payload-smoke`
- `make forge-smoke`
- `make public-portability-check`

Usage notes:

- Start with `make repo-brief` for compact branch, remote, workflow, target, and readiness context before broader shell exploration.
- Use `make bootstrap-ci` before `make verify-ci` in fresh CI runners or local scratch environments when the repo runtime has not been prepared yet.
- Use `make bootstrap-security` before `make verify-security` when scanner binaries or policy tooling are missing from the current machine.
- Use `make verify-paths` to check tracked files for raw workspace-root leakage before shipping docs, reports, or evidence artifacts.
- Use `make fix-paths-safe` only for deterministic rewrites of docs and generated reports; keep source, tests, config, and archive fixes manual unless the generator has been sanitized.
- Use `make push-gate` before pushing; it runs the local-first DevSecOps path, including path-origin checks, and records any emergency bypass reason.
- Treat `make verify-security` as the default local/on-prem security validation surface. It wraps repo-specific checks plus shared scanners such as `gitleaks`, pinned safe `trivy`, `semgrep`, `actionlint`, `zizmor`, `conftest`, and `yamllint` when those surfaces are present.
- Optional `make sonarqube-local` targets self-hosted SonarQube Community only when local `SONAR_HOST_URL` and `SONAR_TOKEN` are set; SonarCloud is not part of the default contract.
- Hardened or containerized adapters require Syft SBOM plus `grype dir:. --fail-on high`; standard repos keep Grype advisory unless they are promoted after baseline triage.
- Local unchanged `make verify-security` reruns may reuse fresh per-step scanner artifacts; GitHub Actions reruns required scanners by default.
- Use `make verify-ui-cli` only when it is rendered for the repo; it runs repo-declared browser/UI CLI checks using native headless mode or `xvfb-run` when explicitly required.
- Use `make ui-review-pack` only when it is rendered for the repo and visual/UI evidence is needed; it is an advisory full-review surface that should write `artifacts/ui-review/latest/summary.md`, screenshots under `artifacts/ui-review/latest/screenshots/`, and optional Lighthouse JSON under `artifacts/ui-review/latest/lighthouse/`.
- Use release-candidate targets only when they are rendered for the repo. Set `RELEASE_ARTIFACT`, `RELEASE_PLATFORM`, and platform-specific variables before running signing, smoke, production-readiness, or release-candidate-readiness wrappers.
- Use `tpl-ui-review-brief --repo <repo-id> --mode auto --prompt <prompt>` before UI page creation, component additions, existing-surface refinements, screenshot critiques, or formatting/readability fixes; existing defects need screenshot/route/state evidence, while greenfield UI does not.
- Use `make verify-ui-cli` for fast repo-declared browser smoke checks, and reserve `make ui-review-pack` for visual review, accessibility, mobile, reduced-motion, large-text, or Lighthouse evidence.
- Treat `make review-ready` as the handoff summary target before opening or updating a PR; it defaults to `REVIEW_READY_SCOPE=core`, can run safe repo-native prep hooks before the core checks, and writes concise artifacts for the LLM chain.
- Use `REVIEW_READY_SCOPE=full make review-ready` when you need container, SBOM, or CI-local detail in addition to the core PR checks.
- Use `make release-gate-local` before private Free `dev -> main` or promotion handoff; it writes `artifacts/tooling/release-gate-local/latest/{summary.json,summary.md}`, treats GitHub Actions as advisory evidence, and requires a manual human gate.
- Treat `make ci-local` as the local workflow truth surface; it runs workflow trigger audits, actionlint/zizmor/conftest/yamllint checks when available, and can execute `act` only when `CI_LOCAL_MODE=run` is set.
- When generated `tooling-*.yml` workflows exist, the workflow-focused scanners target that managed surface first before falling back to the repo's broader workflow directory.
- All generated information and verify targets write `summary.json`, `summary.md`, and step logs under `artifacts/tooling/<target>/` unless `TOOLING_LOG_ROOT` overrides the default.
- Rendered repos ignore `artifacts/` by default so repeated tooling runs do not create review noise.
- Activate the generated local pre-push hook with `pre-commit install --hook-type pre-push`; it calls `make push-gate` instead of spending hosted minutes on avoidable failures.
- From an operator shell, generated shared tool invocations bridge into codex-owned tooling automatically when needed.
- Use raw `codex-<tool>` commands only for bridge debugging or when a repo lacks deterministic verify entrypoints.

Generated files are safe to re-render. Edit central templates, not this directory, when changing the shared contract.
