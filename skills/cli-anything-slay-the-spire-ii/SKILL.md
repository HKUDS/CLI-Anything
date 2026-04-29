---
name: "cli-anything-slay-the-spire-ii"
description: >-
  Command-line interface for Slay the Spire 2 - Control the real game through a local bridge mod HTTP API. Reads normalized game state and sends action commands for combat, navigation, rewards, and menu management.
---

# cli-anything-slay-the-spire-ii

A stateful command-line interface for controlling the real Slay the Spire 2
game through the local `STS2_Bridge` mod. The CLI reads normalized game state
and sends action commands via a local HTTP API at `localhost:15526`.

## Installation

This CLI requires a bridge mod that runs inside the game process. Both the CLI
and the bridge are distributed from the same repository:

```
https://github.com/HKUDS/CLI-Anything
```

### 1. Install the CLI

```bash
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything/slay_the_spire_ii/agent-harness
pip install -e .
```

### 2. Build and install the bridge mod

The bridge mod is a `.NET 9` plugin that must be compiled and installed into
the game directory. Full instructions are in the repository README, but the
short version is:

```bash
cd CLI-Anything/slay_the_spire_ii/agent-harness/bridge/plugin
./build.sh
cd ../install
./install_bridge.sh
```

If the build script cannot auto-detect the game data directory, set
`STS2_GAME_DATA_DIR` explicitly:

```bash
STS2_GAME_DATA_DIR="/path/to/data_sts2" ./build.sh
```

### 3. Enable the mod and verify

Launch Slay the Spire 2 via Steam, enable the `STS2_Bridge` mod in the mod
manager, then verify the connection:

```bash
cli-anything-sts2 state
```

If this returns JSON, the CLI and bridge are connected.

**Prerequisites:**
- Python 3.10+
- Slay the Spire 2 (Steam) with `STS2_Bridge` mod enabled
- `.NET 9 SDK` (only needed to build the bridge mod)

## Usage

### Basic Commands

```bash
# Read normalized game state (always start here)
cli-anything-sts2 state

# Start interactive REPL mode (default)
cli-anything-sts2

# Show all available commands
cli-anything-sts2 --help
```

## Command Groups

### State Inspection

| Command | Description |
|---------|-------------|
| `state` | Normalized state with `decision` field |
| `raw-state` | Raw bridge JSON |

### Main Menu

| Command | Description |
|---------|-------------|
| `continue-game` | Continue a saved run |
| `start-game --character IRONCLAD --ascension 0` | Start a new run |
| `abandon-game` | Abandon the current save |
| `return-to-main-menu` | Return to menu from any screen |

Characters: `IRONCLAD`, `SILENT`, `DEFECT`, `NECROBINDER`, `REGENT`

### Combat

| Command | Description |
|---------|-------------|
| `play-card <index> [--target <enemy_id>]` | Play a card from hand |
| `use-potion <slot> [--target <enemy_id>]` | Use a potion |
| `end-turn` | End the current turn |

### Map & Room Flow

| Command | Description |
|---------|-------------|
| `choose-map <index>` | Select a map node |
| `proceed` | Leave the current room |

### Rewards

| Command | Description |
|---------|-------------|
| `claim-reward <index>` | Claim a combat reward |
| `pick-card-reward <index>` | Pick a card reward |
| `skip-card-reward` | Skip the card reward |
| `claim-treasure-relic <index>` | Claim a treasure relic |
| `select-relic <index>` | Select a relic |
| `skip-relic-selection` | Skip relic selection |

### Events & Rest Sites

| Command | Description |
|---------|-------------|
| `event <index>` | Choose an event option |
| `advance-dialogue` | Advance dialogue-only events |
| `rest <index>` | Choose a campfire action |

### Shop

| Command | Description |
|---------|-------------|
| `shop-buy <index>` | Buy from the shop |

### Card/Relic Selection Overlays

| Command | Description |
|---------|-------------|
| `select-card <index>` | Select a card in overlay |
| `confirm-selection` | Confirm the current selection |
| `cancel-selection` | Cancel the current selection |
| `combat-select-card <index>` | Select a card during combat overlay |
| `combat-confirm-selection` | Confirm combat card selection |

### Raw Action

| Command | Description |
|---------|-------------|
| `action <name> --kv key=value` | Send a raw bridge action |

## Decision States

The `state` command returns JSON with a `decision` field indicating the current
game screen. Route your next command based on this value:

| Decision | Meaning | Typical Next Commands |
|----------|---------|----------------------|
| `menu` | Main menu | `continue-game`, `start-game` |
| `combat_play` | In combat, your turn | `play-card`, `use-potion`, `end-turn` |
| `hand_select` | Card selection overlay | `combat-select-card`, `combat-confirm-selection` |
| `map_select` | Map node selection | `choose-map` |
| `game_over` | Run ended | `return-to-main-menu` |
| `combat_rewards` | Post-combat rewards | `claim-reward`, `proceed` |
| `card_reward` | Card reward pick | `pick-card-reward`, `skip-card-reward` |
| `event_choice` | Event screen | `event`, `advance-dialogue` |
| `rest_site` | Campfire | `rest` |
| `shop` | Shop screen | `shop-buy`, `proceed` |
| `card_select` | Card selection screen | `select-card`, `confirm-selection` |
| `relic_select` | Relic selection | `select-relic`, `skip-relic-selection` |
| `treasure` | Treasure room | `claim-treasure-relic`, `proceed` |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--base-url` | `http://localhost:15526` | Bridge API URL |
| `--timeout` | `10.0` | HTTP timeout in seconds |

## For AI Agents

1. **Always read `state` first** to get the `decision` field
2. **Re-read state after each action** - indices and energy change during combat
3. **Check return codes** - 0 for success, non-zero for errors
4. **Parse stdout** for JSON output
