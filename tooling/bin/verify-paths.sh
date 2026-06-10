#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"
export PYTHONDONTWRITEBYTECODE=1
exec python3 tooling/bin/tooling_runner.py "verify-paths" "$@"
