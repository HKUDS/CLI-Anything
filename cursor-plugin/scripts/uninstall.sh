#!/usr/bin/env bash

set -euo pipefail

for arg in "$@"; do
  case "${arg}" in
    --help|-h)
      echo "Usage: $0"
      echo "Uninstall the CLI-Anything Cursor local plugin and clear the discovery pointer."
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      echo "Usage: $0" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PLUGIN_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
DISCOVERY_POINTER="$(discovery_pointer_path)"

if [[ -f "${PLUGIN_SRC}/PLUGIN_ROOT.txt" && -f "${PLUGIN_SRC}/.cursor-plugin/plugin.json" ]]; then
  DEST_DIR="${PLUGIN_SRC}"
else
  if [[ -n "${CURSOR_PLUGINS_HOME:-}" ]]; then
    PLUGINS_HOME="$(resolve_plugins_home "${CURSOR_PLUGINS_HOME}")"
  else
    PLUGINS_HOME="$(resolve_plugins_home "${HOME}/.cursor/plugins")"
  fi
  DEST_DIR="${PLUGINS_HOME}/local/cli-anything"
fi

if ! is_cli_anything_install_path "${DEST_DIR}"; then
  echo "Refusing to uninstall unexpected path (expected .../local/cli-anything): ${DEST_DIR}" >&2
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

echo "Uninstall complete. Reload the Cursor window if it is open."
