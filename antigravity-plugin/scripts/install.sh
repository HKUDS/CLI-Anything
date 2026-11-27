#!/usr/bin/env bash

set -euo pipefail

FORCE=0
DRY_RUN=0
WORKSPACE_PATH=""

while [[ $# -gt 0 ]]; do
  case "${1}" in
    --force|-f)
      FORCE=1
      shift
      ;;
    --dry-run|-n)
      DRY_RUN=1
      shift
      ;;
    --workspace|-w)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for ${1}" >&2
        exit 2
      fi
      WORKSPACE_PATH="${2}"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [--force] [--dry-run] [--workspace <path>]"
      echo "Install the CLI-Anything Google Antigravity plugin with vendored methodology resources."
      echo "Global destination:    \${ANTIGRAVITY_PLUGINS_HOME:-~/.gemini/config/plugins}/cli-anything"
      echo "Workspace destination: <workspace>/.agents/plugins/cli-anything"
      exit 0
      ;;
    *)
      echo "Unknown argument: ${1}" >&2
      echo "Usage: $0 [--force] [--dry-run] [--workspace <path>]" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

PLUGIN_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${PLUGIN_SRC}/.." && pwd)"
CANONICAL_PLUGIN="${REPO_ROOT}/cli-anything-plugin"
PREVIEW_PROTOCOL="${REPO_ROOT}/docs/PREVIEW_PROTOCOL.md"

if [[ ! -f "${CANONICAL_PLUGIN}/HARNESS.md" ]]; then
  echo "Cannot find canonical CLI-Anything resources at: ${CANONICAL_PLUGIN}" >&2
  echo "Run this installer from a full CLI-Anything repository checkout." >&2
  exit 1
fi

if [[ ! -f "${PREVIEW_PROTOCOL}" ]]; then
  echo "Cannot find preview protocol at: ${PREVIEW_PROTOCOL}" >&2
  echo "Run this installer from a full CLI-Anything repository checkout." >&2
  exit 1
fi

if [[ ! -f "${PLUGIN_SRC}/plugin.json" ]]; then
  echo "Cannot find Antigravity plugin manifest at: ${PLUGIN_SRC}/plugin.json" >&2
  exit 1
fi

IS_GLOBAL=1
if [[ -n "${WORKSPACE_PATH}" ]]; then
  IS_GLOBAL=0
  WS_ROOT="$(resolve_workspace_root "${WORKSPACE_PATH}")"
  PLUGINS_HOME="${WS_ROOT}/.agents/plugins"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    mkdir -p "${PLUGINS_HOME}"
  fi
else
  CREATE_MODE="create"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    CREATE_MODE=""
  fi
  if [[ -n "${ANTIGRAVITY_PLUGINS_HOME:-}" ]]; then
    PLUGINS_HOME="$(resolve_plugins_home "${ANTIGRAVITY_PLUGINS_HOME}" "${CREATE_MODE}")"
  else
    PLUGINS_HOME="$(resolve_plugins_home "${HOME}/.gemini/config/plugins" "${CREATE_MODE}")"
  fi
fi

DEST_DIR="${PLUGINS_HOME}/cli-anything"
DISCOVERY_POINTER="$(discovery_pointer_path)"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[dry-run] Source adapter:     ${PLUGIN_SRC}"
  echo "[dry-run] Canonical plugin:   ${CANONICAL_PLUGIN}"
  echo "[dry-run] Preview protocol:   ${PREVIEW_PROTOCOL}"
  echo "[dry-run] Destination:        ${DEST_DIR}"
  if [[ "${IS_GLOBAL}" -eq 1 ]]; then
    echo "[dry-run] Discovery pointer:  ${DISCOVERY_POINTER}"
  else
    echo "[dry-run] Discovery pointer:  (unchanged for workspace install)"
  fi
  if [[ -e "${DEST_DIR}" && "${FORCE}" -ne 1 ]]; then
    echo "[dry-run] Note: destination exists; real run would require --force."
  fi
  exit 0
fi

