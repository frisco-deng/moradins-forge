#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if command -v tpl-push-gate >/dev/null 2>&1; then
  exec tpl-push-gate --repo-root "${ROOT_DIR}" "$@"
fi

for candidate in "${TPL_ROOT:-}" "${TPLDECK_ROOT:-}" "${ROOT_DIR}/../.templates" "${HOME}/code/.templates"; do
  if [[ -n "${candidate}" && -x "${candidate}/scripts/tpl-push-gate" ]]; then
    exec "${candidate}/scripts/tpl-push-gate" --repo-root "${ROOT_DIR}" "$@"
  fi
done

printf 'push-gate: missing tpl-push-gate; install .templates shell helpers or set TPL_ROOT\n' >&2
exit 127
