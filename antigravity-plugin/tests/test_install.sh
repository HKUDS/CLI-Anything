#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PLUGIN_SRC}/.." && pwd)"
CANONICAL_PLUGIN="${REPO_ROOT}/cli-anything-plugin"
TMP_DIR="$(mktemp -d)"
export HOME="${TMP_DIR}/home"
mkdir -p "${HOME}"
PLUGINS_HOME="${TMP_DIR}/plugins"
INSTALLED_DIR="${PLUGINS_HOME}/cli-anything"
STALE_STAGING_DIR="${PLUGINS_HOME}/.cli-anything.tmp.stale"
DISCOVERY_POINTER="${HOME}/.gemini/cli-anything-generator.root"
WORKSPACE_DIR="${TMP_DIR}/sample-workspace"
WS_INSTALLED_DIR="${WORKSPACE_DIR}/.agents/plugins/cli-anything"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

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

[[ -n "${PYTHON_BIN}" ]] || fail "python3/python not available"

mkdir -p "${WORKSPACE_DIR}"

# 1. Dry-run must validate without creating destination or pointer.
DRY_PLUGINS="${TMP_DIR}/dry-root/plugins"
ANTIGRAVITY_PLUGINS_HOME="${DRY_PLUGINS}" bash "${PLUGIN_SRC}/scripts/install.sh" --dry-run >/dev/null
[[ ! -e "${DRY_PLUGINS}" ]] || fail "--dry-run created plugins directory"
[[ ! -e "${DISCOVERY_POINTER}" ]] || fail "--dry-run created discovery pointer"

mkdir -p "${STALE_STAGING_DIR}"
echo "left over from an interrupted install" > "${STALE_STAGING_DIR}/stale.txt"

# 2. Full global install
ANTIGRAVITY_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh"

assert_file "${INSTALLED_DIR}/plugin.json"
assert_file "${INSTALLED_DIR}/README.md"
assert_file "${INSTALLED_DIR}/PLUGIN_ROOT.txt"
assert_file "${INSTALLED_DIR}/assets/logo.svg"
assert_file "${INSTALLED_DIR}/hooks.json"
assert_file "${INSTALLED_DIR}/rules/cli-anything-generator.md"
assert_file "${INSTALLED_DIR}/agents/cli-anything-auditor.md"
assert_file "${DISCOVERY_POINTER}"
for skill in cli-anything cli-anything-refine cli-anything-test cli-anything-validate cli-anything-list; do
  assert_file "${INSTALLED_DIR}/skills/${skill}/SKILL.md"
done
assert_file "${INSTALLED_DIR}/references/antigravity-tooling.md"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"
assert_file "${INSTALLED_DIR}/references/commands/cli-anything.md"
assert_file "${INSTALLED_DIR}/references/commands/refine.md"
assert_file "${INSTALLED_DIR}/references/commands/test.md"
assert_file "${INSTALLED_DIR}/references/commands/validate.md"
assert_file "${INSTALLED_DIR}/references/commands/list.md"
assert_file "${INSTALLED_DIR}/references/guides/auto-save-dry-run.md"
assert_file "${INSTALLED_DIR}/references/guides/session-locking.md"
assert_file "${INSTALLED_DIR}/references/guides/preview-methodology.md"
assert_file "${INSTALLED_DIR}/references/docs/PREVIEW_PROTOCOL.md"
assert_file "${INSTALLED_DIR}/scripts/repl_skin.py"
assert_file "${INSTALLED_DIR}/scripts/preview_bundle.py"
assert_file "${INSTALLED_DIR}/scripts/skill_generator.py"
assert_file "${INSTALLED_DIR}/scripts/verify_harness.py"
assert_file "${INSTALLED_DIR}/scripts/list_harnesses.py"
assert_file "${INSTALLED_DIR}/scripts/pep420_guard.py"
assert_file "${INSTALLED_DIR}/scripts/templates/SKILL.md.template"
assert_file "${INSTALLED_DIR}/scripts/install.sh"
assert_file "${INSTALLED_DIR}/scripts/install.ps1"
assert_file "${INSTALLED_DIR}/scripts/uninstall.sh"
assert_file "${INSTALLED_DIR}/scripts/uninstall.ps1"
assert_file "${INSTALLED_DIR}/scripts/lib.sh"
assert_file "${INSTALLED_DIR}/scripts/lib.ps1"

[[ ! -e "${PLUGINS_HOME}/.cli-anything.lock" ]] || fail "stale lock directory remained after install"

STAMP="$(tr -d '\r\n' < "${INSTALLED_DIR}/PLUGIN_ROOT.txt")"
POINTER="$(tr -d '\r\n' < "${DISCOVERY_POINTER}")"
[[ -n "${STAMP}" ]] || fail "PLUGIN_ROOT.txt is empty"
[[ "${STAMP}" == "${POINTER}" ]] || fail "discovery pointer mismatch: ${POINTER} != ${STAMP}"

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
[[ ! -d "${INSTALLED_DIR}/antigravity-plugin" ]] ||
  fail "installer created a nested antigravity-plugin directory"
