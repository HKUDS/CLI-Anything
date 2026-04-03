#!/bin/sh
set -eu

REPO_ROOT="/Users/lixun/Documents/codex "

python3 "$REPO_ROOT/scripts/install_intel_mcp_clients.py" --pretty
sh "$REPO_ROOT/scripts/install_intel_mcp_pre_push_hook.sh"
sh "$REPO_ROOT/scripts/test_intel_mcp_stack.sh"
