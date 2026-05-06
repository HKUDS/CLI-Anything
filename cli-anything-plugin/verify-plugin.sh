#!/usr/bin/env bash
# Verify cli-anything plugin structure

echo "Verifying cli-anything plugin structure..."
echo ""

ERRORS=0

# Check required files
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
check_file "commands/cli-anything.md"
check_file "commands/refine.md"
check_file "commands/test.md"
check_file "commands/validate.md"
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
