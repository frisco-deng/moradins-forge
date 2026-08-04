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

OUTPUT_DIR="$REPO_ROOT/artifacts/bootstrap/latest"
OUTPUT_PATH="$OUTPUT_DIR/install-prerequisites.sh"
mkdir -p "$OUTPUT_DIR"
{
  printf '%s\n' '#!/usr/bin/env bash'
  printf '%s\n' 'set -euo pipefail'
  printf '%s\n' 'if ! command -v brew >/dev/null 2>&1; then'
  printf '%s\n' '  printf "%s\n" "Homebrew is required for this user-level plan. Install it from https://brew.sh after review." >&2'
  printf '%s\n' '  exit 2'
  printf '%s\n' 'fi'
  printf '%s\n' 'if [[ "${1:-}" != "--apply" ]]; then'
  printf '%s\n' '  printf "%s\n" "dry-run formulae: git python"'
  printf '%s\n' '  printf "%s\n" "reversal: brew uninstall git python"'
  printf '%s\n' '  exit 0'
  printf '%s\n' 'fi'
  printf '%s\n' 'brew install git python'
  printf '%s\n' 'git --version'
  printf '%s\n' 'python3 --version'
  printf '%s\n' 'printf "%s\n" "reversal: brew uninstall git python"'
} > "$OUTPUT_PATH"
chmod 0755 "$OUTPUT_PATH"
printf '%s\n' "moradin-forge bootstrap: Python 3 is required." >&2
printf '%s\n' "Review $OUTPUT_PATH, dry-run it, then run: $OUTPUT_PATH --apply" >&2
exit 127
