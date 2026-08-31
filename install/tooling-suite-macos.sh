#!/usr/bin/env bash
set -euo pipefail

umask 077
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
FORGE_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd -P)

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
	printf '%s\n' 'Run the tooling suite as the target user, not root.' >&2
	exit 2
fi

python_path=$(command -v python3 || true)
if [[ -z $python_path ]]; then
	printf '%s\n' 'Python 3.11+ is required. Review the official python.org or Homebrew package before continuing.' >&2
	exit 2
fi

exec "$python_path" "$FORGE_ROOT/scripts/moradin_tooling_suite_native.py" \
	--platform macos --forge-root "$FORGE_ROOT" "$@"
