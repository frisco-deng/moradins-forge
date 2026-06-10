# Moradin Payload

`manifest.yaml` is the source of truth for the sidecar payload copied into a
target repo during Forge adoption.

The payload contract controls:

- included Forge docs, scripts, and support files,
- excluded generated or local-only artifacts,
- the default sidecar directory `.moradins-harness/`,
- platform bootstrap entrypoints and their shared request-only core,
- compatibility keys that keep early adopters stable during the public alpha.

Do not add generated local evidence or host-specific paths to the payload.
