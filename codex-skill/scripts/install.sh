#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/.." && pwd)"
PLUGIN_DIR="${REPO_ROOT}/cli-anything-plugin"
PREVIEW_PROTOCOL="${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md"
DEST_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
DEST_DIR="${DEST_ROOT}/cli-anything"
STAGING_DIR=""

if [[ ! -f "${PLUGIN_DIR}/HARNESS.md" ]]; then
  echo "Cannot find canonical CLI-Anything resources at: ${PLUGIN_DIR}" >&2
  echo "Run this installer from a full CLI-Anything repository checkout." >&2
  exit 1
fi

if [[ ! -f "${PREVIEW_PROTOCOL}" ]]; then
  echo "Cannot find preview protocol at: ${PREVIEW_PROTOCOL}" >&2
  echo "Run this installer from a full CLI-Anything repository checkout." >&2
  exit 1
fi

mkdir -p "${DEST_ROOT}"

if [[ -e "${DEST_DIR}" ]]; then
  echo "Refusing to overwrite existing skill: ${DEST_DIR}" >&2
  echo "Remove it manually if you want to reinstall." >&2
  exit 1
fi

cleanup() {
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf "${STAGING_DIR}"
  fi
}
trap cleanup EXIT

STAGING_DIR="$(mktemp -d "${DEST_ROOT}/.cli-anything.tmp.XXXXXX")"
cp -R "${SKILL_DIR}/." "${STAGING_DIR}/"
mkdir -p \
  "${STAGING_DIR}/references/commands" \
  "${STAGING_DIR}/references/docs" \
  "${STAGING_DIR}/references/guides" \
  "${STAGING_DIR}/scripts/templates"

cp "${PLUGIN_DIR}/HARNESS.md" "${STAGING_DIR}/references/HARNESS.md"
cp "${PLUGIN_DIR}/commands/"*.md "${STAGING_DIR}/references/commands/"
cp "${PLUGIN_DIR}/guides/"*.md "${STAGING_DIR}/references/guides/"
cp "${PLUGIN_DIR}/repl_skin.py" "${STAGING_DIR}/scripts/repl_skin.py"
cp "${PLUGIN_DIR}/preview_bundle.py" "${STAGING_DIR}/scripts/preview_bundle.py"
cp "${PLUGIN_DIR}/skill_generator.py" "${STAGING_DIR}/scripts/skill_generator.py"
cp "${PLUGIN_DIR}/templates/"* "${STAGING_DIR}/scripts/templates/"
cp "${PREVIEW_PROTOCOL}" "${STAGING_DIR}/references/docs/PREVIEW_PROTOCOL.md"

mv "${STAGING_DIR}" "${DEST_DIR}"

echo "Installed Codex skill to: ${DEST_DIR}"
echo "Vendored CLI-Anything methodology resources into the installed skill."
echo "Restart Codex to pick up the new skill."
