#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="${1:-${CLI_ANYTHING_REPO:-}}"

if [[ -z "${REPO_ROOT}" ]]; then
  echo "Provide a repo root path as the first argument or set CLI_ANYTHING_REPO." >&2
  exit 1
fi

REPO_ROOT="$(cd "${REPO_ROOT}" && pwd)"

declare -A SOURCES=(
  [HARNESS]="${REPO_ROOT}/cli-anything-plugin/HARNESS.md"
  [REPL]="${REPO_ROOT}/cli-anything-plugin/repl_skin.py"
  [GENERATOR]="${REPO_ROOT}/cli-anything-plugin/skill_generator.py"
  [TEMPLATE]="${REPO_ROOT}/cli-anything-plugin/templates/SKILL.md.template"
  [OPENAI_YAML]="${REPO_ROOT}/codex-skill/agents/openai.yaml"
  [INSTALL_SH]="${REPO_ROOT}/codex-skill/scripts/install.sh"
  [INSTALL_PS1]="${REPO_ROOT}/codex-skill/scripts/install.ps1"
)

for key in "${!SOURCES[@]}"; do
  if [[ ! -f "${SOURCES[$key]}" ]]; then
    echo "Missing required source file for ${key}: ${SOURCES[$key]}" >&2
    exit 1
  fi
done

mkdir -p \
  "${SKILL_DIR}/references" \
  "${SKILL_DIR}/agents" \
  "${SKILL_DIR}/scripts" \
  "${SKILL_DIR}/assets/cli_anything_plugin/templates"

cp "${SOURCES[HARNESS]}" "${SKILL_DIR}/references/HARNESS.md"
cp "${SOURCES[REPL]}" "${SKILL_DIR}/assets/cli_anything_plugin/repl_skin.py"
cp "${SOURCES[GENERATOR]}" "${SKILL_DIR}/assets/cli_anything_plugin/skill_generator.py"
cp "${SOURCES[TEMPLATE]}" "${SKILL_DIR}/assets/cli_anything_plugin/templates/SKILL.md.template"
cp "${SOURCES[OPENAI_YAML]}" "${SKILL_DIR}/agents/openai.yaml"
cp "${SOURCES[INSTALL_SH]}" "${SKILL_DIR}/scripts/install.sh"
cp "${SOURCES[INSTALL_PS1]}" "${SKILL_DIR}/scripts/install.ps1"

echo "Sync complete."
