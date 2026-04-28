#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEST_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
DEST_DIR="${DEST_ROOT}/cli-anything"

mkdir -p "${DEST_ROOT}"

if [[ -e "${DEST_DIR}" ]]; then
  echo "Refusing to overwrite existing skill: ${DEST_DIR}" >&2
  echo "Remove it manually if you want to reinstall." >&2
  exit 1
fi

cp -R "${SKILL_DIR}" "${DEST_DIR}"

echo "Installed Codex skill to: ${DEST_DIR}"
echo "Restart Codex to pick up the new skill."
