# Shared helpers for CLI-Anything Google Antigravity plugin install/uninstall (bash).
# shellcheck shell=bash

normalize_path_key() {
  printf '%s' "${1}" | tr '[:upper:]' '[:lower:]' | tr '\\' '/' | sed 's:/*$::'
}

# Convert Git Bash / MSYS / Cygwin / WSL-style paths to Windows host paths for Antigravity tools.
to_host_path() {
  local p="${1}"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "${p}"
    return 0
  fi
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*|Linux)
      if [[ "${p}" =~ ^/([a-zA-Z])/(.*)$ ]]; then
        local drive rest
        drive="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:lower:]' '[:upper:]')"
        rest="${BASH_REMATCH[2]//\//\\}"
        printf '%s:\\%s' "${drive}" "${rest}"
        return 0
      fi
      if [[ "${p}" =~ ^/mnt/([a-zA-Z])/(.*)$ ]]; then
        local drive rest
        drive="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:lower:]' '[:upper:]')"
        rest="${BASH_REMATCH[2]//\//\\}"
        printf '%s:\\%s' "${drive}" "${rest}"
        return 0
      fi
      ;;
  esac
  printf '%s' "${p}"
}

detect_python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    if python3 -c "import sys" >/dev/null 2>&1; then
      printf '%s' "python3"
      return 0
    fi
  fi
  if command -v python >/dev/null 2>&1; then
    if python -c "import sys" >/dev/null 2>&1; then
      printf '%s' "python"
      return 0
    fi
  fi
  return 1
}

canonicalize_path() {
  local raw="${1}"
  local pybin=""
  pybin="$(detect_python_bin 2>/dev/null || true)"
  if [[ -n "${pybin}" ]]; then
    local out
    out="$("${pybin}" -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "${raw}")"
    if command -v cygpath >/dev/null 2>&1; then
      out="$(cygpath -u "${out}")"
    fi
    printf '%s' "${out}"
  else
    if [[ "${raw}" == "~"* ]]; then
      raw="${HOME}${raw:1}"
    fi
    if [[ "${raw}" != /* && "${raw}" != [A-Za-z]:* && "${raw}" != \\* ]]; then
      raw="$(pwd)/${raw}"
    fi
    case "${raw}" in
      *..*)
        echo "Invalid path (refuses '..' without python): ${raw}" >&2
        return 1
        ;;
    esac
    if [[ "${raw}" != "/" ]]; then
      raw="${raw%/}"
    fi
    printf '%s' "${raw}"
  fi
}

# Resolve ANTIGRAVITY_PLUGINS_HOME / default global plugins root.
# Second arg: "create" to mkdir (install), anything else skips creating.
# Preserves the logical `.../plugins` path even when `plugins` is a symlink to a
# differently named storage directory so install and uninstall follow the same path policy.
resolve_plugins_home() {
  local raw="${1}"
  local mode="${2:-}"
  if [[ -z "${raw}" || "${raw}" == "." || "${raw}" == ".." ]]; then
    echo "Invalid ANTIGRAVITY_PLUGINS_HOME: ${raw}" >&2
    return 1
  fi

  raw="$(canonicalize_path "${raw}")"

  if [[ "$(basename "${raw}")" != "plugins" ]]; then
    echo "ANTIGRAVITY_PLUGINS_HOME must resolve to a directory named 'plugins' (got: ${raw})" >&2
    echo "Example: ~/.gemini/config/plugins or /custom/path/plugins" >&2
    return 1
  fi

  if [[ "${mode}" == "create" ]]; then
    if [[ -L "${raw}" && ! -d "${raw}" ]]; then
      echo "Plugins symlink target does not exist or is not a directory: ${raw}" >&2
      return 1
    fi
    if [[ -e "${raw}" && ! -d "${raw}" ]]; then
      echo "Plugins path exists and is not a directory: ${raw}" >&2
      return 1
    fi
    mkdir -p "${raw}"
  fi
  printf '%s' "${raw}"
}

resolve_workspace_root() {
  local raw="${1}"
  if [[ -z "${raw}" ]]; then
    echo "Workspace path must not be empty." >&2
    return 1
  fi
  raw="$(canonicalize_path "${raw}")"
  if [[ ! -d "${raw}" ]]; then
    echo "Workspace directory does not exist: ${raw}" >&2
    return 1
  fi
  if command -v realpath >/dev/null 2>&1; then
    realpath "${raw}"
  else
    (cd "${raw}" && pwd -P)
  fi
}

# Atomic exclusive lock file (POSIX O_CREAT|O_EXCL via shell noclobber) to serialize
# concurrent installs into the same plugins root. Avoids external `mkdir` races observed
# in some coreutils implementations (e.g. uutils coreutils 0.8.0 on Ubuntu 26.04) and
# matches the Windows PowerShell FileMode.CreateNew lock on the same `.cli-anything.lock` path.
acquire_install_lock() {
  local lock_path="${1}"
  local max_attempts="${2:-50}"
  local attempt=0
  while ! ( set -C; printf '%s\n' "$$" > "${lock_path}" ) 2>/dev/null; do
    attempt=$((attempt + 1))
    if [[ "${attempt}" -ge "${max_attempts}" ]]; then
      echo "Could not acquire install lock: ${lock_path}" >&2
      echo "Another install may be running. If a previous run was killed, remove ${lock_path} and retry." >&2
      return 1
    fi
    sleep 0.1
  done
}

release_install_lock() {
  local lock_path="${1}"
  if [[ -n "${lock_path}" && -e "${lock_path}" ]]; then
    rm -rf "${lock_path}"
  fi
}

# True when path is .../plugins/cli-anything (slash or backslash).
is_cli_anything_install_path() {
  local key
  key="$(normalize_path_key "${1}")"
  [[ "$(basename "${key}")" == "cli-anything" ]] || return 1
  case "${key}" in
    */plugins/cli-anything) return 0 ;;
    *) return 1 ;;
  esac
}

# True when dir is a self-installed cli-anything plugin directory (supports invoking
# uninstall.sh via a symlink target path whose parent basename is not 'plugins').
is_verified_self_install_dir() {
  local dir="${1}"
  [[ "$(basename "${dir}")" == "cli-anything" ]] || return 1
  [[ -f "${dir}/PLUGIN_ROOT.txt" && -f "${dir}/plugin.json" ]] || return 1
  grep -q '"name"[[:space:]]*:[[:space:]]*"cli-anything"' "${dir}/plugin.json" || return 1
  local stamped real_dir stamp_key real_key dir_key
  stamped="$(tr -d '\r\n' < "${dir}/PLUGIN_ROOT.txt")"
  [[ -n "${stamped}" ]] || return 1
  real_dir="$(to_host_path "$(cd "${dir}" && pwd -P)")"
  stamp_key="$(normalize_path_key "${stamped}")"
  real_key="$(normalize_path_key "${real_dir}")"
  dir_key="$(normalize_path_key "$(to_host_path "${dir}")")"
  [[ "${stamp_key}" == "${real_key}" || "${stamp_key}" == "${dir_key}" ]]
}

discovery_pointer_path() {
  printf '%s' "${HOME}/.gemini/cli-anything-generator.root"
}
