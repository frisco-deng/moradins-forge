---
title: "Project Builder SSH Operator Guide"
status: approved
owner: platform-operations
last_reviewed: 2026-03-07
source_refs: []
related_docs:
  - project_builder_runbook.md
  - docs/design_docs/project_builder_control_api.md
---

# Project Builder SSH Operator Guide

## Current-Scope Release

- SSH only
- `ssh_agent` auth supported
- `pem_path` auth supported
- PAT / HTTPS Git-host auth is deferred and documented only as a future-scope stub

## Saved Profile Fields

- label
- host
- user
- port
- allowlisted root
- auth method
- PEM path when required
- known hosts mode

## Supported Commands from the UI

- `pwd`
- `ls`
- `ls -- '<target_repo>'`
- `ls -- '<target_repo>/<sidecar_dir>'`

These are the only interactive commands exposed through the System Status and Builder buttons.

## Remote Deploy Flow

1. Validate and build the sidecar locally.
2. Open a guarded SSH connection.
3. Create the remote sidecar directory under the allowlisted root.
4. Stream the sidecar with tar-over-SSH.
5. Unpack only under `<allowlisted_root>/<target_repo>/<sidecar_dir>`.

## Failure Modes

- missing or invalid PEM path
- host/user/port validation failure
- allowlisted root not absolute
- remote SSH feature flag disabled
- remote repo path missing
- overwrite confirmation missing
- tar or ssh binary missing on the local operator host

## Operator Rules

- do not store passphrases or secrets in browser state
- prefer SSH agent when available
- use `accept_new` only for controlled bootstrap cases
- keep sidecar writes confined to the dedicated harness directory
