#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PLUGIN_SRC}/.." && pwd)"
CANONICAL_PLUGIN="${REPO_ROOT}/cli-anything-plugin"
TMP_DIR="$(mktemp -d)"
# Isolate HOME so discovery pointer and default paths stay inside the temp tree.
export HOME="${TMP_DIR}/home"
mkdir -p "${HOME}"
PLUGINS_HOME="${TMP_DIR}/plugins"
INSTALLED_DIR="${PLUGINS_HOME}/local/cli-anything"
STALE_STAGING_DIR="${PLUGINS_HOME}/local/.cli-anything.tmp.stale"
DISCOVERY_POINTER="${HOME}/.cursor/cli-anything-generator.root"

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

mkdir -p "${STALE_STAGING_DIR}"
echo "left over from an interrupted install" > "${STALE_STAGING_DIR}/stale.txt"

CURSOR_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh"

assert_file "${INSTALLED_DIR}/.cursor-plugin/plugin.json"
assert_file "${INSTALLED_DIR}/PLUGIN_ROOT.txt"
assert_file "${DISCOVERY_POINTER}"
assert_file "${INSTALLED_DIR}/commands/cli-anything.md"
assert_file "${INSTALLED_DIR}/commands/cli-anything-refine.md"
assert_file "${INSTALLED_DIR}/commands/cli-anything-test.md"
assert_file "${INSTALLED_DIR}/commands/cli-anything-validate.md"
assert_file "${INSTALLED_DIR}/commands/cli-anything-list.md"
assert_file "${INSTALLED_DIR}/skills/cli-anything-generator/SKILL.md"
assert_file "${INSTALLED_DIR}/rules/cli-anything-generator.mdc"
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
assert_file "${INSTALLED_DIR}/scripts/install.sh"
assert_file "${INSTALLED_DIR}/scripts/install.ps1"
assert_file "${INSTALLED_DIR}/scripts/uninstall.sh"
assert_file "${INSTALLED_DIR}/scripts/uninstall.ps1"
assert_file "${INSTALLED_DIR}/scripts/lib.sh"
assert_file "${INSTALLED_DIR}/scripts/lib.ps1"

STAMP="$(tr -d '\r\n' < "${INSTALLED_DIR}/PLUGIN_ROOT.txt")"
POINTER="$(tr -d '\r\n' < "${DISCOVERY_POINTER}")"
[[ -n "${STAMP}" ]] || fail "PLUGIN_ROOT.txt is empty"
[[ "${STAMP}" == "${POINTER}" ]] || fail "discovery pointer mismatch: ${POINTER} != ${STAMP}"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"

# On Git Bash / MSYS, stamps must be Windows host paths for Cursor Read tools.
case "$(uname -s 2>/dev/null || true)" in
  MINGW*|MSYS*|CYGWIN*)
    [[ "${STAMP}" =~ ^[A-Za-z]:\\ ]] ||
      fail "Windows Git Bash install must stamp a drive path, got: ${STAMP}"
    if command -v cygpath >/dev/null 2>&1; then
      STAMP_UNIX="$(cygpath -u "${STAMP}")"
      assert_file "${STAMP_UNIX}/references/HARNESS.md"
    fi
    ;;
  *)
    assert_file "${STAMP}/references/HARNESS.md"
    ;;
esac

[[ -d "${STALE_STAGING_DIR}" ]] ||
  fail "installer reused or removed the stale staging directory"
[[ ! -d "${INSTALLED_DIR}/tests" ]] ||
  fail "installer copied tests/ into the installed plugin"
[[ ! -d "${INSTALLED_DIR}/cursor-plugin" ]] ||
  fail "installer created a nested cursor-plugin directory"
[[ ! -d "${INSTALLED_DIR}/skills/cli-anything" ]] ||
  fail "old skills/cli-anything name should not be installed"

