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
ORPHAN_NESTED="${SKILL_DIR}/references/guides/orphan-nested"
ORPHAN_FIXED="${SKILL_DIR}/references/docs/orphan-regression.md"
VENDORED_HARNESS="${SKILL_DIR}/references/HARNESS.md"
CANONICAL_HARNESS="${REPO_ROOT}/cli-anything-plugin/HARNESS.md"
VENDORED_GUIDE="${SKILL_DIR}/references/guides/session-locking.md"
CANONICAL_GUIDE="${REPO_ROOT}/cli-anything-plugin/guides/session-locking.md"

# Backups live outside the canonical source directories so the sync's
# wildcard mirroring cannot sweep them into the vendored bundle.
BACKUP_DIR="$(mktemp -d)"
cleanup() {
  rm -f "${ORPHAN}" "${ORPHAN_FIXED}"
  rm -rf "${ORPHAN_NESTED}"
  if [[ -f "${BACKUP_DIR}/HARNESS.md" ]] &&
    { [[ ! -f "${VENDORED_HARNESS}" ]] ||
      ! cmp -s "${BACKUP_DIR}/HARNESS.md" "${VENDORED_HARNESS}"; }; then
    cp "${BACKUP_DIR}/HARNESS.md" "${VENDORED_HARNESS}"
  fi
  if [[ -f "${BACKUP_DIR}/session-locking.md" ]]; then
    [[ -f "${CANONICAL_GUIDE}" ]] ||
      cp "${BACKUP_DIR}/session-locking.md" "${CANONICAL_GUIDE}"
    [[ -f "${VENDORED_GUIDE}" ]] ||
      cp "${BACKUP_DIR}/session-locking.md" "${VENDORED_GUIDE}"
  fi
  rm -rf "${BACKUP_DIR}"
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
cp "${VENDORED_HARNESS}" "${BACKUP_DIR}/HARNESS.md"
echo "drift" >> "${VENDORED_HARNESS}"
expect_validate_fail "out-of-sync vendored file not detected"
python3 "${SYNC}" >/dev/null
cmp -s "${VENDORED_HARNESS}" "${CANONICAL_HARNESS}" ||
  fail "sync did not restore drifted vendored file"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after restore"

# 3. Deleted canonical resource: sync removes the vendored copy.
cp "${CANONICAL_GUIDE}" "${BACKUP_DIR}/session-locking.md"
rm "${CANONICAL_GUIDE}"
python3 "${SYNC}" >/dev/null
[[ ! -e "${VENDORED_GUIDE}" ]] ||
  fail "sync kept vendored copy of deleted canonical resource"
cp "${BACKUP_DIR}/session-locking.md" "${CANONICAL_GUIDE}"
python3 "${SYNC}" >/dev/null
[[ -f "${VENDORED_GUIDE}" ]] || fail "sync did not restore deleted resource"
python3 "${VALIDATE}" >/dev/null || fail "final validation failed"

# 4. Nested orphan tree: validate fails, sync removes it recursively.
mkdir -p "${ORPHAN_NESTED}/old"
echo "stale" > "${ORPHAN_NESTED}/old/file.md"
expect_validate_fail "nested orphan tree not detected"
python3 "${SYNC}" >/dev/null
[[ ! -e "${ORPHAN_NESTED}" ]] || fail "sync did not remove nested orphan tree"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after nested orphan cleanup"

# 5. Stale fixed resource: validate fails, sync removes it.
echo "stale" > "${ORPHAN_FIXED}"
expect_validate_fail "stale fixed resource not detected"
python3 "${SYNC}" >/dev/null
[[ ! -e "${ORPHAN_FIXED}" ]] || fail "sync did not remove stale fixed resource"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after fixed cleanup"

echo "PASS: codex-skill sync and validation regression tests."
