#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$SCRIPT_DIR/STS2_Bridge.csproj"
OUT_DIR="$SCRIPT_DIR/out/STS2_Bridge"
CONFIGURATION="${CONFIGURATION:-Release}"
DOTNET_CLI_HOME="${DOTNET_CLI_HOME:-$SCRIPT_DIR/.dotnet-cli-home}"
INSTALL_DIR="$SCRIPT_DIR/../install/bridge_plugin"

mkdir -p "$DOTNET_CLI_HOME"
mkdir -p "$INSTALL_DIR"
export DOTNET_CLI_HOME
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

find_dotnet() {
  if [ -x "$HOME/.dotnet-arm64/dotnet" ]; then
    echo "$HOME/.dotnet-arm64/dotnet"
    return
  fi
  if [ -x "$HOME/.dotnet/dotnet" ]; then
    echo "$HOME/.dotnet/dotnet"
    return
  fi
  if command -v dotnet >/dev/null 2>&1; then
    command -v dotnet
    return
  fi
  return 1
}

detect_game_data_dir() {
  if [ -n "${STS2_GAME_DATA_DIR:-}" ] && [ -d "${STS2_GAME_DATA_DIR}" ]; then
    echo "${STS2_GAME_DATA_DIR}"
    return
  fi

  local base="$HOME/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources"
  local arm="$base/data_sts2_macos_arm64"
  local x64="$base/data_sts2_macos_x86_64"

  if [ -d "$arm" ]; then
    echo "$arm"
    return
  fi
  if [ -d "$x64" ]; then
    echo "$x64"
    return
  fi
  return 1
}

DOTNET_BIN="$(find_dotnet || true)"
if [ -z "$DOTNET_BIN" ]; then
  echo "ERROR: dotnet not found. Install .NET 9 SDK first." >&2
  exit 1
fi

GAME_DATA_DIR="${1:-$(detect_game_data_dir || true)}"
if [ -z "$GAME_DATA_DIR" ]; then
  echo "ERROR: Could not detect Slay the Spire 2 data directory." >&2
  echo "Usage: ./build.sh /path/to/data_sts2_macos_arm64" >&2
  exit 1
fi

if [ ! -f "$GAME_DATA_DIR/sts2.dll" ]; then
  echo "ERROR: sts2.dll not found in $GAME_DATA_DIR" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "Building STS2_Bridge"
echo "dotnet      : $DOTNET_BIN"
echo "game data   : $GAME_DATA_DIR"
echo "output dir  : $OUT_DIR"
echo

"$DOTNET_BIN" build "$PROJECT" \
  -c "$CONFIGURATION" \
  -o "$OUT_DIR" \
  -p:STS2GameDataDir="$GAME_DATA_DIR"

cp "$OUT_DIR/STS2_Bridge.dll" "$INSTALL_DIR/STS2_Bridge.dll"
cp "$SCRIPT_DIR/bridge_manifest.json" "$INSTALL_DIR/STS2_Bridge.json"

echo
echo "Build succeeded."
echo "Install these files into <game_install>/mods/:"
echo "  $OUT_DIR/STS2_Bridge.dll"
echo "  $SCRIPT_DIR/bridge_manifest.json  ->  STS2_Bridge.json"
echo
echo "Project-local install bundle updated at:"
echo "  $INSTALL_DIR/STS2_Bridge.dll"
echo "  $INSTALL_DIR/STS2_Bridge.json"