assert_same "${CANONICAL_PLUGIN}/HARNESS.md" "${INSTALLED_DIR}/references/HARNESS.md"
assert_same "${CANONICAL_PLUGIN}/repl_skin.py" "${INSTALLED_DIR}/scripts/repl_skin.py"
assert_same "${CANONICAL_PLUGIN}/preview_bundle.py" "${INSTALLED_DIR}/scripts/preview_bundle.py"
assert_same "${CANONICAL_PLUGIN}/skill_generator.py" "${INSTALLED_DIR}/scripts/skill_generator.py"
assert_same "${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md" "${INSTALLED_DIR}/references/docs/PREVIEW_PROTOCOL.md"
assert_tree_same "${CANONICAL_PLUGIN}/commands" "${INSTALLED_DIR}/references/commands"
assert_tree_same "${CANONICAL_PLUGIN}/guides" "${INSTALLED_DIR}/references/guides"
assert_tree_same "${CANONICAL_PLUGIN}/templates" "${INSTALLED_DIR}/scripts/templates"

python3 -m py_compile \
  "${INSTALLED_DIR}/scripts/repl_skin.py" \
  "${INSTALLED_DIR}/scripts/preview_bundle.py" \
  "${INSTALLED_DIR}/scripts/skill_generator.py"

if CURSOR_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh" >/dev/null 2>&1; then
  fail "installer overwrote an existing plugin without --force"
fi

MARKER="${INSTALLED_DIR}/.install-marker"
echo "first-install" > "${MARKER}"
CURSOR_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh" --force
[[ ! -f "${MARKER}" ]] || fail "--force upgrade did not replace the previous install"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"
assert_file "${INSTALLED_DIR}/PLUGIN_ROOT.txt"
STAMP2="$(tr -d '\r\n' < "${INSTALLED_DIR}/PLUGIN_ROOT.txt")"
[[ -n "${STAMP2}" ]] || fail "stamp after --force is empty"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"

grep -q 'cli-anything-generator.root' "${INSTALLED_DIR}/commands/cli-anything.md" ||
  fail "installed command does not document discovery pointer"
grep -q 'agent-harness/.cli-anything-progress.json' "${INSTALLED_DIR}/commands/cli-anything.md" ||
  fail "installed command does not use agent-harness progress path"
grep -q 'alwaysApply: false' "${INSTALLED_DIR}/rules/cli-anything-generator.mdc" ||
  fail "generator rule must be alwaysApply false (avoid global context pollution)"
grep -q 'agent-harness/\*\*' "${INSTALLED_DIR}/rules/cli-anything-generator.mdc" ||
  fail "generator rule must include agent-harness globs"
grep -q 'references/HARNESS.md' "${INSTALLED_DIR}/skills/cli-anything-generator/SKILL.md" ||
  fail "installed skill does not point to vendored HARNESS.md"
grep -q 'cli-hub-meta-skill' "${INSTALLED_DIR}/skills/cli-anything-generator/SKILL.md" ||
  fail "installed skill does not document consumer Hub path"

python3 - <<'PY' "${INSTALLED_DIR}/.cursor-plugin/plugin.json"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data.get("name") == "cli-anything", data
PY

MARKETPLACE="${REPO_ROOT}/.cursor-plugin/marketplace.json"
assert_file "${MARKETPLACE}"
python3 - <<'PY' "${MARKETPLACE}"
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
names = [p.get("name") for p in data.get("plugins", [])]
assert "cli-anything" in names, names
sources = [p.get("source") for p in data.get("plugins", [])]
assert "./cursor-plugin" in sources, sources
PY

DETACHED_ROOT="${TMP_DIR}/detached"
DETACHED_LOG="${TMP_DIR}/detached-install.log"
mkdir -p "${DETACHED_ROOT}"
cp -R "${PLUGIN_SRC}" "${DETACHED_ROOT}/cursor-plugin"
if CURSOR_PLUGINS_HOME="${TMP_DIR}/detached-plugins/plugins" bash "${DETACHED_ROOT}/cursor-plugin/scripts/install.sh" >"${DETACHED_LOG}" 2>&1; then
  fail "installer accepted a detached plugin without canonical resources"
