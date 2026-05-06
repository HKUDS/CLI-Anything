#!/usr/bin/env bash
# cli-anything plugin setup script

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Windows bash environment check (helps avoid cryptic cygpath errors later)
is_windows_bash() {
    case "$(uname -s 2>/dev/null)" in
        CYGWIN*|MINGW*|MSYS*) return 0 ;;
    esac
    return 1
}

if is_windows_bash && ! command -v cygpath >/dev/null 2>&1; then
    echo -e "${RED}✗${NC} Windows bash environment detected but 'cygpath' was not found."
    echo -e "${YELLOW}  Please install Git for Windows (Git Bash) or use WSL, then rerun this script.${NC}"
    exit 1
fi

# Plugin info
PLUGIN_NAME="cli-anything"
PLUGIN_VERSION="1.0.0"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  cli-anything Plugin v${PLUGIN_VERSION}${NC}"
echo -e "${BLUE}  Build powerful CLI interfaces for any GUI application${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if HARNESS.md exists
HARNESS_PATH="/root/cli-anything/HARNESS.md"
if [ ! -f "$HARNESS_PATH" ]; then
    echo -e "${YELLOW}⚠️  HARNESS.md not found at $HARNESS_PATH${NC}"
    echo -e "${YELLOW}   The cli-anything methodology requires HARNESS.md${NC}"
    echo -e "${YELLOW}   You can create it or specify a custom path with --harness-path${NC}"
    echo ""
fi

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
echo "  HARNESS.md: /root/cli-anything/HARNESS.md"
echo "  Plugin README: Use '/help cli-anything' for more info"
echo ""
echo -e "${GREEN}Ready to build CLI harnesses! 🚀${NC}"
echo ""
