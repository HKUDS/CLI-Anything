#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$SCRIPT_DIR/bridge_plugin"
DLL="$BUNDLE_DIR/STS2_Bridge.dll"
JSON="$BUNDLE_DIR/STS2_Bridge.json"

if [ ! -f "$DLL" ] || [ ! -f "$JSON" ]; then
  echo "ERROR: bridge plugin files not found in $BUNDLE_DIR" >&2
  echo "Build the bridge first: ../plugin/build.sh" >&2
  exit 1
fi

GAME_ROOT="${1:-$HOME/Library/Application Support/Steam/steamapps/common/Slay the Spire 2}"
MOD_DIR="$GAME_ROOT/SlayTheSpire2.app/Contents/MacOS/mods/STS2_Bridge"

mkdir -p "$MOD_DIR"
cp "$DLL" "$MOD_DIR/STS2_Bridge.dll"
cp "$JSON" "$MOD_DIR/STS2_Bridge.json"

echo "Installed bridge plugin to:"
echo "  $MOD_DIR/STS2_Bridge.dll"
echo "  $MOD_DIR/STS2_Bridge.json"