fi
grep -q 'Cannot find canonical CLI-Anything resources' "${DETACHED_LOG}" ||
  fail "detached install did not explain the missing canonical resources"

BAD_HOME_LOG="${TMP_DIR}/bad-home.log"
BAD_HOME_PATH="${TMP_DIR}/not-plugins-dir"
if CURSOR_PLUGINS_HOME="${BAD_HOME_PATH}" bash "${PLUGIN_SRC}/scripts/install.sh" >"${BAD_HOME_LOG}" 2>&1; then
  fail "installer accepted CURSOR_PLUGINS_HOME whose basename is not plugins"
fi
grep -q "named 'plugins'" "${BAD_HOME_LOG}" ||
  fail "installer did not reject non-plugins CURSOR_PLUGINS_HOME"
[[ ! -e "${BAD_HOME_PATH}" ]] ||
  fail "rejected CURSOR_PLUGINS_HOME should not create the target directory"

TRAVERSAL_LOG="${TMP_DIR}/traversal.log"
TRAVERSAL_OUTSIDE="${TMP_DIR}/outside"
# After normalization this becomes TMP_DIR/outside (basename outside), not plugins.
if CURSOR_PLUGINS_HOME="${TMP_DIR}/evil/../outside" bash "${PLUGIN_SRC}/scripts/install.sh" >"${TRAVERSAL_LOG}" 2>&1; then
  fail "installer accepted traversed CURSOR_PLUGINS_HOME"
fi
grep -q "named 'plugins'" "${TRAVERSAL_LOG}" ||
  fail "installer did not reject traversed CURSOR_PLUGINS_HOME"
[[ ! -e "${TRAVERSAL_OUTSIDE}" ]] ||
  fail "rejected traversed CURSOR_PLUGINS_HOME should not create the outside directory"

# Uninstall clears install dir + matching discovery pointer.
CURSOR_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/uninstall.sh"
[[ ! -e "${INSTALLED_DIR}" ]] || fail "uninstall left plugin directory behind"
[[ ! -e "${DISCOVERY_POINTER}" ]] || fail "uninstall left discovery pointer behind"

# Reinstall, then foreign pointer must be preserved across uninstall.
CURSOR_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"
FOREIGN_ROOT="${TMP_DIR}/some-other-plugin-root"
printf '%s\n' "${FOREIGN_ROOT}" > "${DISCOVERY_POINTER}"
CURSOR_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/uninstall.sh"
[[ ! -e "${INSTALLED_DIR}" ]] || fail "uninstall left plugin directory behind after foreign-pointer case"
[[ -f "${DISCOVERY_POINTER}" ]] || fail "uninstall removed a non-matching discovery pointer"
LEFT_POINTER="$(tr -d '\r\n' < "${DISCOVERY_POINTER}")"
[[ "${LEFT_POINTER}" == "${FOREIGN_ROOT}" ]] ||
  fail "foreign discovery pointer changed: ${LEFT_POINTER}"

# Shared lib path helpers
# shellcheck source=../scripts/lib.sh
source "${PLUGIN_SRC}/scripts/lib.sh"
is_cli_anything_install_path "/tmp/foo/local/cli-anything" ||
  fail "is_cli_anything_install_path should accept .../local/cli-anything"
is_cli_anything_install_path 'C:\Users\x\.cursor\plugins\local\cli-anything' ||
  fail "is_cli_anything_install_path should accept Windows ...\\local\\cli-anything"
if is_cli_anything_install_path "/tmp/CLI-Anything/cursor-plugin"; then
  fail "is_cli_anything_install_path must reject repo cursor-plugin path"
fi

# Final reinstall for a clean installed tree at end of test.
CURSOR_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"
assert_file "${DISCOVERY_POINTER}"

echo "PASS: Cursor plugin installer vendors the complete CLI-Anything resource set."
