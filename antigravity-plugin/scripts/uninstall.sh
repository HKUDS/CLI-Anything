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

if [[ -n "${WORKSPACE_PATH}" ]]; then
  WS_ROOT="$(resolve_workspace_root "${WORKSPACE_PATH}")"
  DEST_DIR="${WS_ROOT}/.agents/plugins/cli-anything"
elif [[ -f "${PLUGIN_SRC}/PLUGIN_ROOT.txt" && -f "${PLUGIN_SRC}/plugin.json" ]]; then
  DEST_DIR="${PLUGIN_SRC}"
else
  if [[ -n "${ANTIGRAVITY_PLUGINS_HOME:-}" ]]; then
    PLUGINS_HOME="$(resolve_plugins_home "${ANTIGRAVITY_PLUGINS_HOME}")"
  else
    PLUGINS_HOME="$(resolve_plugins_home "${HOME}/.gemini/config/plugins")"
  fi
  DEST_DIR="${PLUGINS_HOME}/cli-anything"
fi

if ! is_cli_anything_install_path "${DEST_DIR}"; then
  echo "Refusing to uninstall unexpected path (expected .../plugins/cli-anything): ${DEST_DIR}" >&2
  exit 1
fi

DEST_HOST="$(to_host_path "${DEST_DIR}")"
if [[ -d "${DEST_DIR}" ]]; then
  DEST_HOST="$(to_host_path "$(cd "${DEST_DIR}" && pwd -P)")"
fi

if [[ -e "${DEST_DIR}" ]]; then
  rm -rf "${DEST_DIR}"
  echo "Removed plugin directory: ${DEST_DIR}"
else
  echo "Plugin directory not found (already removed): ${DEST_DIR}"
fi

if [[ -f "${DISCOVERY_POINTER}" ]]; then
  POINTER="$(tr -d '\r\n' < "${DISCOVERY_POINTER}")"
  PTR_KEY="$(normalize_path_key "${POINTER}")"
  DEST_KEY="$(normalize_path_key "${DEST_HOST}")"
  DEST_UNIX_KEY="$(normalize_path_key "${DEST_DIR}")"
  if [[ "${PTR_KEY}" == "${DEST_KEY}" || "${PTR_KEY}" == "${DEST_UNIX_KEY}" ]]; then
    rm -f "${DISCOVERY_POINTER}"
    echo "Removed discovery pointer: ${DISCOVERY_POINTER}"
  else
    echo "Left discovery pointer unchanged (points elsewhere): ${POINTER}"
  fi
else
  echo "Discovery pointer not present: ${DISCOVERY_POINTER}"
fi

echo "Uninstall complete."
