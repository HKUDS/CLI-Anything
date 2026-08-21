# Shared helpers for CLI-Anything Cursor plugin install/uninstall (bash).
# shellcheck shell=bash

normalize_path_key() {
  printf '%s' "${1}" | tr '[:upper:]' '[:lower:]' | tr '\\' '/' | sed 's:/*$::'
}

# Convert Git Bash / MSYS / Cygwin / WSL-style paths to Windows host paths for Cursor tools.
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

# Resolve CURSOR_PLUGINS_HOME / default plugins root.
# Second arg: "create" to mkdir (install), anything else skips creating.
resolve_plugins_home() {
  local raw="${1}"
  local mode="${2:-}"
  if [[ -z "${raw}" || "${raw}" == "." || "${raw}" == ".." ]]; then
    echo "Invalid CURSOR_PLUGINS_HOME: ${raw}" >&2
    return 1
  fi

  # Canonicalize without creating the path (abspath collapses ".." safely).
  if command -v python3 >/dev/null 2>&1; then
    raw="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "${raw}")"
  elif command -v python >/dev/null 2>&1; then
    raw="$(python -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "${raw}")"
  else
    if [[ "${raw}" == "~"* ]]; then
      raw="${HOME}${raw:1}"
    fi
    if [[ "${raw}" != /* && "${raw}" != [A-Za-z]:* && "${raw}" != \\* ]]; then
      raw="$(pwd)/${raw}"
    fi
    case "${raw}" in
      *..*)
        echo "Invalid CURSOR_PLUGINS_HOME (refuses '..' without python): ${raw}" >&2
        return 1
        ;;
    esac
  fi

  if [[ "$(basename "${raw}")" != "plugins" ]]; then
    echo "CURSOR_PLUGINS_HOME must resolve to a directory named 'plugins' (got: ${raw})" >&2
    echo "Example: ~/.cursor/plugins or /custom/path/plugins" >&2
    return 1
  fi

  if [[ "${mode}" == "create" ]]; then
    mkdir -p "${raw}"
    if command -v realpath >/dev/null 2>&1; then
      raw="$(realpath "${raw}")"
    else
      raw="$(cd "${raw}" && pwd -P)"
    fi
  elif [[ -d "${raw}" ]]; then
    if command -v realpath >/dev/null 2>&1; then
      raw="$(realpath "${raw}")"
    else
      raw="$(cd "${raw}" && pwd -P)"
    fi
  fi
  printf '%s' "${raw}"
}

# True when path is .../local/cli-anything (slash or backslash).
is_cli_anything_install_path() {
  local key
  key="$(normalize_path_key "${1}")"
  [[ "$(basename "${key}")" == "cli-anything" ]] || return 1
  case "${key}" in
    */local/cli-anything) return 0 ;;
    *) return 1 ;;
  esac
}

discovery_pointer_path() {
  printf '%s' "${HOME}/.cursor/cli-anything-generator.root"
}
