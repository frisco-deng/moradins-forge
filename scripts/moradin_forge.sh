#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

cd "$REPO_ROOT"

if command -v uv >/dev/null 2>&1; then
  exec uv run python "$REPO_ROOT/scripts/moradin_forge.py" "$@"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$REPO_ROOT/scripts/moradin_forge.py" "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$REPO_ROOT/scripts/moradin_forge.py" "$@"
fi

printf '%s\n' "moradin-forge: Python 3 is required; write an install request from another host or install Python manually." >&2
exit 127
