# Slay the Spire II CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 2 | 9 | Unit tests for action payload factories and normalized state mapping |
| `test_full_e2e.py` | 2 | 5 | CLI subprocess tests against a mocked local bridge server |
| **Total** | **4** | **14** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic state payloads and direct function calls. No game
process or network access is required.

### `TestActionAdapter` (4 tests)

- `play_card()` includes `target` only when provided
- `start_new_game()` preserves character and ascension
- `from_name()` dispatches to the correct factory
- `from_name()` rejects unknown action names

### `TestStateAdapter` (5 tests)

- Combat state normalizes to `combat_play`
- Shop state splits items into cards, relics, potions, and card removal
- Menu state exposes launcher capabilities
- Overlay state preserves overlay payload
- Unknown state falls back to `decision="unknown"` and includes raw payload

## E2E Tests (`test_full_e2e.py`)

These tests start a local fake HTTP server that mimics the bridge plugin API, so
they run without Slay the Spire II installed.

### `TestBridgeSubprocess` (4 tests)

- `--help` exits 0 and shows the CLI name
- `raw-state` returns the raw bridge JSON object
- `state` returns normalized JSON with the expected `decision`
- `action <name> --kv key=value` posts the expected body to the fake bridge

### `TestCommandSubprocess` (1 test)

- `continue-game` posts the action produced by `action_adapter.continue_game()`

## Realistic Workflow Scenarios

### Scenario 1: Inspect game state before acting

- **Simulates**: An agent polling the live game to decide its next move
- **Operations**: `raw-state` -> `state`
- **Verified**: Raw JSON is preserved, normalized JSON contains the expected decision

### Scenario 2: Send a bridge action from the CLI

- **Simulates**: An agent issuing a one-shot command during a run
- **Operations**: `action custom --kv floor=12 --kv urgent=true`
- **Verified**: The fake bridge receives the exact action payload and CLI exits 0

### Scenario 3: Trigger a typed action factory

- **Simulates**: An agent using a higher-level command rather than raw JSON
- **Operations**: `continue-game`
- **Verified**: The fake bridge receives `{"action": "continue_game"}`
