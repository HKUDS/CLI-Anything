#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

python3 "$REPO_ROOT/scripts/install_intel_mcp_clients.py" --pretty
sh "$REPO_ROOT/scripts/install_intel_mcp_pre_push_hook.sh"
sh "$REPO_ROOT/scripts/test_intel_mcp_stack.sh"
