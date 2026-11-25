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
ORPHAN_FIXED_NESTED="${SKILL_DIR}/references/docs/orphan-nested"
ORPHAN_LINK="${SKILL_DIR}/references/guides/orphan-link"
ORPHAN_DANGLING_LINK="${SKILL_DIR}/references/docs/orphan-dangling-link"
VENDORED_HARNESS="${SKILL_DIR}/references/HARNESS.md"
CANONICAL_HARNESS="${REPO_ROOT}/cli-anything-plugin/HARNESS.md"
VENDORED_GUIDE="${SKILL_DIR}/references/guides/session-locking.md"
CANONICAL_GUIDE="${REPO_ROOT}/cli-anything-plugin/guides/session-locking.md"

# Backups live outside the canonical source directories so the sync's
# wildcard mirroring cannot sweep them into the vendored bundle.
BACKUP_DIR="$(mktemp -d)"
cleanup() {
  # Restore the canonical guide first: sync requires it to be present.
  if [[ -f "${BACKUP_DIR}/session-locking.md" ]]; then
    if [[ -L "${CANONICAL_GUIDE}" || -d "${CANONICAL_GUIDE}" ]]; then
      rm -rf "${CANONICAL_GUIDE}"
    fi
    [[ -f "${CANONICAL_GUIDE}" ]] ||
      cp "${BACKUP_DIR}/session-locking.md" "${CANONICAL_GUIDE}"
  fi
  # Best-effort structural repair: clears conflicting path types, removes
  # orphans, and restores vendored copies from canonical sources.
  python3 "${SYNC}" >/dev/null 2>&1 || true
  # If a file still occupies an expected parent directory (sync broken),
  # clear it and retry once so the mirror can be rebuilt.
  if [[ -f "${SKILL_DIR}/references/docs" ]]; then
    rm -f "${SKILL_DIR}/references/docs"
    python3 "${SYNC}" >/dev/null 2>&1 || true
  fi
  # Restore the whole references tree independently of sync if a test left
  # it as a symlink or missing (the sync under test may itself be broken).
  if [[ -d "${BACKUP_DIR}/references" ]] &&
    { [[ -L "${SKILL_DIR}/references" ]] || [[ ! -d "${SKILL_DIR}/references" ]]; }; then
    rm -rf "${SKILL_DIR}/references"
    cp -R "${BACKUP_DIR}/references" "${SKILL_DIR}/references"
  fi
  # Belt-and-braces restores in case sync itself is broken or refused to run.
  rm -f "${ORPHAN}" "${ORPHAN_FIXED}" "${ORPHAN_LINK}" "${ORPHAN_DANGLING_LINK}" 2>/dev/null ||
    true
  rm -rf "${ORPHAN_NESTED}" "${ORPHAN_FIXED_NESTED}" 2>/dev/null || true
  if [[ -f "${BACKUP_DIR}/HARNESS.md" ]] &&
    { [[ -L "${VENDORED_HARNESS}" ]] ||
      [[ ! -f "${VENDORED_HARNESS}" ]] ||
      ! cmp -s "${BACKUP_DIR}/HARNESS.md" "${VENDORED_HARNESS}"; }; then
    [[ ! -L "${VENDORED_HARNESS}" ]] || rm -f "${VENDORED_HARNESS}"
    [[ ! -d "${VENDORED_HARNESS}" ]] || rm -rf "${VENDORED_HARNESS}"
    cp "${BACKUP_DIR}/HARNESS.md" "${VENDORED_HARNESS}"
  fi
  if [[ -f "${BACKUP_DIR}/session-locking.md" ]]; then
    if [[ -L "${VENDORED_GUIDE}" || -d "${VENDORED_GUIDE}" ]]; then
      rm -rf "${VENDORED_GUIDE}"
    fi
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

# 6. Nested stale fixed resource: validate fails, sync removes it recursively.
mkdir -p "${ORPHAN_FIXED_NESTED}/old"
echo "stale" > "${ORPHAN_FIXED_NESTED}/old/file.md"
expect_validate_fail "nested stale fixed resource not detected"
python3 "${SYNC}" >/dev/null
[[ ! -e "${ORPHAN_FIXED_NESTED}" ]] ||
  fail "sync did not remove nested stale fixed resource"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after nested fixed cleanup"

# 7. Orphaned directory symlink: validate fails, sync removes the link.
ln -s /tmp "${ORPHAN_LINK}"
expect_validate_fail "orphaned directory symlink not detected"
python3 "${SYNC}" >/dev/null
[[ ! -e "${ORPHAN_LINK}" && ! -L "${ORPHAN_LINK}" ]] ||
  fail "sync did not remove orphaned directory symlink"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after symlink cleanup"

# 8. Dangling symlink under a fixed parent: validate fails, sync removes it.
ln -s /nonexistent "${ORPHAN_DANGLING_LINK}"
expect_validate_fail "dangling symlink not detected"
python3 "${SYNC}" >/dev/null
[[ ! -e "${ORPHAN_DANGLING_LINK}" && ! -L "${ORPHAN_DANGLING_LINK}" ]] ||
  fail "sync did not remove dangling symlink"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after dangling link cleanup"

# 9. Symlinked mapped destination: validate fails, sync restores a real copy.
rm -f "${VENDORED_HARNESS}"
ln -s "${CANONICAL_HARNESS}" "${VENDORED_HARNESS}"
expect_validate_fail "symlinked mapped destination not detected"
python3 "${SYNC}" >/dev/null
[[ ! -L "${VENDORED_HARNESS}" ]] ||
  fail "sync did not replace symlinked mapped destination"
cmp -s "${VENDORED_HARNESS}" "${CANONICAL_HARNESS}" ||
  fail "sync did not restore vendored copy at symlinked destination"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after symlink restore"

# 10. Directory at a mapped destination: validate fails, sync repairs.
rm -f "${VENDORED_HARNESS}"
mkdir -p "${VENDORED_HARNESS}/old"
echo "stale" > "${VENDORED_HARNESS}/old/file.md"
expect_validate_fail "directory at mapped destination not detected"
python3 "${SYNC}" >/dev/null
[[ -f "${VENDORED_HARNESS}" && ! -d "${VENDORED_HARNESS}" ]] ||
  fail "sync did not replace directory at mapped destination"
cmp -s "${VENDORED_HARNESS}" "${CANONICAL_HARNESS}" ||
  fail "sync did not restore correct content at mapped destination"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after dir repair"

# 11. Regular file at an expected parent directory: sync repairs.
cp -R "${SKILL_DIR}/references" "${BACKUP_DIR}/references"
rm -rf "${SKILL_DIR}/references/docs"
echo "stale" > "${SKILL_DIR}/references/docs"
expect_validate_fail "file at expected parent directory not detected"
python3 "${SYNC}" >/dev/null
[[ -d "${SKILL_DIR}/references/docs" ]] ||
  fail "sync did not replace file at expected parent directory"
[[ -f "${SKILL_DIR}/references/docs/PREVIEW_PROTOCOL.md" ]] ||
  fail "sync did not restore resources under repaired parent"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after parent repair"

# 12. Symlinked references directory: sync must not escape codex-skill/.
rm -rf "${SKILL_DIR}/references"
ln -s "${REPO_ROOT}/cli-anything-plugin" "${SKILL_DIR}/references"
python3 "${SYNC}" >/dev/null
[[ ! -L "${SKILL_DIR}/references" ]] ||
  fail "sync did not replace symlinked references directory"
[[ -f "${CANONICAL_HARNESS}" ]] ||
  fail "sync deleted a canonical source through a symlinked ancestor"
[[ -f "${SKILL_DIR}/references/HARNESS.md" ]] ||
  fail "sync did not restore resources under the replaced directory"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after symlinked ancestor repair"

# 13. Symlinked DIR_MAP root: validate fails, sync replaces with a real dir.
rm -rf "${SKILL_DIR}/references/guides"
ln -s "${REPO_ROOT}/cli-anything-plugin/guides" "${SKILL_DIR}/references/guides"
expect_validate_fail "symlinked DIR_MAP root not detected"
python3 "${SYNC}" >/dev/null
[[ ! -L "${SKILL_DIR}/references/guides" ]] ||
  fail "sync did not replace symlinked DIR_MAP root"
[[ -f "${SKILL_DIR}/references/guides/session-locking.md" ]] ||
  fail "sync did not restore resources under symlinked DIR_MAP root"
[[ -f "${REPO_ROOT}/cli-anything-plugin/guides/session-locking.md" ]] ||
  fail "sync touched canonical sources through symlinked DIR_MAP root"
python3 "${VALIDATE}" >/dev/null || fail "validation failed after DIR_MAP root repair"

echo "PASS: codex-skill sync and validation regression tests."
