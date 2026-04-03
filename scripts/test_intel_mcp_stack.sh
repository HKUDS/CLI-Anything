#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

python3 -m unittest \
  tests.test_intel_skill_runtime \
  tests.test_intel_mcp_server \
  tests.test_intel_mcp_doctor \
  tests.test_intel_plugin_manifest

python3 "$REPO_ROOT/scripts/intel_mcp_doctor.py" --pretty --strict
