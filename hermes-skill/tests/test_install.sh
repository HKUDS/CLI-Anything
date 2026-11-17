#!/usr/bin/env bash
#
# End-to-end test for hermes-skill/scripts/install.sh.
#
# Asserts that the installer vendors the complete canonical resource set, is
# atomic, refuses to clobber without --force, supports HERMES_HOME and
# --profile, honours --dry-run, and fails with a useful message when run
# detached from a repository checkout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/.." && pwd)"
PLUGIN_DIR="${REPO_ROOT}/cli-anything-plugin"
TMP_DIR="$(mktemp -d)"
HERMES_ROOT="${TMP_DIR}/hermes-home"
INSTALLED_DIR="${HERMES_ROOT}/skills/cli-anything-hermes"
STALE_STAGING_DIR="${HERMES_ROOT}/skills/.cli-anything-hermes.tmp.stale"

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

assert_absent() {
  [[ ! -e "$1" ]] || fail "expected path to be absent: $1"
}

assert_same() {
  cmp -s "$1" "$2" || fail "files differ: $1 $2"
}

assert_tree_same() {
  diff -qr "$1" "$2" >/dev/null || fail "directories differ: $1 $2"
}

# A relocatable copy of the skill, detached from any repository checkout.
DETACHED_ROOT="${TMP_DIR}/detached"
mkdir -p "${DETACHED_ROOT}"
cp -R "${SKILL_DIR}" "${DETACHED_ROOT}/hermes-skill"

# A stale staging directory from an interrupted install must survive untouched.
mkdir -p "${STALE_STAGING_DIR}/hermes-skill"
echo "left over from an interrupted install" > "${STALE_STAGING_DIR}/hermes-skill/stale.txt"

# --dry-run writes nothing.
HERMES_HOME="${HERMES_ROOT}" bash "${SKILL_DIR}/scripts/install.sh" --dry-run >/dev/null
assert_absent "${INSTALLED_DIR}"

# A detached checkout cannot vendor the methodology and must say so.
if HERMES_HOME="${TMP_DIR}/detached-home" bash "${DETACHED_ROOT}/hermes-skill/scripts/install.sh" \
  >"${TMP_DIR}/detached.log" 2>&1; then
  fail "installer accepted a detached skill without canonical resources"
fi
grep -q 'cannot find canonical CLI-Anything resources' "${TMP_DIR}/detached.log" ||
  fail "detached install did not explain the missing canonical resources"

# The real install.
HERMES_HOME="${HERMES_ROOT}" bash "${SKILL_DIR}/scripts/install.sh"

assert_file "${INSTALLED_DIR}/SKILL.md"
assert_file "${INSTALLED_DIR}/agents/hermes.yaml"
assert_file "${INSTALLED_DIR}/references/HARNESS.md"
assert_file "${INSTALLED_DIR}/references/hermes-tooling.md"
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
assert_file "${INSTALLED_DIR}/scripts/templates/SKILL.md.template"

[[ -d "${STALE_STAGING_DIR}" ]] ||
  fail "installer reused or removed the stale staging directory"
[[ ! -d "${INSTALLED_DIR}/hermes-skill" ]] ||
  fail "installer created a nested hermes-skill directory"

assert_same "${PLUGIN_DIR}/HARNESS.md" "${INSTALLED_DIR}/references/HARNESS.md"
assert_same "${PLUGIN_DIR}/repl_skin.py" "${INSTALLED_DIR}/scripts/repl_skin.py"
assert_same "${PLUGIN_DIR}/preview_bundle.py" "${INSTALLED_DIR}/scripts/preview_bundle.py"
assert_same "${PLUGIN_DIR}/skill_generator.py" "${INSTALLED_DIR}/scripts/skill_generator.py"
assert_same "${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md" "${INSTALLED_DIR}/references/docs/PREVIEW_PROTOCOL.md"
assert_tree_same "${PLUGIN_DIR}/commands" "${INSTALLED_DIR}/references/commands"
assert_tree_same "${PLUGIN_DIR}/guides" "${INSTALLED_DIR}/references/guides"
assert_tree_same "${PLUGIN_DIR}/templates" "${INSTALLED_DIR}/scripts/templates"

grep -q 'references/HARNESS.md' "${INSTALLED_DIR}/SKILL.md" ||
  fail "installed SKILL.md does not point to the vendored HARNESS.md"

# Frontmatter must match the skill name Hermes will index, with a short
# description (Hermes clips long descriptions in its skill index).
python3 - "${INSTALLED_DIR}/SKILL.md" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
assert text.startswith("---"), "SKILL.md must start with frontmatter"
end = text.find("\n---", 3)
assert end != -1, "frontmatter must close"
frontmatter = text[3:end]
name = re.search(r"^name:\s*(\S+)", frontmatter, re.MULTILINE)
description = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
assert name and name.group(1).strip('"\'') == "cli-anything-hermes", "unexpected skill name"
assert description, "frontmatter needs a description"
value = description.group(1).strip().strip('"\'')
assert len(value) <= 60, "description is %d chars; Hermes clips above 60" % len(value)
PY

# The installed verifier must run standalone and reject a broken target.
python3 "${INSTALLED_DIR}/scripts/verify_harness.py" --help >/dev/null
if python3 "${INSTALLED_DIR}/scripts/verify_harness.py" "${TMP_DIR}/not-a-harness" \
  >"${TMP_DIR}/verify.log" 2>&1; then
  fail "verifier accepted a directory that is not a harness"
fi

# Reinstalling without --force must fail; with --force it must replace.
if HERMES_HOME="${HERMES_ROOT}" bash "${SKILL_DIR}/scripts/install.sh" >/dev/null 2>&1; then
  fail "installer overwrote an existing skill without --force"
fi
echo "stale" > "${INSTALLED_DIR}/stale-marker.txt"
HERMES_HOME="${HERMES_ROOT}" bash "${SKILL_DIR}/scripts/install.sh" --force >/dev/null
assert_absent "${INSTALLED_DIR}/stale-marker.txt"
assert_file "${INSTALLED_DIR}/SKILL.md"

# --profile installs into the profile's skill tree.
PROFILE_DIR="${HERMES_ROOT}/profiles/research/skills/cli-anything-hermes"
HERMES_HOME="${HERMES_ROOT}" bash "${SKILL_DIR}/scripts/install.sh" --profile research >/dev/null
assert_file "${PROFILE_DIR}/SKILL.md"
assert_file "${PROFILE_DIR}/references/HARNESS.md"

echo "PASS: Hermes skill installer vendors the complete CLI-Anything resource set."
