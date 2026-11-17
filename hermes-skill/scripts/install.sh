#!/usr/bin/env bash
#
# Install the CLI-Anything skill for Hermes Agent.
#
# The installer vendors the canonical CLI-Anything resources (HARNESS.md,
# command specs, guides, templates, helper modules) into the installed skill so
# a normal Hermes installation is self-contained and does not depend on keeping
# a repository checkout around.
#
# Usage:
#   bash hermes-skill/scripts/install.sh [--force] [--dry-run] [--profile NAME] [--skill-dir DIR]
#
# Environment:
#   HERMES_HOME   Hermes home directory (default: $HOME/.hermes)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/.." && pwd)"
PLUGIN_DIR="${REPO_ROOT}/cli-anything-plugin"
PREVIEW_PROTOCOL="${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md"
VERIFY_SCRIPT="${SKILL_DIR}/scripts/verify_harness.py"

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PROFILE=""
SKILL_DIR_OVERRIDE=""
FORCE=0
DRY_RUN=0
STAGING_DIR=""

usage() {
  cat <<'EOF'
Install the CLI-Anything skill for Hermes Agent.

  --force             replace an existing installation
  --dry-run           show what would be installed, change nothing
  --profile NAME      install into $HERMES_HOME/profiles/NAME/skills
  --skill-dir DIR     install into DIR/cli-anything-hermes instead of the default
  -h, --help          show this help

Environment:
  HERMES_HOME         Hermes home directory (default: ~/.hermes)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --profile) PROFILE="${2:-}"; [[ -n "${PROFILE}" ]] || { echo "--profile needs a name" >&2; exit 2; }; shift 2 ;;
    --skill-dir) SKILL_DIR_OVERRIDE="${2:-}"; [[ -n "${SKILL_DIR_OVERRIDE}" ]] || { echo "--skill-dir needs a path" >&2; exit 2; }; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -n "${SKILL_DIR_OVERRIDE}" ]]; then
  DEST_ROOT="${SKILL_DIR_OVERRIDE}"
elif [[ -n "${PROFILE}" ]]; then
  DEST_ROOT="${HERMES_HOME}/profiles/${PROFILE}/skills"
else
  DEST_ROOT="${HERMES_HOME}/skills"
fi
DEST_DIR="${DEST_ROOT}/cli-anything-hermes"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf "${STAGING_DIR}"
  fi
}
trap cleanup EXIT

[[ -f "${PLUGIN_DIR}/HARNESS.md" ]] ||
  fail "cannot find canonical CLI-Anything resources at ${PLUGIN_DIR}
Run this installer from a full CLI-Anything repository checkout."
[[ -f "${PREVIEW_PROTOCOL}" ]] ||
  fail "cannot find the preview protocol at ${PREVIEW_PROTOCOL}
Run this installer from a full CLI-Anything repository checkout."
[[ -f "${VERIFY_SCRIPT}" ]] ||
  fail "cannot find the harness verifier at ${VERIFY_SCRIPT}"

if [[ -e "${DEST_DIR}" && ${FORCE} -eq 0 ]]; then
  fail "${DEST_DIR} already exists.
Re-run with --force to replace it, or remove it manually."
fi

if [[ ${DRY_RUN} -eq 1 ]]; then
  echo "Dry run — nothing was written."
  echo "  skill source : ${SKILL_DIR}"
  echo "  destination  : ${DEST_DIR}"
  echo "  vendored from: ${PLUGIN_DIR}, ${PREVIEW_PROTOCOL}"
  if [[ -e "${DEST_DIR}" ]]; then
    echo "  note         : destination exists and would be replaced (--force)"
  fi
  exit 0
fi

mkdir -p "${DEST_ROOT}"
STAGING_DIR="$(mktemp -d "${DEST_ROOT}/.cli-anything-hermes.tmp.XXXXXX")"

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

# Verify the staged tree before it becomes the live skill.
[[ -f "${STAGING_DIR}/SKILL.md" ]] || fail "staged skill is missing SKILL.md"
cmp -s "${PLUGIN_DIR}/HARNESS.md" "${STAGING_DIR}/references/HARNESS.md" ||
  fail "vendored HARNESS.md does not match the canonical copy"
cmp -s "${PLUGIN_DIR}/repl_skin.py" "${STAGING_DIR}/scripts/repl_skin.py" ||
  fail "vendored repl_skin.py does not match the canonical copy"
if command -v python3 >/dev/null 2>&1; then
  python3 -m py_compile \
    "${STAGING_DIR}/scripts/repl_skin.py" \
    "${STAGING_DIR}/scripts/preview_bundle.py" \
    "${STAGING_DIR}/scripts/skill_generator.py" \
    "${STAGING_DIR}/scripts/verify_harness.py" ||
    fail "vendored Python modules did not compile"
  rm -rf "${STAGING_DIR}/scripts/__pycache__"
fi

if [[ -e "${DEST_DIR}" ]]; then
  rm -rf "${DEST_DIR}"
fi
mv "${STAGING_DIR}" "${DEST_DIR}"
STAGING_DIR=""

echo "Installed the CLI-Anything skill to: ${DEST_DIR}"
echo "Vendored HARNESS.md, command specs, guides, templates and helper modules."
echo "Next: start a new Hermes session (the skill index is built at session start),"
echo "then ask Hermes to build, refine, test, validate or list a harness."
echo "Check any harness with: python3 ${DEST_DIR}/scripts/verify_harness.py <software-dir>"
