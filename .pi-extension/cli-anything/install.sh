#!/usr/bin/env bash
# install.sh — Install CLI-Anything extension for Pi Coding Agent globally.
#
# Copies the extension into Pi's global extensions directory so the
# /cli-anything commands are available in ALL projects.
#
# Usage:
#   bash install.sh              # Install
#   bash install.sh --uninstall  # Uninstall
#
# After installing, run '/reload' in Pi or restart Pi to activate.

set -euo pipefail

# ─── Paths ─────────────────────────────────────────────────────────────

TARGET_DIR="$HOME/.pi/agent/extensions/cli-anything"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Find repo root reliably — use git, fall back to searching upward
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" || {
	dir="$SCRIPT_DIR"
	while [ "$dir" != "/" ]; do
		if [ -f "$dir/.git" ] || [ -d "$dir/.git" ] || [ -f "$dir/CONTRIBUTING.md" ]; then
			REPO_ROOT="$dir"
			break
		fi
		dir="$(dirname "$dir")"
	done
	if [ -z "${REPO_ROOT:-}" ]; then
		echo "Error: Cannot determine repo root. Run this script from inside the CLI-Anything repository."
		exit 1
	fi
}

# ─── Uninstall ─────────────────────────────────────────────────────────

if [ "${1:-}" = "--uninstall" ]; then
    if [ -d "$TARGET_DIR" ]; then
        rm -rf "$TARGET_DIR"
        echo "✓ CLI-Anything extension uninstalled from $TARGET_DIR"
    else
        echo "Extension not found at $TARGET_DIR (already uninstalled)"
    fi
    exit 0
fi

# ─── Pre-flight checks ────────────────────────────────────────────────

if [ ! -f "$SCRIPT_DIR/index.ts" ]; then
    echo "Error: Cannot find index.ts in $SCRIPT_DIR"
    echo "Make sure you're running this script from the extension directory."
    exit 1
fi

PLUGIN_SRC="$REPO_ROOT/cli-anything-plugin"
for required in \
    "$SCRIPT_DIR/index.ts" \
    "$PLUGIN_SRC/HARNESS.md" \
    "$PLUGIN_SRC/repl_skin.py" \
    "$PLUGIN_SRC/preview_bundle.py" \
    "$PLUGIN_SRC/skill_generator.py" \
    "$PLUGIN_SRC/templates/SKILL.md.template" \
    "$REPO_ROOT/docs/PREVIEW_PROTOCOL.md"; do
    if [ ! -f "$required" ]; then
        echo "Error: Missing required extension resource: $required" >&2
        exit 1
    fi
done
for command in cli-anything refine test validate list; do
    if [ ! -f "$PLUGIN_SRC/commands/$command.md" ]; then
        echo "Error: Missing command specification: $command.md" >&2
        exit 1
    fi
done

# Assemble the complete extension before replacing a working installation.
PARENT_DIR="$(dirname "$TARGET_DIR")"
mkdir -p "$PARENT_DIR"
STAGING_DIR="$(mktemp -d "$PARENT_DIR/.cli-anything.tmp.XXXXXX")"
BACKUP_DIR=""
cleanup() {
    if [ -n "$STAGING_DIR" ] && [ -d "$STAGING_DIR" ]; then
        rm -rf "$STAGING_DIR"
    fi
}
trap cleanup EXIT

mkdir -p "$STAGING_DIR/commands" "$STAGING_DIR/guides" \
    "$STAGING_DIR/scripts" "$STAGING_DIR/templates" "$STAGING_DIR/docs"
cp "$SCRIPT_DIR/index.ts" "$STAGING_DIR/"
cp "$PLUGIN_SRC/commands/"*.md "$STAGING_DIR/commands/"
cp "$PLUGIN_SRC/guides/"*.md "$STAGING_DIR/guides/"
cp "$PLUGIN_SRC/templates/"* "$STAGING_DIR/templates/"
cp "$PLUGIN_SRC/HARNESS.md" "$STAGING_DIR/"
cp "$PLUGIN_SRC/repl_skin.py" "$STAGING_DIR/scripts/"
cp "$PLUGIN_SRC/preview_bundle.py" "$STAGING_DIR/scripts/"
cp "$PLUGIN_SRC/skill_generator.py" "$STAGING_DIR/scripts/"
cp "$REPO_ROOT/docs/PREVIEW_PROTOCOL.md" "$STAGING_DIR/docs/"
if [ -d "$PLUGIN_SRC/tests" ]; then
    mkdir -p "$STAGING_DIR/tests"
    cp "$PLUGIN_SRC/tests/"*.py "$STAGING_DIR/tests/"
fi

if [ -e "$TARGET_DIR" ]; then
    BACKUP_DIR="$(mktemp -d "$PARENT_DIR/.cli-anything.backup.XXXXXX")"
    mv "$TARGET_DIR" "$BACKUP_DIR/previous"
fi
if ! mv "$STAGING_DIR" "$TARGET_DIR"; then
    if [ -n "$BACKUP_DIR" ]; then
        mv "$BACKUP_DIR/previous" "$TARGET_DIR" || {
            echo "Previous installation retained at: $BACKUP_DIR/previous" >&2
            exit 1
        }
        rmdir "$BACKUP_DIR"
    fi
    exit 1
fi
STAGING_DIR=""
if [ -n "$BACKUP_DIR" ]; then
    rm -rf "$BACKUP_DIR"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ CLI-Anything extension installed globally!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Location: $TARGET_DIR"
echo ""
echo "  Available commands:"
echo "    /cli-anything <path-or-repo>        Build a CLI harness"
echo "    /cli-anything:refine <path> [focus] Refine a harness"
echo "    /cli-anything:test <path-or-repo>   Test a harness"
echo "    /cli-anything:validate <path>       Validate a harness"
echo "    /cli-anything:list [options]        List all CLI tools"
echo ""
echo "  Run '/reload' in Pi or restart Pi to activate."
echo ""
