#!/usr/bin/env bash
# Unified registration for CLI-Anything across Claude Code, OpenCode, and Codex.
# One command to install all three adapters from this repository.
#
# Usage:
#   scripts/register.sh install [--targets claude,opencode,codex|all]
#   scripts/register.sh status  [--targets claude,opencode,codex|all]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

KNOWN_TARGETS=(claude opencode codex)

# OpenCode needs the command files plus HARNESS.md from the plugin directory.
OPENCODE_FILES=(cli-anything.md cli-anything-refine.md cli-anything-test.md cli-anything-validate.md cli-anything-list.md cli-anything-register.md)

die()  { printf 'error: %s\n' "$*" >&2; exit 1; }
log()  { printf '%s\n' "$*"; }

# --- source / destination paths -------------------------------------------

claude_src()     { echo "$REPO_ROOT/cli-anything-plugin"; }
claude_dst()     { echo "$HOME/.claude/plugins/cli-anything"; }

codex_src()      { echo "$REPO_ROOT/codex-skill"; }
codex_dst()      { echo "${CODEX_HOME:-$HOME/.codex}/skills/cli-anything"; }

opencode_dst()   { echo "${OPENCODE_HOME:-$HOME/.config/opencode}/commands"; }

# --- install helpers -------------------------------------------------------

install_claude() {
    local src; src="$(claude_src)"
    local dst; dst="$(claude_dst)"
    [[ -d "$src" ]] || die "source missing: $src"
    if [[ -e "$dst" ]]; then log "  skip claude  (already at $dst)"; return; fi
    mkdir -p "$(dirname "$dst")"
    cp -R "$src" "$dst"
    log "  installed claude  -> $dst"
}

install_opencode() {
    local dst; dst="$(opencode_dst)"
    mkdir -p "$dst"
    local skipped=0 installed=0
    for f in "${OPENCODE_FILES[@]}"; do
        local src="$REPO_ROOT/opencode-commands/$f"
        [[ -f "$src" ]] || die "source missing: $src"
        if [[ -e "$dst/$f" ]]; then skipped=$((skipped+1)); continue; fi
        cp "$src" "$dst/$f"
        installed=$((installed+1))
    done
    # HARNESS.md comes from cli-anything-plugin/
    local harness_src="$REPO_ROOT/cli-anything-plugin/HARNESS.md"
    [[ -f "$harness_src" ]] || die "source missing: $harness_src"
    if [[ -e "$dst/HARNESS.md" ]]; then
        skipped=$((skipped+1))
    else
        cp "$harness_src" "$dst/HARNESS.md"
        installed=$((installed+1))
    fi
    if [[ $skipped -gt 0 && $installed -eq 0 ]]; then
        log "  skip opencode (all $skipped files exist)"
    else
        log "  installed opencode -> $dst ($installed new, $skipped existing)"
    fi
}

install_codex() {
    local src; src="$(codex_src)"
    local dst; dst="$(codex_dst)"
    [[ -d "$src" ]] || die "source missing: $src"
    if [[ -e "$dst" ]]; then log "  skip codex   (already at $dst)"; return; fi
    mkdir -p "$(dirname "$dst")"
    cp -R "$src" "$dst"
    log "  installed codex   -> $dst"
}

# --- status ----------------------------------------------------------------

status_target() {
    local target="$1"
    case "$target" in
        claude)
            [[ -d "$(claude_dst)" ]] \
                && log "  claude   installed  $(claude_dst)" \
                || log "  claude   missing    $(claude_dst)" ;;
        codex)
            [[ -d "$(codex_dst)" ]] \
                && log "  codex    installed  $(codex_dst)" \
                || log "  codex    missing    $(codex_dst)" ;;
        opencode)
            local dst; dst="$(opencode_dst)"; local n=0; local total=$((${#OPENCODE_FILES[@]}+1))
            for f in "${OPENCODE_FILES[@]}"; do [[ -e "$dst/$f" ]] && n=$((n+1)); done
            [[ -e "$dst/HARNESS.md" ]] && n=$((n+1))
            log "  opencode ${n}/${total} files  $dst" ;;
    esac
}

# --- target resolution -----------------------------------------------------

resolve_targets() {
    local raw="${1:-all}"
    if [[ "$raw" == "all" ]]; then printf '%s\n' "${KNOWN_TARGETS[@]}"; return; fi
    IFS=',' read -r -a list <<< "$raw"
    for t in "${list[@]}"; do
        [[ " ${KNOWN_TARGETS[*]} " == *" $t "* ]] || die "unknown target: $t"
        printf '%s\n' "$t"
    done
}

# --- main ------------------------------------------------------------------

main() {
    local cmd="${1:-help}"; shift || true
    local targets_raw="all"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --targets) [[ -n "${2:-}" ]] || die "--targets requires a value"; targets_raw="$2"; shift 2 ;;
            *) die "unknown option: $1" ;;
        esac
    done

    local -a targets; mapfile -t targets < <(resolve_targets "$targets_raw")

    case "$cmd" in
        install)
            log "Installing CLI-Anything adapters..."
            for t in "${targets[@]}"; do "install_$t"; done
            log "Done. Run '$0 status' to verify."
            ;;
        status)
            for t in "${targets[@]}"; do status_target "$t"; done
            ;;
        *)
            cat <<'EOF'
Unified CLI-Anything registration.

Usage:
  scripts/register.sh install [--targets claude,opencode,codex|all]
  scripts/register.sh status  [--targets claude,opencode,codex|all]

Installs the existing platform adapters from this repository into each
agent's local configuration directory. Does not modify any files in
the repository itself.
EOF
            ;;
    esac
}

main "$@"