LOCK_PATH="${PLUGINS_HOME}/.cli-anything.lock"
LOCK_HELD=0
STAGING_DIR=""
MAIN_PID="${BASHPID:-$$}"

cleanup() {
  if [[ "${BASHPID:-$$}" != "${MAIN_PID}" ]]; then
    return 0
  fi
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf "${STAGING_DIR}"
  fi
  if [[ "${LOCK_HELD}" -eq 1 ]]; then
    release_install_lock "${LOCK_PATH}"
  fi
}
trap cleanup EXIT

acquire_install_lock "${LOCK_PATH}"
LOCK_HELD=1

if [[ -e "${DEST_DIR}" && "${FORCE}" -ne 1 ]]; then
  echo "Refusing to overwrite existing plugin: ${DEST_DIR}" >&2
  echo "Re-run with --force to upgrade, or remove it manually." >&2
  exit 1
fi

STAGING_DIR="$(mktemp -d "${PLUGINS_HOME}/.cli-anything.tmp.XXXXXX")"
LOCK_KEY="$(normalize_path_key "$(resolve_real_path "${LOCK_PATH}")")"
STAGING_KEY="$(normalize_path_key "$(resolve_real_path "${STAGING_DIR}")")"
DEST_KEY="$(normalize_path_key "$(resolve_real_path "${DEST_DIR}")")"

# Copy adapter package (exclude tests, .git, .agents, staging/dest subtrees, and references/ which is assembled cleanly below).
while IFS= read -r -d '' entry; do
  base="$(basename "${entry}")"
  case "${base}" in
    tests|references|.git|.agents|__pycache__)
      continue
      ;;
  esac
  entry_key="$(normalize_path_key "$(resolve_real_path "${entry}")")"
  if [[ "${STAGING_KEY}" == "${entry_key}" || "${STAGING_KEY}" == "${entry_key}/"* || "${DEST_KEY}" == "${entry_key}" || "${DEST_KEY}" == "${entry_key}/"* || "${LOCK_KEY}" == "${entry_key}" || "${LOCK_KEY}" == "${entry_key}/"* ]]; then
    continue
  fi
  cp -R "${entry}" "${STAGING_DIR}/"
done < <(find "${PLUGIN_SRC}" -mindepth 1 -maxdepth 1 -print0)

mkdir -p \
  "${STAGING_DIR}/references/commands" \
  "${STAGING_DIR}/references/docs" \
  "${STAGING_DIR}/references/guides" \
  "${STAGING_DIR}/scripts/templates"

if [[ -f "${PLUGIN_SRC}/references/antigravity-tooling.md" ]]; then
  cp "${PLUGIN_SRC}/references/antigravity-tooling.md" "${STAGING_DIR}/references/antigravity-tooling.md"
fi

cp "${CANONICAL_PLUGIN}/HARNESS.md" "${STAGING_DIR}/references/HARNESS.md"
cp "${CANONICAL_PLUGIN}/commands/"*.md "${STAGING_DIR}/references/commands/"
cp "${CANONICAL_PLUGIN}/guides/"*.md "${STAGING_DIR}/references/guides/"
cp "${CANONICAL_PLUGIN}/repl_skin.py" "${STAGING_DIR}/scripts/repl_skin.py"
cp "${CANONICAL_PLUGIN}/preview_bundle.py" "${STAGING_DIR}/scripts/preview_bundle.py"
cp "${CANONICAL_PLUGIN}/skill_generator.py" "${STAGING_DIR}/scripts/skill_generator.py"
cp "${CANONICAL_PLUGIN}/templates/"* "${STAGING_DIR}/scripts/templates/"
cp "${PREVIEW_PROTOCOL}" "${STAGING_DIR}/references/docs/PREVIEW_PROTOCOL.md"

