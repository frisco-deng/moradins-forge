# SECURITY

Moradin's Forge is local-first and consent-gated.

- Forge does not install host tools.
- Forge does not publish, upload, or phone home with target repo contents.
- Forge writes a sidecar only after explicit approval.
- Forge preserves target root workflows by default.
- Forge writes install requests as human-run instructions instead of executing
  privileged setup commands.
- Forge verification scans generated sidecars for forbidden host-specific
  references and unexpected root mutations.

Security references:

- `docs/references/moradin_forge_agent_integration_contract_v1.md`
- `docs/references/tooling_readiness_install_request_contract_v1.md`
- `docs/15_checklists/security_review.md`
