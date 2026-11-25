#!/usr/bin/env bash
# Regression tests for codex-skill vendored resource sync and validation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SKILL_DIR}/.." && pwd)"
SYNC="${REPO_ROOT}/.github/scripts/sync_codex_skill.py"
VALIDATE="${REPO_ROOT}/.github/scripts/validate_codex_skill.py"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

ORPHAN="${SKILL_DIR}/references/guides/orphan-regression.md"
VENDORED_HARNESS="${SKILL_DIR}/references/HARNESS.md"
CANONICAL_HARNESS="${REPO_ROOT}/cli-anything-plugin/HARNESS.md"
VENDORED_GUIDE="${SKILL_DIR}/references/guides/session-locking.md"
CANONICAL_GUIDE="${REPO_ROOT}/cli-anything-plugin/guides/session-locking.md"

cleanup() {
  rm -f "${ORPHAN}" "${VENDORED_HARNESS}.bak"
  if [[ -f "${CANONICAL_GUIDE}.bak" && ! -f "${CANONICAL_GUIDE}" ]]; then
    mv "${CANONICAL_GUIDE}.bak" "${CANONICAL_GUIDE}"
  else
    rm -f "${CANONICAL_GUIDE}.bak"
  fi
}
trap cleanup EXIT

# validate must fail when the mirror is inconsistent
expect_validate_fail() {
  if python3 "${VALIDATE}" >/dev/null 2>&1; then
    fail "validate unexpectedly passed: $1"
  fi
}

python3 "${SYNC}" >/dev/null
python3 "${VALIDATE}" >/dev/null || fail "clean tree failed validation"

# 1. Orphaned vendored file: validate fails, sync removes it, validate passes.
echo "stale" > "${ORPHAN}"
expect_validate_fail "orphaned vendored file not detected"
python3 "${SYNC}" >/dev/null
[[ ! -e "${ORPHAN}" ]] || fail "sync did not remove orphaned vendored file"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after orphan cleanup"

# 2. Out-of-sync vendored file: validate fails, sync restores it.
cp "${VENDORED_HARNESS}" "${VENDORED_HARNESS}.bak"
echo "drift" >> "${VENDORED_HARNESS}"
expect_validate_fail "out-of-sync vendored file not detected"
python3 "${SYNC}" >/dev/null
cmp -s "${VENDORED_HARNESS}" "${CANONICAL_HARNESS}" ||
  fail "sync did not restore drifted vendored file"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after restore"
rm -f "${VENDORED_HARNESS}.bak"

# 3. Deleted canonical resource: sync removes the vendored copy.
cp "${CANONICAL_GUIDE}" "${CANONICAL_GUIDE}.bak"
rm "${CANONICAL_GUIDE}"
python3 "${SYNC}" >/dev/null
[[ ! -e "${VENDORED_GUIDE}" ]] ||
  fail "sync kept vendored copy of deleted canonical resource"
mv "${CANONICAL_GUIDE}.bak" "${CANONICAL_GUIDE}"
python3 "${SYNC}" >/dev/null
[[ -f "${VENDORED_GUIDE}" ]] || fail "sync did not restore deleted resource"
python3 "${VALIDATE}" >/dev/null || fail "final validation failed"

echo "PASS: codex-skill sync and validation regression tests."
