# Moradin Payload

`manifest.yaml` is the source of truth for the sidecar payload copied into a
target repo during Forge adoption.

The payload contract controls:

- included Forge docs, scripts, and support files,
- excluded generated or local-only artifacts,
- the default sidecar directory `.moradins-harness/`,
- platform bootstrap entrypoints and prerequisite-script bridge,
- bounded onboarding, digest-bound tooling, and offline bundle helpers,
- independently owned agent guidance and transactional upgrade controls,
- compatibility keys that keep early adopters stable during the public beta.

Do not add generated local evidence or host-specific paths to the payload.