[[ ! -e "${INSTALLED_DIR}/rules/AGENTS.md" ]] ||
  fail "generator plugin must not ship always-on rules/AGENTS.md"

# 3. Byte-for-byte parity with canonical upstream resources
assert_same "${CANONICAL_PLUGIN}/HARNESS.md" "${INSTALLED_DIR}/references/HARNESS.md"
assert_same "${CANONICAL_PLUGIN}/repl_skin.py" "${INSTALLED_DIR}/scripts/repl_skin.py"
assert_same "${CANONICAL_PLUGIN}/preview_bundle.py" "${INSTALLED_DIR}/scripts/preview_bundle.py"
assert_same "${CANONICAL_PLUGIN}/skill_generator.py" "${INSTALLED_DIR}/scripts/skill_generator.py"
assert_same "${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md" "${INSTALLED_DIR}/references/docs/PREVIEW_PROTOCOL.md"
assert_same "${PLUGIN_SRC}/references/antigravity-tooling.md" "${INSTALLED_DIR}/references/antigravity-tooling.md"
assert_tree_same "${CANONICAL_PLUGIN}/commands" "${INSTALLED_DIR}/references/commands"
assert_tree_same "${CANONICAL_PLUGIN}/guides" "${INSTALLED_DIR}/references/guides"
assert_tree_same "${CANONICAL_PLUGIN}/templates" "${INSTALLED_DIR}/scripts/templates"

"${PYTHON_BIN}" -B -m py_compile \
  "${INSTALLED_DIR}/scripts/repl_skin.py" \
  "${INSTALLED_DIR}/scripts/preview_bundle.py" \
  "${INSTALLED_DIR}/scripts/skill_generator.py" \
  "${INSTALLED_DIR}/scripts/verify_harness.py" \
  "${INSTALLED_DIR}/scripts/list_harnesses.py" \
  "${INSTALLED_DIR}/scripts/pep420_guard.py"

# 4. Validate plugin.json, skills frontmatter, rule globs, agent frontmatter, and hooks.json
"${PYTHON_BIN}" - <<'PY' "${INSTALLED_DIR}"
import json, os, re, sys
root = sys.argv[1]

manifest = json.load(open(os.path.join(root, "plugin.json"), encoding="utf-8"))
allowed = {
    "$schema", "name", "displayName", "version", "description", "author",
    "homepage", "repository", "logo", "suggestedPrompts", "disabled",
    "license", "keywords", "skills", "extensions",
}
unknown = set(manifest.keys()) - allowed
assert not unknown, f"Unknown plugin.json fields: {unknown}"
assert manifest.get("name") == "cli-anything", manifest
assert manifest.get("$schema") == "https://antigravity.google/schemas/v1/plugin.json", manifest
assert manifest.get("license") == "Apache-2.0", manifest
assert isinstance(manifest.get("keywords"), list) and len(manifest["keywords"]) >= 3, manifest
assert isinstance(manifest.get("suggestedPrompts"), list) and len(manifest["suggestedPrompts"]) == 3, manifest
assert os.path.isfile(os.path.join(root, manifest["logo"])), manifest["logo"]

expected_skills = [
    "cli-anything", "cli-anything-refine", "cli-anything-test",
    "cli-anything-validate", "cli-anything-list",
]
for sk in expected_skills:
    text = open(os.path.join(root, "skills", sk, "SKILL.md"), encoding="utf-8").read()
    m = re.search(r"(?m)^name:\s*(\S+)\s*$", text)
    assert m and m.group(1) == sk, f"Skill folder/frontmatter mismatch for {sk}"

rule_text = open(os.path.join(root, "rules", "cli-anything-generator.md"), encoding="utf-8").read()
assert "trigger: glob" in rule_text, "rule must use trigger: glob"
assert re.search(r'(?m)^globs:\s*"[^"]*agent-harness/\*\*', rule_text), "rule globs must be comma-separated string"

agent_text = open(os.path.join(root, "agents", "cli-anything-auditor.md"), encoding="utf-8").read()
assert "name: cli-anything-auditor" in agent_text
assert "subagent: true" in agent_text

hooks = json.load(open(os.path.join(root, "hooks.json"), encoding="utf-8"))
guard = hooks["pep420-namespace-guard"]
assert guard["enabled"] is False
assert guard["PreToolUse"][0]["matcher"] == "write_file"
assert "./scripts/pep420_guard.py" in guard["PreToolUse"][0]["hooks"][0]["command"]
PY

# 5. Live execution check of installed scripts (also works without PLUGIN_ROOT.txt, simulating `agy plugin install`)
rm -f "${INSTALLED_DIR}/PLUGIN_ROOT.txt"
if [[ -d "${REPO_ROOT}/gimp/agent-harness" ]]; then
  "${PYTHON_BIN}" "${INSTALLED_DIR}/scripts/verify_harness.py" "${REPO_ROOT}/gimp" --json >/dev/null
fi
"${PYTHON_BIN}" "${INSTALLED_DIR}/scripts/list_harnesses.py" --path "${REPO_ROOT}" --depth 1 --json >/dev/null

# 6. Refuses overwrite without --force; atomic upgrade with --force
if ANTIGRAVITY_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh" >/dev/null 2>&1; then
  fail "installer overwrote an existing plugin without --force"
