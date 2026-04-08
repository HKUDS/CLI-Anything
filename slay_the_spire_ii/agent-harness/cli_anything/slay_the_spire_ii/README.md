# cli-anything-slay-the-spire-ii

A stateful command-line interface for controlling the real Slay the Spire 2
game through the local `STS2_Bridge` mod. Reads normalized game state and
sends action commands via a local HTTP API.

## Installation

This CLI is installed as part of the cli-anything-slay-the-spire-ii package:

```bash
pip install cli-anything-slay-the-spire-ii
```

**Prerequisites:**
- Python 3.10+
- Slay the Spire 2 (Steam) with `STS2_Bridge` mod installed and enabled
- The bridge mod listening on `http://localhost:15526`

## Usage

### Basic Commands

```bash
# Show help
cli-anything-sts2 --help

# Start interactive REPL mode (default)
cli-anything-sts2

# Read normalized game state
cli-anything-sts2 state

# Read raw bridge JSON
cli-anything-sts2 raw-state
```

### REPL Mode

Run `cli-anything-sts2` with no subcommand to enter the interactive REPL. The
explicit `repl` subcommand still works too:

```bash
cli-anything-sts2
# Enter commands interactively:
# > slay_the_spire_ii [http://localhost:15526] ❯ state
# > slay_the_spire_ii [http://localhost:15526] ❯ play-card 0 --target jaw_worm_0
# > slay_the_spire_ii [http://localhost:15526] ❯ end-turn
```

## Command Groups

### State Inspection

| Command | Description |
|---------|-------------|
| `state` | Print normalized game state with `decision` field |
| `raw-state` | Print raw bridge-plugin JSON |

### Main Menu

| Command | Description |
|---------|-------------|
| `continue-game` | Continue a saved run |
| `start-game --character IRONCLAD --ascension 0` | Start a new run |
| `abandon-game` | Abandon the current save |
| `return-to-main-menu` | Return to the main menu |

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
| `shop-buy <index>` | Buy an item from the shop |

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
| `action <name> --kv key=value` | Send a raw action with payload |

## Examples

### Start a New Run

```bash
cli-anything-sts2 start-game --character IRONCLAD --ascension 0
cli-anything-sts2 state
```

### Play Through Combat

```bash
cli-anything-sts2 state                          # Check game state
cli-anything-sts2 play-card 0 --target jaw_worm_0  # Play first card
cli-anything-sts2 state                          # Re-check after play
cli-anything-sts2 end-turn                       # End turn
```

### Navigate Map and Events

```bash
cli-anything-sts2 choose-map 0                   # Pick a map node
cli-anything-sts2 event 1                        # Choose event option
cli-anything-sts2 rest 0                         # Rest at campfire
```

### Interactive REPL Session

```bash
cli-anything-sts2
# > slay_the_spire_ii [http://localhost:15526] ❯ state
# > slay_the_spire_ii [http://localhost:15526] ❯ play-card 2
# > slay_the_spire_ii [http://localhost:15526] ❯ end-turn
# > slay_the_spire_ii [http://localhost:15526] ❯ exit
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--base-url` | `http://localhost:15526` | Bridge API URL |
| `--timeout` | `10.0` | HTTP timeout in seconds |

## Architecture

```
cli_anything/slay_the_spire_ii/
├── __init__.py
├── __main__.py                  # python3 -m cli_anything.slay_the_spire_ii
├── slay_the_spire_ii_cli.py     # CLI entry point (Click + default REPL)
├── core/
│   ├── __init__.py
│   ├── action_adapter.py        # Action payload factories
│   ├── state_adapter.py         # Raw → normalized state mapping
│   └── types.py                 # JsonDict, PlannedAction
├── utils/
│   ├── __init__.py
│   ├── sts2_backend.py          # HTTP client for the bridge API
│   └── repl_skin.py             # Shared REPL interface
└── skills/
    └── SKILL.md                 # Skill definition for AI agents
```

## For AI Agents

When using this CLI programmatically:

1. **Always read `state` first** to get the current `decision` field
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stdout** for JSON output
4. **Re-read state after each action** - hand indices and energy change during combat
5. **Use absolute paths** for any file operations

## More Information

- Architecture: See STS2.md in the agent-harness root
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0
