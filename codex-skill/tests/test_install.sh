#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/.." && pwd)"
PLUGIN_DIR="${REPO_ROOT}/cli-anything-plugin"
TMP_DIR="$(mktemp -d)"
CODEX_HOME="${TMP_DIR}/codex-home"
INSTALLED_DIR="${CODEX_HOME}/skills/cli-anything"
STALE_STAGING_DIR="${CODEX_HOME}/skills/.cli-anything.tmp.stale"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_file() {
  [[ -f "$1" ]] || fail "expected file: $1"
}

assert_same() {
  cmp -s "$1" "$2" || fail "files differ: $1 $2"
}

assert_tree_same() {
  diff -qr "$1" "$2" >/dev/null || fail "directories differ: $1 $2"
}

mkdir -p "${STALE_STAGING_DIR}/codex-skill"
echo "left over from an interrupted install" > "${STALE_STAGING_DIR}/codex-skill/stale.txt"

CODEX_HOME="${CODEX_HOME}" bash "${SKILL_DIR}/scripts/install.sh"

assert_file "${INSTALLED_DIR}/SKILL.md"
[[ -d "${STALE_STAGING_DIR}" ]] ||
  fail "installer reused or removed the stale staging directory"
[[ ! -d "${INSTALLED_DIR}/codex-skill" ]] ||
  fail "installer created a nested codex-skill directory"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"
assert_file "${INSTALLED_DIR}/references/commands/cli-anything.md"
assert_file "${INSTALLED_DIR}/references/commands/refine.md"
assert_file "${INSTALLED_DIR}/references/commands/test.md"
assert_file "${INSTALLED_DIR}/references/commands/validate.md"
assert_file "${INSTALLED_DIR}/references/commands/list.md"
assert_file "${INSTALLED_DIR}/references/guides/auto-save-dry-run.md"
assert_file "${INSTALLED_DIR}/references/guides/session-locking.md"
assert_file "${INSTALLED_DIR}/references/guides/preview-methodology.md"
assert_file "${INSTALLED_DIR}/scripts/repl_skin.py"
assert_file "${INSTALLED_DIR}/scripts/preview_bundle.py"
assert_file "${INSTALLED_DIR}/scripts/skill_generator.py"
assert_file "${INSTALLED_DIR}/scripts/templates/SKILL.md.template"
assert_file "${INSTALLED_DIR}/references/docs/PREVIEW_PROTOCOL.md"

assert_same "${PLUGIN_DIR}/HARNESS.md" "${INSTALLED_DIR}/references/HARNESS.md"
assert_same "${PLUGIN_DIR}/repl_skin.py" "${INSTALLED_DIR}/scripts/repl_skin.py"
assert_same "${PLUGIN_DIR}/preview_bundle.py" "${INSTALLED_DIR}/scripts/preview_bundle.py"
assert_same "${PLUGIN_DIR}/skill_generator.py" "${INSTALLED_DIR}/scripts/skill_generator.py"
assert_same "${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md" "${INSTALLED_DIR}/references/docs/PREVIEW_PROTOCOL.md"
assert_tree_same "${PLUGIN_DIR}/commands" "${INSTALLED_DIR}/references/commands"
assert_tree_same "${PLUGIN_DIR}/guides" "${INSTALLED_DIR}/references/guides"
assert_tree_same "${PLUGIN_DIR}/templates" "${INSTALLED_DIR}/scripts/templates"

python3 -m py_compile \
  "${INSTALLED_DIR}/scripts/repl_skin.py" \
  "${INSTALLED_DIR}/scripts/preview_bundle.py" \
  "${INSTALLED_DIR}/scripts/skill_generator.py"

if CODEX_HOME="${CODEX_HOME}" bash "${SKILL_DIR}/scripts/install.sh" >/dev/null 2>&1; then
  fail "installer overwrote an existing skill"
fi

grep -q 'references/HARNESS.md' "${INSTALLED_DIR}/SKILL.md" ||
  fail "installed SKILL.md does not point to vendored HARNESS.md"

DETACHED_ROOT="${TMP_DIR}/detached"
DETACHED_LOG="${TMP_DIR}/detached-install.log"
mkdir -p "${DETACHED_ROOT}"
cp -R "${SKILL_DIR}" "${DETACHED_ROOT}/codex-skill"
if CODEX_HOME="${TMP_DIR}/detached-home" bash "${DETACHED_ROOT}/codex-skill/scripts/install.sh" >"${DETACHED_LOG}" 2>&1; then
  fail "installer accepted a detached skill without canonical resources"
fi
grep -q 'Cannot find canonical CLI-Anything resources' "${DETACHED_LOG}" ||
  fail "detached install did not explain the missing canonical resources"

echo "PASS: Codex skill installer vendors the complete CLI-Anything resource set."