fi

MARKER="${INSTALLED_DIR}/.install-marker"
echo "first-install" > "${MARKER}"
ANTIGRAVITY_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh" --force
[[ ! -f "${MARKER}" ]] || fail "--force upgrade did not replace the previous install"
assert_file "${INSTALLED_DIR}/PLUGIN_ROOT.txt"

# 7. Workspace-scoped install must not clobber global discovery pointer
bash "${PLUGIN_SRC}/scripts/install.sh" --workspace "${WORKSPACE_DIR}"
assert_file "${WS_INSTALLED_DIR}/plugin.json"
assert_file "${WS_INSTALLED_DIR}/references/HARNESS.md"
assert_file "${WS_INSTALLED_DIR}/scripts/verify_harness.py"
POINTER_AFTER_WS="$(tr -d '\r\n' < "${DISCOVERY_POINTER}")"
[[ "${POINTER_AFTER_WS}" == "${STAMP}" ]] ||
  fail "workspace install overwrote global discovery pointer: ${POINTER_AFTER_WS}"

bash "${PLUGIN_SRC}/scripts/uninstall.sh" --workspace "${WORKSPACE_DIR}"
[[ ! -e "${WS_INSTALLED_DIR}" ]] || fail "workspace uninstall left plugin directory behind"
[[ -f "${DISCOVERY_POINTER}" ]] || fail "workspace uninstall removed global discovery pointer"

# 8. Detached and invalid/traversal path rejection
DETACHED_ROOT="${TMP_DIR}/detached"
DETACHED_LOG="${TMP_DIR}/detached-install.log"
mkdir -p "${DETACHED_ROOT}"
cp -R "${PLUGIN_SRC}" "${DETACHED_ROOT}/antigravity-plugin"
if ANTIGRAVITY_PLUGINS_HOME="${TMP_DIR}/detached-plugins/plugins" bash "${DETACHED_ROOT}/antigravity-plugin/scripts/install.sh" >"${DETACHED_LOG}" 2>&1; then
  fail "installer accepted a detached plugin without canonical resources"
fi
grep -q 'Cannot find canonical CLI-Anything resources' "${DETACHED_LOG}" ||
  fail "detached install did not explain missing canonical resources"

BAD_HOME_PATH="${TMP_DIR}/not-plugins-dir"
if ANTIGRAVITY_PLUGINS_HOME="${BAD_HOME_PATH}" bash "${PLUGIN_SRC}/scripts/install.sh" >/dev/null 2>&1; then
  fail "installer accepted non-plugins ANTIGRAVITY_PLUGINS_HOME"
fi
[[ ! -e "${BAD_HOME_PATH}" ]] || fail "rejected ANTIGRAVITY_PLUGINS_HOME created directory"

TRAVERSAL_OUTSIDE="${TMP_DIR}/outside"
if ANTIGRAVITY_PLUGINS_HOME="${TMP_DIR}/evil/../outside" bash "${PLUGIN_SRC}/scripts/install.sh" >/dev/null 2>&1; then
  fail "installer accepted traversed ANTIGRAVITY_PLUGINS_HOME"
fi
[[ ! -e "${TRAVERSAL_OUTSIDE}" ]] || fail "rejected traversed ANTIGRAVITY_PLUGINS_HOME created directory"

# 9. Uninstall clears install dir + matching pointer; preserves foreign pointer
ANTIGRAVITY_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/uninstall.sh"
[[ ! -e "${INSTALLED_DIR}" ]] || fail "uninstall left plugin directory behind"
[[ ! -e "${DISCOVERY_POINTER}" ]] || fail "uninstall left discovery pointer behind"

ANTIGRAVITY_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/install.sh"
FOREIGN_ROOT="${TMP_DIR}/some-other-plugin-root"
printf '%s\n' "${FOREIGN_ROOT}" > "${DISCOVERY_POINTER}"
ANTIGRAVITY_PLUGINS_HOME="${PLUGINS_HOME}" bash "${PLUGIN_SRC}/scripts/uninstall.sh"
[[ ! -e "${INSTALLED_DIR}" ]] || fail "uninstall left plugin dir after foreign-pointer case"
[[ "$(tr -d '\r\n' < "${DISCOVERY_POINTER}")" == "${FOREIGN_ROOT}" ]] ||
  fail "foreign discovery pointer changed"

# 10. Shared lib helpers
# shellcheck source=../scripts/lib.sh
source "${PLUGIN_SRC}/scripts/lib.sh"
is_cli_anything_install_path "/home/user/.gemini/config/plugins/cli-anything" || fail "rejected unix global path"
is_cli_anything_install_path 'C:\Users\x\.gemini\config\plugins\cli-anything' || fail "rejected windows global path"
is_cli_anything_install_path "/work/repo/.agents/plugins/cli-anything" || fail "rejected workspace path"
if is_cli_anything_install_path "/tmp/CLI-Anything/antigravity-plugin"; then
  fail "must reject repo antigravity-plugin path"
fi

echo "PASS: Antigravity plugin installer, components, and scripts verified."
