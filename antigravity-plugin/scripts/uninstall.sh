#!/usr/bin/env bash

set -euo pipefail

WORKSPACE_PATH=""

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --workspace|-w)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for ${1}" >&2
        exit 2
      fi
      WORKSPACE_PATH="${2}"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [--workspace <path>]"
      echo "Uninstall the CLI-Anything Google Antigravity plugin and clear the matching discovery pointer."
      exit 0
      ;;
    *)
      echo "Unknown argument: ${1}" >&2
      echo "Usage: $0 [--workspace <path>]" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PLUGIN_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
DISCOVERY_POINTER="$(discovery_pointer_path)"

SELF_VERIFIED=0
if [[ -n "${WORKSPACE_PATH}" ]]; then
  WS_ROOT="$(resolve_workspace_root "${WORKSPACE_PATH}")"
  DEST_DIR="${WS_ROOT}/.agents/plugins/cli-anything"
elif is_verified_self_install_dir "${PLUGIN_SRC}"; then
  DEST_DIR="${PLUGIN_SRC}"
  SELF_VERIFIED=1
elif [[ -e "${PLUGIN_SRC}/PLUGIN_ROOT.txt" || -L "${PLUGIN_SRC}/PLUGIN_ROOT.txt" ]]; then
  echo "Refusing to fall back to global uninstall: invoked from an installed plugin copy with a stale or mismatched PLUGIN_ROOT.txt (${PLUGIN_SRC})." >&2
  echo "Pass --workspace <path> to uninstall a relocated workspace copy, or run uninstall.sh from the source checkout to uninstall the global plugin." >&2
  exit 1
else
  if [[ -n "${ANTIGRAVITY_PLUGINS_HOME:-}" ]]; then
    PLUGINS_HOME="$(resolve_plugins_home "${ANTIGRAVITY_PLUGINS_HOME}")"
  else
    PLUGINS_HOME="$(resolve_plugins_home "${HOME}/.gemini/config/plugins")"
  fi
  DEST_DIR="${PLUGINS_HOME}/cli-anything"
fi

if [[ "${SELF_VERIFIED}" -ne 1 ]] && ! is_cli_anything_install_path "${DEST_DIR}"; then
  echo "Refusing to uninstall unexpected path (expected .../plugins/cli-anything): ${DEST_DIR}" >&2
  exit 1
fi

LOCK_DIR="$(dirname "${DEST_DIR}")"
LOCK_PATH="${LOCK_DIR}/.cli-anything.lock"
LOCK_HELD=0
MAIN_PID="${BASHPID:-$$}"

cleanup() {
  if [[ "${BASHPID:-$$}" != "${MAIN_PID}" ]]; then
    return 0
  fi
  if [[ "${LOCK_HELD}" -eq 1 ]]; then
    release_install_lock "${LOCK_PATH}"
  fi
}
trap cleanup EXIT

if [[ ! -e "${LOCK_DIR}" && ! -L "${LOCK_DIR}" ]]; then
  mkdir -p "${LOCK_DIR}"
fi
if [[ -d "${LOCK_DIR}" ]]; then
  acquire_install_lock "${LOCK_PATH}"
  LOCK_HELD=1
fi

DEST_HOST="$(to_host_path "${DEST_DIR}")"
if [[ -d "${DEST_DIR}" ]]; then
  DEST_HOST="$(to_host_path "$(cd "${DEST_DIR}" && pwd -P)")"
elif [[ -d "${LOCK_DIR}" ]]; then
  DEST_HOST="$(to_host_path "$(cd "${LOCK_DIR}" && pwd -P)/$(basename "${DEST_DIR}")")"
fi

if [[ -e "${DEST_DIR}" ]]; then
  rm -rf "${DEST_DIR}"
  echo "Removed plugin directory: ${DEST_DIR}"
else
  echo "Plugin directory not found (already removed): ${DEST_DIR}"
fi

remove_discovery_pointer_if_matches "${DISCOVERY_POINTER}" "${DEST_HOST}" "${DEST_DIR}"

echo "Uninstall complete."
