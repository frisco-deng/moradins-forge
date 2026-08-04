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
  printf '%s\n' 'if [[ "${1:-}" != "--apply" ]]; then'
  printf '%s\n' '  printf "%s\n" "dry-run packages: git python3 ca-certificates curl"'
  printf '%s\n' '  printf "%s\n" "reversal: apt-get remove -- git python3 ca-certificates curl"'
  printf '%s\n' '  exit 0'
  printf '%s\n' 'fi'
  printf '%s\n' 'if [[ "${EUID}" -ne 0 ]]; then'
  printf '%s\n' '  printf "%s\n" "Run this reviewed script explicitly with sudo." >&2'
  printf '%s\n' '  exit 2'
  printf '%s\n' 'fi'
  printf '%s\n' 'apt-get update'
  printf '%s\n' 'apt-get install -y -- git python3 ca-certificates curl'
  printf '%s\n' 'git --version'
  printf '%s\n' 'python3 --version'
  printf '%s\n' 'printf "%s\n" "reversal: apt-get remove -- git python3 ca-certificates curl"'
} > "$OUTPUT_PATH"
chmod 0755 "$OUTPUT_PATH"
printf '%s\n' "moradin-forge bootstrap: Python 3 is required." >&2
printf '%s\n' "Review $OUTPUT_PATH, dry-run it, then run: sudo $OUTPUT_PATH --apply" >&2
exit 127
