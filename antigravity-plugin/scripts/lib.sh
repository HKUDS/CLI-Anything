# Shared helpers for CLI-Anything Google Antigravity plugin install/uninstall (bash).
# shellcheck shell=bash

is_wsl_host() {
  [[ -n "${WSL_DISTRO_NAME:-}" || -n "${WSL_INTEROP:-}" ]] && return 0
  grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease 2>/dev/null
}

is_case_insensitive_path() {
  local p="${1}"
  case "${p}" in
    [A-Za-z]:/*|[A-Za-z]:\\*|\\\\*) return 0 ;;
  esac
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*|Darwin) return 0 ;;
    Linux)
      if is_wsl_host && [[ "${p}" =~ ^/mnt/[a-zA-Z](/|$) ]]; then
        return 0
      fi
      ;;
  esac
  return 1
}

normalize_path_key() {
  local p="${1}"
  p="$(printf '%s' "${p}" | tr '\\' '/')"
  if [[ "${p}" != "/" ]]; then
    p="$(printf '%s' "${p}" | sed 's:/*$::')"
  fi
  if is_case_insensitive_path "${1}"; then
    printf '%s' "${p}" | tr '[:upper:]' '[:lower:]'
  else
    printf '%s' "${p}"
  fi
}

# Convert Git Bash / MSYS / Cygwin / WSL-mounted Windows paths to Windows host paths.
# Leaves native Linux and macOS POSIX paths untouched.
to_host_path() {
  local p="${1}"
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*)
      if command -v cygpath >/dev/null 2>&1; then
        cygpath -w "${p}"
        return 0
      fi
      if [[ "${p}" =~ ^/([a-zA-Z])/(.*)$ ]]; then
        local drive rest
        drive="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:lower:]' '[:upper:]')"
        rest="${BASH_REMATCH[2]//\//\\}"
        printf '%s:\\%s' "${drive}" "${rest}"
        return 0
      fi
      ;;
    Linux)
      if is_wsl_host && [[ "${p}" =~ ^/mnt/([a-zA-Z])/(.*)$ ]]; then
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
    case "$(uname -s 2>/dev/null || true)" in
      MINGW*|MSYS*|CYGWIN*)
        if command -v cygpath >/dev/null 2>&1; then
          out="$(cygpath -u "${out}")"
        fi
        ;;
    esac
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

# Convert Windows host drive paths (e.g. C:\foo\bar) into shell POSIX paths on MSYS/Cygwin/WSL.
from_host_path() {
  local p="${1}"
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*)
      if [[ "${p}" =~ ^[A-Za-z]:[\\/] || "${p}" == \\\\* ]]; then
        if command -v cygpath >/dev/null 2>&1; then
          cygpath -u "${p}"
          return 0
        fi
        if [[ "${p}" =~ ^([A-Za-z]):[\\/](.*)$ ]]; then
          local drive rest
          drive="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
          rest="$(printf '%s' "${BASH_REMATCH[2]}" | tr '\\' '/')"
          printf '/%s/%s' "${drive}" "${rest}"
          return 0
        fi
      fi
      ;;
    Linux)
      if is_wsl_host && [[ "${p}" =~ ^([A-Za-z]):[\\/](.*)$ ]]; then
        local drive rest
        drive="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
        rest="$(printf '%s' "${BASH_REMATCH[2]}" | tr '\\' '/')"
        printf '/mnt/%s/%s' "${drive}" "${rest}"
        return 0
      fi
      ;;
  esac
  printf '%s' "${p}"
}

# Resolve symlinks/junctions on a path (including existing ancestors when the leaf is absent),
# returning a host-format path suitable for normalize_path_key comparison.
resolve_real_path() {
  local raw="${1}"
  local shell_path
  shell_path="$(from_host_path "${raw}")"

  local pybin=""
  pybin="$(detect_python_bin 2>/dev/null || true)"
  if [[ -n "${pybin}" ]]; then
    local py_input="${shell_path}"
    case "$(uname -s 2>/dev/null || true)" in
      MINGW*|MSYS*|CYGWIN*)
        # Native Windows Python expects a Windows path; MSYS Python accepts both.
        py_input="$(to_host_path "${shell_path}")"
        ;;
    esac
    local py_out=""
    if py_out="$("${pybin}" -c 'import os,sys; print(os.path.realpath(os.path.expanduser(sys.argv[1])))' "${py_input}" 2>/dev/null)" && [[ -n "${py_out}" ]]; then
      to_host_path "${py_out}"
      return 0
    fi
  fi

  # Pure-shell fallback (no Python): walk up to the deepest existing directory and resolve with pwd -P.
  local cur="${shell_path}"
  local suffix=""
  if [[ "${cur}" == "~"* ]]; then
    cur="${HOME}${cur:1}"
  fi
  if [[ "${cur}" != "/" ]]; then
    cur="${cur%/}"
  fi
  while [[ -n "${cur}" && "${cur}" != "/" && ! -d "${cur}" ]]; do
    local base parent
    base="$(basename "${cur}")"
    parent="$(dirname "${cur}")"
    if [[ "${parent}" == "${cur}" ]]; then
      break
    fi
    if [[ -n "${suffix}" ]]; then
      suffix="${base}/${suffix}"
    else
      suffix="${base}"
    fi
    cur="${parent}"
  done

  if [[ -d "${cur}" ]]; then
    local resolved_dir
    resolved_dir="$(cd "${cur}" 2>/dev/null && pwd -P)" || resolved_dir="${cur}"
    if [[ -n "${suffix}" ]]; then
      if [[ "${resolved_dir}" == "/" ]]; then
        resolved_dir="/${suffix}"
      else
        resolved_dir="${resolved_dir}/${suffix}"
      fi
    fi
    to_host_path "${resolved_dir}"
    return 0
  fi

  to_host_path "${shell_path}"
}

# True when dir is a self-installed cli-anything plugin directory (supports invoking
# uninstall.sh via a symlink/junction target path whose parent basename is not 'plugins').
is_verified_self_install_dir() {
  local dir="${1}"
  [[ "$(basename "${dir}")" == "cli-anything" ]] || return 1
  [[ -f "${dir}/PLUGIN_ROOT.txt" && -f "${dir}/plugin.json" ]] || return 1
  grep -q '"name"[[:space:]]*:[[:space:]]*"cli-anything"' "${dir}/plugin.json" || return 1
  local stamped real_dir stamp_key stamp_real_key real_key dir_key
  stamped="$(tr -d '\r\n' < "${dir}/PLUGIN_ROOT.txt")"
  [[ -n "${stamped}" ]] || return 1
  real_dir="$(to_host_path "$(cd "${dir}" && pwd -P)")"
  stamp_key="$(normalize_path_key "${stamped}")"
  stamp_real_key="$(normalize_path_key "$(resolve_real_path "${stamped}")")"
  real_key="$(normalize_path_key "${real_dir}")"
  dir_key="$(normalize_path_key "$(to_host_path "${dir}")")"
  [[ "${stamp_key}" == "${real_key}" || "${stamp_key}" == "${dir_key}" || "${stamp_real_key}" == "${real_key}" ]]
}

discovery_pointer_path() {
  printf '%s' "${HOME}/.gemini/cli-anything-generator.root"
}

# Atomically publish the shared discovery pointer so concurrent global installs
# targeting distinct ANTIGRAVITY_PLUGINS_HOME roots never truncate or interleave it.
write_discovery_pointer() {
  local pointer_path="${1}"
  local value="${2}"
  local ptr_dir ptr_tmp="" ptr_lock="" rc=1
  ptr_dir="$(dirname "${pointer_path}")"
  mkdir -p "${ptr_dir}"
  ptr_lock="${ptr_dir}/.cli-anything-generator.root.lock"
  acquire_install_lock "${ptr_lock}"
  if ptr_tmp="$(mktemp "${ptr_dir}/.cli-anything-generator.root.tmp.XXXXXX")"; then
    if printf '%s\n' "${value}" > "${ptr_tmp}"; then
      local attempt=0 moved=0
      while [[ "${attempt}" -lt 10 ]]; do
        if mv -f "${ptr_tmp}" "${pointer_path}" 2>/dev/null; then
          moved=1
          break
        fi
        attempt=$((attempt + 1))
        sleep 0.05
      done
      if [[ "${moved}" -eq 1 ]] || mv -f "${ptr_tmp}" "${pointer_path}"; then
        rc=0
      else
        rm -f "${ptr_tmp}" 2>/dev/null || true
      fi
    else
      rm -f "${ptr_tmp}" 2>/dev/null || true
    fi
  fi
  release_install_lock "${ptr_lock}"
  return "${rc}"
}

# Atomically check and remove the shared discovery pointer under the same lock
# used by write_discovery_pointer() so concurrent installs into another root
# cannot publish a new pointer between comparison and deletion.
remove_discovery_pointer_if_matches() {
  local pointer_path="${1}"
  local dest_host="${2}"
  local dest_dir="${3}"
  local ptr_dir ptr_lock="" rc=0
  ptr_dir="$(dirname "${pointer_path}")"
  if [[ ! -d "${ptr_dir}" ]]; then
    echo "Discovery pointer not present: ${pointer_path}"
    return 0
  fi
  ptr_lock="${ptr_dir}/.cli-anything-generator.root.lock"
  acquire_install_lock "${ptr_lock}"
  if [[ -f "${pointer_path}" ]]; then
    local pointer="" ptr_key="" ptr_real_key="" dest_key="" dest_unix_key=""
    if pointer="$(tr -d '\r\n' < "${pointer_path}")"; then
      ptr_key="$(normalize_path_key "${pointer}" || true)"
      ptr_real_key="$(normalize_path_key "$(resolve_real_path "${pointer}" || true)" || true)"
      dest_key="$(normalize_path_key "${dest_host}" || true)"
      dest_unix_key="$(normalize_path_key "${dest_dir}" || true)"
      if [[ "${ptr_key}" == "${dest_key}" || "${ptr_key}" == "${dest_unix_key}" || "${ptr_real_key}" == "${dest_key}" ]]; then
        if rm -f "${pointer_path}"; then
          echo "Removed discovery pointer: ${pointer_path}"
        else
          rc=1
        fi
      else
        echo "Left discovery pointer unchanged (points elsewhere): ${pointer}"
      fi
    else
      rc=1
    fi
  else
    echo "Discovery pointer not present: ${pointer_path}"
  fi
  release_install_lock "${ptr_lock}"
  return "${rc}"
}
