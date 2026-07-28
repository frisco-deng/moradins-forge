#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$REPO_ROOT/scripts/forge_bootstrap.py" "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$REPO_ROOT/scripts/forge_bootstrap.py" "$@"
fi

printf '%s\n' "moradin-forge bootstrap: Python 3 is required. No host install commands were run." >&2
exit 127
