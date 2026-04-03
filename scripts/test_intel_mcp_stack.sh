#!/bin/sh
set -eu

REPO_ROOT="/Users/lixun/Documents/codex "

python3 -m unittest \
  "$REPO_ROOT/tests/test_intel_skill_runtime.py" \
  "$REPO_ROOT/tests/test_intel_mcp_server.py" \
  "$REPO_ROOT/tests/test_intel_mcp_doctor.py" \
  "$REPO_ROOT/tests/test_intel_plugin_manifest.py"

python3 "$REPO_ROOT/scripts/intel_mcp_doctor.py" --pretty --strict
