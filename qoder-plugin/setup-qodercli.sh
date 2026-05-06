#!/usr/bin/env bash
# Register cli-anything plugin for Qodercli
#
# Usage:
#   bash setup-qodercli.sh              # Auto-detect plugin path
#   bash setup-qodercli.sh /custom/path # Use custom plugin path

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Determine plugin path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Determine plugin directory: normalize to absolute path
if [ $# -ge 1 ]; then
    if ! PLUGIN_DIR="$(cd "$1" && pwd)"; then
        echo -e "${YELLOW}Error: Invalid plugin directory: $1${NC}" >&2
        exit 1
    fi
else
    # Default to cli-anything-plugin relative to qoder-plugin directory
    if ! PLUGIN_DIR="$(cd "${SCRIPT_DIR}/../cli-anything-plugin" 2>/dev/null && pwd)"; then
        echo -e "${YELLOW}Error: Could not find cli-anything-plugin directory at ${SCRIPT_DIR}/../cli-anything-plugin${NC}" >&2
        echo -e "${YELLOW}Please provide an explicit plugin path:${NC}" >&2
        echo -e "${YELLOW}  bash setup-qodercli.sh /path/to/cli-anything-plugin${NC}" >&2
        exit 1
    fi
fi

# Validate plugin directory
if [ ! -f "${PLUGIN_DIR}/.claude-plugin/plugin.json" ]; then
    echo -e "${YELLOW}Error: plugin.json not found at ${PLUGIN_DIR}/.claude-plugin/plugin.json${NC}"
    exit 1
fi

# Qodercli config file
QODER_CONFIG="${QODER_HOME:-$HOME}/.qoder.json"
CONFIG_DIR="$(dirname "${QODER_CONFIG}")"

# Ensure config directory exists
if [ ! -d "${CONFIG_DIR}" ]; then
    if ! mkdir -p "${CONFIG_DIR}"; then
        echo -e "${YELLOW}Error: Failed to create config directory ${CONFIG_DIR}${NC}" >&2
        exit 1
    fi
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  cli-anything Plugin for Qodercli${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Plugin path: ${PLUGIN_DIR}"
echo "Config file: ${QODER_CONFIG}"
echo ""

# JSON escape helper for paths when jq is not available
json_escape_path() {
    printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

# Cleanup function for temp files
cleanup_temp() {
    if [ -n "${TMP_CONFIG:-}" ] && [ -f "${TMP_CONFIG}" ]; then
        rm -f "${TMP_CONFIG}"
    fi
}
trap cleanup_temp EXIT

# Create or update config
if [ -f "${QODER_CONFIG}" ]; then
    # Config exists - need jq to safely update it
    if ! command -v jq &> /dev/null; then
        ESCAPED_PATH=$(json_escape_path "${PLUGIN_DIR}")
        echo -e "${YELLOW}jq not found. Please install jq or manually add to ${QODER_CONFIG}:${NC}"
        echo ""
        echo "Add this entry to plugins.sources.local array:"
        echo ""
        echo "  {\"path\": \"${ESCAPED_PATH}\"}"
        echo ""
        exit 1
    fi

    # Validate existing config is valid JSON before attempting modification
    if ! jq empty "${QODER_CONFIG}" 2>/dev/null; then
        echo -e "${YELLOW}Error: ${QODER_CONFIG} contains invalid JSON.${NC}"
        echo -e "${YELLOW}Please fix the JSON syntax before running this script.${NC}"
        exit 1
    fi

    # Check if plugin already registered (using --arg for safe variable passing)
    if jq -e --arg path "${PLUGIN_DIR}" '.plugins.sources.local[]? | select(.path == $path)' "${QODER_CONFIG}" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Plugin already registered in ${QODER_CONFIG}${NC}"
    else
        # Add plugin to existing config
        # Backup original config before modification
        cp "${QODER_CONFIG}" "${QODER_CONFIG}.bak"
        echo -e "  Backup saved to ${QODER_CONFIG}.bak"
        # Create temp file in same directory for atomic mv on same filesystem
        TMP_CONFIG=$(mktemp "${CONFIG_DIR}/.qoder.json.XXXXXX")
        jq --arg path "${PLUGIN_DIR}" '
            .plugins //= {} |
            .plugins.sources //= {} |
            .plugins.sources.local //= [] |
            .plugins.sources.local += [{"path": $path}]
        ' "${QODER_CONFIG}" > "${TMP_CONFIG}"
        mv "${TMP_CONFIG}" "${QODER_CONFIG}"
        echo -e "${GREEN}✓ Plugin added to ${QODER_CONFIG}${NC}"
    fi
else
    # Config does not exist - create new
    if command -v jq &> /dev/null; then
        # Use jq for safe JSON generation
        jq -n --arg path "${PLUGIN_DIR}" '
            {
                "plugins": {
                    "sources": {
                        "local": [{"path": $path}]
                    }
                }
            }
        ' > "${QODER_CONFIG}"
    else
        # Fallback: use bash with escaped path
        ESCAPED_PATH=$(json_escape_path "${PLUGIN_DIR}")
        cat > "${QODER_CONFIG}" << EOF
{
  "plugins": {
    "sources": {
      "local": [{"path": "${ESCAPED_PATH}"}]
    }
  }
}
EOF
    fi
    echo -e "${GREEN}✓ Created ${QODER_CONFIG} with plugin registered${NC}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Start a new Qodercli session to use the plugin."
echo ""
echo "Available commands:"
echo ""
echo -e "  ${BLUE}/cli-anything:cli-anything${NC} <path>    - Build complete CLI harness"
echo -e "  ${BLUE}/cli-anything:refine${NC} <path> [focus]  - Refine existing harness"
echo -e "  ${BLUE}/cli-anything:test${NC} <path>            - Run tests"
echo -e "  ${BLUE}/cli-anything:validate${NC} <path>        - Validate harness"
echo -e "  ${BLUE}/cli-anything:list${NC}                   - List CLI tools"
echo ""