# Pre-publish integrity verification: byte-equality + Python syntax check before touching DEST_DIR.
cmp -s "${CANONICAL_PLUGIN}/HARNESS.md" "${STAGING_DIR}/references/HARNESS.md"
cmp -s "${CANONICAL_PLUGIN}/repl_skin.py" "${STAGING_DIR}/scripts/repl_skin.py"
cmp -s "${CANONICAL_PLUGIN}/preview_bundle.py" "${STAGING_DIR}/scripts/preview_bundle.py"
cmp -s "${CANONICAL_PLUGIN}/skill_generator.py" "${STAGING_DIR}/scripts/skill_generator.py"
cmp -s "${PREVIEW_PROTOCOL}" "${STAGING_DIR}/references/docs/PREVIEW_PROTOCOL.md"

PYBIN="$(detect_python_bin 2>/dev/null || true)"
if [[ -n "${PYBIN}" ]]; then
  # On POSIX hosts where only `python3` exists, adapt hooks.json so opting in works out of the box.
  if [[ "${PYBIN}" == "python3" && -f "${STAGING_DIR}/hooks.json" ]] && ! command -v python >/dev/null 2>&1; then
    "${PYBIN}" -c '
import pathlib, sys
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text(encoding="utf-8").replace("python -S ./scripts/pep420_guard.py", "python3 -S ./scripts/pep420_guard.py"), encoding="utf-8")
' "${STAGING_DIR}/hooks.json"
  fi
  "${PYBIN}" -B -m py_compile \
    "${STAGING_DIR}/scripts/repl_skin.py" \
    "${STAGING_DIR}/scripts/preview_bundle.py" \
    "${STAGING_DIR}/scripts/skill_generator.py" \
    "${STAGING_DIR}/scripts/_toml_fallback.py" \
    "${STAGING_DIR}/scripts/verify_harness.py" \
    "${STAGING_DIR}/scripts/list_harnesses.py" \
    "${STAGING_DIR}/scripts/pep420_guard.py"
fi

# Atomic replace when upgrading.
# If interrupted after moving the old install aside, look for
# ${PLUGINS_HOME}/.cli-anything.bak.* and restore it manually.
if [[ -e "${DEST_DIR}" ]]; then
  if [[ "${FORCE}" -ne 1 ]]; then
    echo "Refusing to overwrite existing plugin: ${DEST_DIR}" >&2
    echo "Re-run with --force to upgrade, or remove it manually." >&2
    exit 1
  fi
  BACKUP_DIR="${PLUGINS_HOME}/.cli-anything.bak.$(date +%s).$$"
  mv "${DEST_DIR}" "${BACKUP_DIR}"
  if ! mv "${STAGING_DIR}" "${DEST_DIR}"; then
    mv "${BACKUP_DIR}" "${DEST_DIR}"
    echo "Failed to install plugin; previous install restored." >&2
    exit 1
  fi
  rm -rf "${BACKUP_DIR}"
else
  mv "${STAGING_DIR}" "${DEST_DIR}"
fi
STAGING_DIR=""

# Resolve final absolute plugin root and stamp it for Antigravity tool resolution.
PLUGIN_ROOT="$(to_host_path "$(cd "${DEST_DIR}" && pwd -P)")"
printf '%s\n' "${PLUGIN_ROOT}" > "${DEST_DIR}/PLUGIN_ROOT.txt"

if [[ "${IS_GLOBAL}" -eq 1 ]]; then
  write_discovery_pointer "${DISCOVERY_POINTER}" "${PLUGIN_ROOT}"
fi

echo "Installed Antigravity plugin to: ${DEST_DIR}"
echo "PLUGIN_ROOT stamp: ${PLUGIN_ROOT}"
if [[ "${IS_GLOBAL}" -eq 1 ]]; then
  echo "Discovery pointer: ${DISCOVERY_POINTER}"
else
  echo "Workspace-scoped install (global discovery pointer left unchanged)."
fi
echo "Vendored CLI-Anything methodology resources and verified staged scripts."
echo "Slash commands ready on next turn: /cli-anything, /cli-anything-refine, /cli-anything-test, /cli-anything-validate, /cli-anything-list"
echo "Consumer Hub/skills are separate: npx skills add HKUDS/CLI-Anything --skill cli-hub-meta-skill -g -y"
