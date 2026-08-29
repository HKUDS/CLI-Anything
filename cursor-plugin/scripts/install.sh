#!/usr/bin/env bash

set -euo pipefail

FORCE=0
for arg in "$@"; do
  case "${arg}" in
    --force|-f)
      FORCE=1
      ;;
    --help|-h)
      echo "Usage: $0 [--force]"
      echo "Install the CLI-Anything Cursor plugin with vendored methodology resources."
      echo "Destination: \${CURSOR_PLUGINS_HOME:-~/.cursor/plugins}/local/cli-anything"
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      echo "Usage: $0 [--force]" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PLUGIN_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PLUGIN_SRC}/.." && pwd)"
CANONICAL_PLUGIN="${REPO_ROOT}/cli-anything-plugin"
PREVIEW_PROTOCOL="${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md"

if [[ -n "${CURSOR_PLUGINS_HOME:-}" ]]; then
  PLUGINS_HOME="$(resolve_plugins_home "${CURSOR_PLUGINS_HOME}" create)"
else
  PLUGINS_HOME="$(resolve_plugins_home "${HOME}/.cursor/plugins" create)"
fi

DEST_ROOT="${PLUGINS_HOME}/local"
DEST_DIR="${DEST_ROOT}/cli-anything"
DISCOVERY_POINTER="$(discovery_pointer_path)"
STAGING_DIR=""

if [[ ! -f "${CANONICAL_PLUGIN}/HARNESS.md" ]]; then
  echo "Cannot find canonical CLI-Anything resources at: ${CANONICAL_PLUGIN}" >&2
  echo "Run this installer from a full CLI-Anything repository checkout." >&2
  exit 1
fi

if [[ ! -f "${PREVIEW_PROTOCOL}" ]]; then
  echo "Cannot find preview protocol at: ${PREVIEW_PROTOCOL}" >&2
  echo "Run this installer from a full CLI-Anything repository checkout." >&2
  exit 1
fi

if [[ ! -f "${PLUGIN_SRC}/.cursor-plugin/plugin.json" ]]; then
  echo "Cannot find Cursor plugin manifest at: ${PLUGIN_SRC}/.cursor-plugin/plugin.json" >&2
  exit 1
fi

mkdir -p "${DEST_ROOT}"
mkdir -p "${HOME}/.cursor"

if [[ -e "${DEST_DIR}" ]]; then
  if [[ "${FORCE}" -ne 1 ]]; then
    echo "Refusing to overwrite existing plugin: ${DEST_DIR}" >&2
    echo "Re-run with --force to upgrade, or remove it manually." >&2
    exit 1
  fi
fi

cleanup() {
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf "${STAGING_DIR}"
  fi
}
trap cleanup EXIT

STAGING_DIR="$(mktemp -d "${DEST_ROOT}/.cli-anything.tmp.XXXXXX")"

# Copy adapter package (exclude tests and any pre-existing local references/).
while IFS= read -r -d '' entry; do
  base="$(basename "${entry}")"
  case "${base}" in
    tests|references|.git)
      continue
      ;;
  esac
  cp -R "${entry}" "${STAGING_DIR}/"
done < <(find "${PLUGIN_SRC}" -mindepth 1 -maxdepth 1 -print0)

mkdir -p \
  "${STAGING_DIR}/references/commands" \
  "${STAGING_DIR}/references/docs" \
  "${STAGING_DIR}/references/guides" \
  "${STAGING_DIR}/scripts/templates"

cp "${CANONICAL_PLUGIN}/HARNESS.md" "${STAGING_DIR}/references/HARNESS.md"
cp "${CANONICAL_PLUGIN}/commands/"*.md "${STAGING_DIR}/references/commands/"
cp "${CANONICAL_PLUGIN}/guides/"*.md "${STAGING_DIR}/references/guides/"
cp "${CANONICAL_PLUGIN}/repl_skin.py" "${STAGING_DIR}/scripts/repl_skin.py"
cp "${CANONICAL_PLUGIN}/preview_bundle.py" "${STAGING_DIR}/scripts/preview_bundle.py"
cp "${CANONICAL_PLUGIN}/skill_generator.py" "${STAGING_DIR}/scripts/skill_generator.py"
cp "${CANONICAL_PLUGIN}/templates/"* "${STAGING_DIR}/scripts/templates/"
cp "${PREVIEW_PROTOCOL}" "${STAGING_DIR}/references/docs/PREVIEW_PROTOCOL.md"

# Atomic replace when upgrading.
# If interrupted after moving the old install aside, look for
# ${DEST_ROOT}/.cli-anything.bak.* and restore it manually.
if [[ -e "${DEST_DIR}" ]]; then
  BACKUP_DIR="${DEST_ROOT}/.cli-anything.bak.$(date +%s)"
  mv "${DEST_DIR}" "${BACKUP_DIR}"
  if ! mv "${STAGING_DIR}" "${DEST_DIR}"; then
    mv "${BACKUP_DIR}" "${DEST_DIR}"
    echo "Failed to install plugin; previous install restored." >&2
    exit 1
  fi
  rm -rf "${BACKUP_DIR}"
else
  mv "${STAGING_DIR}" "${DEST_DIR}"
fi
STAGING_DIR=""

# Resolve final absolute plugin root and stamp it for Cursor tool resolution.
PLUGIN_ROOT="$(to_host_path "$(cd "${DEST_DIR}" && pwd -P)")"
printf '%s\n' "${PLUGIN_ROOT}" > "${DEST_DIR}/PLUGIN_ROOT.txt"
printf '%s\n' "${PLUGIN_ROOT}" > "${DISCOVERY_POINTER}"

echo "Installed Cursor plugin to: ${DEST_DIR}"
echo "PLUGIN_ROOT stamp: ${PLUGIN_ROOT}"
echo "Discovery pointer: ${DISCOVERY_POINTER}"
echo "Vendored CLI-Anything methodology resources into the installed plugin."
echo "Reload the Cursor window (Developer: Reload Window) to pick up commands."
echo "Consumer Hub/skills are separate: npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y"
