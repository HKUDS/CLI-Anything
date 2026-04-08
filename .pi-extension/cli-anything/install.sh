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

HARNESS_SRC="$REPO_ROOT/cli-anything-plugin/HARNESS.md"
if [ ! -f "$HARNESS_SRC" ]; then
    echo "Warning: HARNESS.md not found at $HARNESS_SRC"
    echo "The extension will still be installed but may not function correctly."
    echo ""
fi

# ─── Install ───────────────────────────────────────────────────────────

echo "Installing CLI-Anything extension for Pi Coding Agent..."
echo ""

# Create target directories
mkdir -p "$TARGET_DIR/commands"
mkdir -p "$TARGET_DIR/guides"
mkdir -p "$TARGET_DIR/scripts"
mkdir -p "$TARGET_DIR/templates"

# Copy extension entry point
cp "$SCRIPT_DIR/index.ts" "$TARGET_DIR/"

# Copy command specifications from the canonical location
COMMANDS_SRC="$REPO_ROOT/cli-anything-plugin/commands"
if [ -d "$COMMANDS_SRC" ]; then
    cp "$COMMANDS_SRC/"*.md "$TARGET_DIR/commands/"
    echo "✓ commands copied from $COMMANDS_SRC"
fi
# Copy guides from the canonical location
GUIDES_SRC="$REPO_ROOT/cli-anything-plugin/guides"
if [ -d "$GUIDES_SRC" ]; then
    cp "$GUIDES_SRC/"*.md "$TARGET_DIR/guides/"
    echo "✓ guides copied from $GUIDES_SRC"
fi

# Copy templates from the canonical location
TEMPLATES_SRC="$REPO_ROOT/cli-anything-plugin/templates"
if [ -d "$TEMPLATES_SRC" ]; then
    cp "$TEMPLATES_SRC/"* "$TARGET_DIR/templates/"
    echo "✓ templates copied from $TEMPLATES_SRC"
fi

# Copy HARNESS.md from the canonical location (so the extension can find it locally)
if [ -f "$HARNESS_SRC" ]; then
    cp "$HARNESS_SRC" "$TARGET_DIR/HARNESS.md"
    echo "✓ HARNESS.md copied from $HARNESS_SRC"
fi

# Copy repl_skin.py from the canonical location
REPL_SKIN_SRC="$REPO_ROOT/cli-anything-plugin/repl_skin.py"
if [ -f "$REPL_SKIN_SRC" ]; then
    cp "$REPL_SKIN_SRC" "$TARGET_DIR/scripts/repl_skin.py"
    echo "✓ repl_skin.py copied from $REPL_SKIN_SRC"
fi

# Copy skill_generator.py from the canonical location
SKILL_GEN_SRC="$REPO_ROOT/cli-anything-plugin/skill_generator.py"
if [ -f "$SKILL_GEN_SRC" ]; then
    cp "$SKILL_GEN_SRC" "$TARGET_DIR/scripts/skill_generator.py"
    echo "✓ skill_generator.py copied from $SKILL_GEN_SRC"
fi

# Copy tests from the canonical location
TESTS_SRC="$REPO_ROOT/cli-anything-plugin/tests"
if [ -d "$TESTS_SRC" ]; then
    mkdir -p "$TARGET_DIR/tests"
    cp "$TESTS_SRC"/*.py "$TARGET_DIR/tests/"
    echo "✓ tests copied from $TESTS_SRC"
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
