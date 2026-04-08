# STS2 Bridge Plugin

This directory contains the source code for `STS2_Bridge`, the in-game mod used
by the CLI-Anything Slay the Spire II harness.

The bridge runs inside the real Steam game process and exposes a local HTTP API
at `http://localhost:15526/api/v1/singleplayer`. The CLI in
`slay_the_spire_ii/agent-harness/` reads game state from that API and sends
actions back through it.

## What Is Here

- `build.sh`
  - Builds the `.NET 9` plugin against your local Slay the Spire II install.
- `bridge_manifest.json`
  - Manifest copied into the install bundle as `STS2_Bridge.json`.
- `docs/raw_api.md`
  - Raw bridge API notes.
- `../install/bridge_plugin/`
  - Project-local install bundle updated by `build.sh`.
- `../install/install_bridge.sh`
  - Copies the built bundle into the game's `mods/STS2_Bridge/` directory.

## Requirements

- `.NET 9 SDK`
- A local Steam install of Slay the Spire II

## Build

From the repository root:

```bash
cd slay_the_spire_ii/agent-harness/bridge/plugin
./build.sh
```

If auto-detection fails, pass the game data directory explicitly:

```bash
./build.sh "/Users/your_name/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64"
```

The build writes a fresh install bundle to:

```text
slay_the_spire_ii/agent-harness/bridge/install/bridge_plugin/
```

## Install Into The Game

From the repository root:

```bash
cd slay_the_spire_ii/agent-harness/bridge/install
./install_bridge.sh
```

This copies:

```text
STS2_Bridge.dll
STS2_Bridge.json
```

into:

```text
<game_install>/SlayTheSpire2.app/Contents/MacOS/mods/STS2_Bridge/
```

After that, launch the game and enable the `STS2_Bridge` mod.
