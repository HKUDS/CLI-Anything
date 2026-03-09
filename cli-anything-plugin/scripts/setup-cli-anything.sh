#!/usr/bin/env bash
# cli-anything plugin setup script

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Plugin info
PLUGIN_NAME="cli-anything"
PLUGIN_VERSION="1.0.0"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  cli-anything Plugin v${PLUGIN_VERSION}${NC}"
echo -e "${BLUE}  Build powerful CLI interfaces for any GUI application${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if HARNESS.md exists (try multiple common locations)
HARNESS_PATHS=(
    "./cli-anything-plugin/HARNESS.md"
    "./HARNESS.md"
    "$HOME/cli-anything/cli-anything-plugin/HARNESS.md"
)
HARNESS_PATH=""
for path in "${HARNESS_PATHS[@]}"; do
    if [ -f "$path" ]; then
        HARNESS_PATH="$path"
        break
    fi
done

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Python 3 detected: ${PYTHON_VERSION}"
else
    echo -e "${RED}✗${NC} Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Check for required Python packages
echo ""
echo "Checking Python dependencies..."

check_package() {
    local package=$1
    if python3 -c "import $package" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $package installed"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $package not installed"
        return 1
    fi
}

MISSING_PACKAGES=()

check_package "click" || MISSING_PACKAGES+=("click")
check_package "pytest" || MISSING_PACKAGES+=("pytest")

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}Missing packages: ${MISSING_PACKAGES[*]}${NC}"
    echo -e "${YELLOW}Install with: pip install ${MISSING_PACKAGES[*]}${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Plugin installed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Available commands:"
echo ""
echo -e "  ${BLUE}/cli-anything${NC} <path-or-repo>       - Build complete CLI harness"
echo -e "  ${BLUE}/cli-anything:refine${NC} <path> [focus] - Refine existing harness"
echo -e "  ${BLUE}/cli-anything:test${NC} <path-or-repo>   - Run tests and update TEST.md"
echo -e "  ${BLUE}/cli-anything:validate${NC} <path-or-repo> - Validate against standards"
echo ""
echo "Examples:"
echo ""
echo -e "  ${BLUE}/cli-anything${NC} /home/user/gimp"
echo -e "  ${BLUE}/cli-anything:refine${NC} /home/user/blender \"particle systems\""
echo -e "  ${BLUE}/cli-anything:test${NC} /home/user/inkscape"
echo -e "  ${BLUE}/cli-anything:validate${NC} /home/user/audacity"
echo ""
echo "Documentation:"
echo ""
if [ -n "$HARNESS_PATH" ]; then
    echo "  HARNESS.md: $HARNESS_PATH"
else
    echo "  HARNESS.md: Not found (install cli-anything-plugin first)"
fi
echo "  Plugin README: Use '/help cli-anything' for more info"
echo ""
echo -e "${GREEN}Ready to build CLI harnesses! 🚀${NC}"
echo ""
