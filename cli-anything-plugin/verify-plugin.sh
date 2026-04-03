#!/usr/bin/env bash
# Verify cli-anything plugin structure

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Verifying cli-anything plugin structure..."
echo ""

ERRORS=0

check_file() {
    if [ -f "$1" ]; then
        echo "✓ $1"
    else
        echo "✗ $1 (MISSING)"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "Required files:"
check_file ".claude-plugin/plugin.json"
check_file "README.md"
check_file "LICENSE"
check_file "PUBLISHING.md"
check_file "workflow-registry.json"
check_file "commands/cli-anything.md"
check_file "commands/refine.md"
check_file "commands/test.md"
check_file "commands/validate.md"
check_file "commands/list.md"
check_file "scripts/setup-cli-anything.sh"

echo ""
echo "Checking plugin.json validity..."
if python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))" 2>/dev/null; then
    echo "✓ plugin.json is valid JSON"
else
    echo "✗ plugin.json is invalid JSON"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "Checking workflow registry validity and command parity..."
if python3 - <<'PY'
import json
from pathlib import Path

root = Path(".")
registry_path = root / "workflow-registry.json"
commands_dir = root / "commands"

registry = json.loads(registry_path.read_text(encoding="utf-8"))
assert isinstance(registry, list) and registry, "workflow registry must be a non-empty list"

registry_commands = []
registry_docs = set()
for entry in registry:
    command = entry["command"]
    registry_commands.append(command)
    for relative_path in entry["expectedFiles"]:
        if relative_path.startswith("commands/") and relative_path.endswith(".md"):
            registry_docs.add(Path(relative_path).stem)
        assert (root / relative_path).exists(), f"missing expected file: {relative_path}"

command_docs = {path.stem for path in commands_dir.glob("*.md")}

assert len(set(registry_commands)) == len(registry_commands), "duplicate registry commands found"
assert set(registry_commands) == command_docs, "registry commands do not match command docs"
assert registry_docs == command_docs, "registry expectedFiles do not match command docs"
PY
then
    echo "✓ workflow-registry.json parses and matches commands/*.md"
else
    echo "✗ workflow registry is invalid or out of sync with commands/*.md"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "Checking script permissions..."
if [ -x "scripts/setup-cli-anything.sh" ]; then
    echo "✓ setup-cli-anything.sh is executable"
else
    echo "✗ setup-cli-anything.sh is not executable"
    ERRORS=$((ERRORS + 1))
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "✓ All checks passed! Plugin is ready."
    exit 0
else
    echo "✗ $ERRORS error(s) found. Please fix before publishing."
    exit 1
fi
