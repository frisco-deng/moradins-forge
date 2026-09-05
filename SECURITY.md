# SECURITY

Moradin's Forge is local-first and consent-gated.

- Agent/bootstrap flows do not install host tools or invoke elevation.
- The separate human-launched tooling suite may install only the operations in
  an exact digest-bound plan after default-No approval. Its privileged phase is
  sealed, receipt-backed, and never launched by an agent.
- Forge does not publish, upload, or phone home with target repo contents.
- Forge writes a sidecar only after explicit approval.
- Forge preserves target root workflows by default.
- Agent-driven adaptive setup writes privileged install requests as human-run
  instructions. The separately launched native tooling suite may enter its
  sealed elevated phase only through the user's exact plan approval.
- Forge bootstrap scripts only clone or prime the repo and write a sanitized
  start card; they do not install host tools or run adoption.
- Forge verification scans generated sidecars for forbidden host-specific
  references and unexpected root mutations.
- Public export checks reject raw home paths, macOS and Windows user paths, WSL
  UNC paths, Codex session paths, SSH clone URLs, raw temp paths, usernames, and
  hostnames.

## Supported Versions

Security fixes are applied to the current public beta line and the most recent
stable line after v1.0. Older prereleases are retained for provenance but are
not patched in place.

## Report A Vulnerability

Use GitHub's private vulnerability reporting form under **Security → Advisories
→ Report a vulnerability** for this repository. Include affected versions,
reproduction steps, impact, and any suggested mitigation. Do not open a public
issue for an unpatched vulnerability and do not include credentials, private
workspace contents, or raw machine identity in a report.

Maintainers will acknowledge a complete report, coordinate validation and a
fix privately, and publish an advisory when affected users can safely update.
No response-time SLA is promised during the prerelease period.

## Dependency Automation

- `dependency-readiness` is the read-only pull-request check for lock
  consistency, graph construction, and high/critical dependency findings.
- `submit-dependencies` writes the dependency snapshot only after protected
  `main` receives a merge; it is not a possible pull-request requirement.
- The scheduled security workflow reruns the full security surface weekly so
  lockfile vulnerabilities are detected even when hosted alert ingestion lags.
- Ruff policy changes and browser-stack changes are isolated from ordinary
  dependency batches for focused review.

Security references:

- `docs/references/moradin_forge_agent_integration_contract_v1.md`
- `docs/references/moradin_forge_installer_bootstrap_contract_v1.md`
- `docs/references/moradin_forge_tooling_suite_contract_v1.md`
- `docs/references/moradin_forge_tooling_suite_contract_v2.md`
- `docs/references/repo_operating_model_v1.md`
- `docs/references/tooling_readiness_install_request_contract_v1.md`
- `docs/15_checklists/security_review.md`
