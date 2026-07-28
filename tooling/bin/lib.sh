#!/usr/bin/env bash
set -euo pipefail

tooling_log() {
  printf '[tooling] %s\n' "$*"
}

tooling_skip() {
  tooling_log "SKIP: $*"
}

tooling_fail() {
  tooling_log "ERROR: $*"
  exit 2
}

tooling_allow_missing_tools() {
  [ "${TOOLING_ALLOW_MISSING_TOOLS:-0}" = "1" ]
}

tooling_allow_plain_docker() {
  [ "${TOOLING_ALLOW_PLAIN_DOCKER:-0}" = "1" ]
}

tooling_codex_user() {
  printf '%s' "${CODEX_TOOL_USER:-codex}"
}

tooling_current_user_is_codex() {
  [ "$(id -un)" = "$(tooling_codex_user)" ]
}

tooling_codex_tool_name() {
  printf 'codex-%s' "$1"
}

tooling_direct_docker_ready() {
  command -v docker >/dev/null 2>&1 || return 1
  bash -lc 'docker info >/dev/null 2>&1'
}

tooling_try_docker_cli() {
  if tooling_current_user_is_codex && tooling_direct_docker_ready; then
    printf '%s' "docker"
    return 0
  fi
  if command -v codex-docker >/dev/null 2>&1; then
    printf '%s' "codex-docker"
    return 0
  fi
  if tooling_allow_plain_docker && command -v docker >/dev/null 2>&1; then
    printf '%s' "docker"
    return 0
  fi
  return 1
}

tooling_try_tool_launcher() {
  local binary="$1"
  local codex_tool
  codex_tool="$(tooling_codex_tool_name "${binary}")"

  if tooling_current_user_is_codex && command -v "${binary}" >/dev/null 2>&1; then
    printf '%s' "${binary}"
    return 0
  fi
  if command -v "${codex_tool}" >/dev/null 2>&1; then
    printf '%s' "${codex_tool}"
    return 0
  fi
  if command -v "${binary}" >/dev/null 2>&1; then
    printf '%s' "${binary}"
    return 0
  fi
  return 1
}

tooling_rewrite_tool_command() {
  local binary="$1"
  local launcher="$2"
  local command="$3"

  if [[ "${launcher}" == "${binary}" ]]; then
    printf '%s' "${command}"
    return 0
  fi

  case "${command}" in
    "${binary}")
      printf '%s' "${launcher}"
      ;;
    "${binary} "*)
      printf '%s%s' "${launcher}" "${command#${binary}}"
      ;;
    *)
      tooling_fail "tool command does not start with expected binary: ${binary}"
      ;;
  esac
}

tooling_fail_or_allow_missing() {
  local message="$1"
  if tooling_allow_missing_tools; then
    tooling_log "WARN: ${message} (allowed by TOOLING_ALLOW_MISSING_TOOLS=1)"
    return 0
  fi
  tooling_fail "${message}"
}

run_checked() {
  local command="$1"
  tooling_log "+ ${command}"
  bash -lc "${command}"
}

run_required_tool() {
  local binary="$1"
  local command="$2"
  local launcher
  local resolved_command

  if ! launcher="$(tooling_try_tool_launcher "${binary}")"; then
    tooling_fail_or_allow_missing "missing command: ${binary}"
    return 0
  fi

  resolved_command="$(tooling_rewrite_tool_command "${binary}" "${launcher}" "${command}")"
  run_checked "${resolved_command}"
}

tooling_docker_cli() {
  local docker_cmd
  if docker_cmd="$(tooling_try_docker_cli)"; then
    printf '%s' "${docker_cmd}"
    return 0
  fi
  tooling_fail "container tooling requires either a direct codex-user docker context or the codex bridge from an operator shell. Run install-shell-helpers.sh and complete osplan.md, or set TOOLING_ALLOW_PLAIN_DOCKER=1 for a temporary local fallback."
}

run_docker_command() {
  local docker_args="$1"
  local docker_cmd
  docker_cmd="$(tooling_docker_cli)"
  tooling_log "+ ${docker_cmd} ${docker_args}"
  bash -lc "${docker_cmd} ${docker_args}"
}

docker_available() {
  local docker_cmd
  if ! docker_cmd="$(tooling_try_docker_cli)"; then
    return 1
  fi
  bash -lc "${docker_cmd} info >/dev/null 2>&1"
}
