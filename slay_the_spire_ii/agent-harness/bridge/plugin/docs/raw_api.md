# Raw API Reference

These API endpoints are available for direct HTTP requests *without* using the MCP server. For example, you can use `curl` or Postman to interact with the mod directly.

The mod exposes two endpoints:
- `http://localhost:15526/api/v1/singleplayer` — for singleplayer runs
- `http://localhost:15526/api/v1/multiplayer` — for multiplayer (co-op) runs

The endpoints are mutually exclusive: calling the singleplayer endpoint during a multiplayer run (or vice versa) returns HTTP 409.

:::note
These endpoints are designed for local use and do not have authentication or security measures, so they should not be exposed publicly - unless you know what you're doing!
:::

## `GET /api/v1/singleplayer`

Query parameters:
| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `format`  | `json`, `markdown` | `json` | Response format |

Returns the current game state. The `state_type` field indicates the screen:
- `monster` / `elite` / `boss` — In combat (full battle state returned)
- `hand_select` — In-combat card selection prompt (exhaust, discard, etc.) with battle state
- `combat_rewards` — Post-combat rewards screen (reward items, proceed button)
- `card_reward` — Card reward selection screen (card choices, skip option)
- `map` — Map navigation screen (full DAG, next options with lookahead, visited path)
- `rest_site` — Rest site (available options: rest, smith, etc.)
- `shop` — Shop (full inventory: cards, relics, potions, card removal with costs)
- `event` — Event or Ancient (options with descriptions, ancient dialogue detection)
- `card_select` — Deck card selection (transform, upgrade, remove, discard) or choose-a-card (potions, effects)
- `relic_select` — Relic choice screen (boss relics, immediate pick + skip)
- `treasure` — Treasure room (chest auto-opens, relic claiming)
- `overlay` — Catch-all for unhandled overlay screens (prevents soft-locks)
- `menu` — No run in progress

### State details

**Battle state includes:**
- Player: HP, block, energy, stars (Regent), gold, character, status, relics, potions, hand (with card details including star costs), pile counts, pile contents, orbs
- Enemies: entity_id, name, HP, block, status, intents with title/label/description
- Keywords on all entities (cards, relics, potions, status)

**Hand select state includes:**
- Mode: `simple_select` (exhaust/discard) or `upgrade_select` (in-combat upgrade)
- Prompt text (e.g., "Select a card to Exhaust.")
- Selectable cards: index, id, name, type, cost, description, upgrade status, keywords
- Already-selected cards (if multi-select): index, name
- Confirm button state
- Full battle state is also included for combat context

**Rewards state includes:**
- Player summary: character, HP, gold, potion slot availability
- Reward items: index, type (`gold`, `potion`, `relic`, `card`, `special_card`, `card_removal`), description, and type-specific details (gold amount, potion id/name)
- Proceed button state

**Event state includes:**
- Event metadata: id, name, whether it's an Ancient, dialogue phase status
- Player summary: character, HP, gold
- Options: index, title, description, locked/proceed/chosen status, attached relic (for Ancients), keywords

**Rest site state includes:**
- Player summary: character, HP, gold
- Available options: index, id, name, description, enabled status
- Proceed button state

**Shop state includes:**
- Player summary: character, HP, gold, potion slot availability
- Full inventory by category: cards (with details, cost, on_sale, keywords), relics (with keywords), potions (with keywords), card removal
- Each item: index, cost, stocked status, affordability
- Shop inventory is auto-opened when state is queried

**Map state includes:**
- Player summary: character, HP, gold, potion slot availability
- Current position and visited path
- Next options: index, coordinate, node type, with 1-level lookahead (children types)
- Full map DAG: all nodes with coordinates, types, and edges (children)

**Card select state includes:**
- Screen type: `transform`, `upgrade`, `select`, `simple_select`, `choose`
- Player summary: character, HP, gold
- Prompt text (e.g., "Choose 2 cards to Transform.")
- Cards: index, id, name, type, cost, description, rarity, upgrade status, keywords
- Preview state, confirm/cancel button availability
- For `choose` type (e.g., Colorless Potion): immediate pick on select, skip availability

**Relic select state includes:**
- Prompt text
- Player summary: character, HP, gold
- Relics: index, id, name, description, keywords
- Skip availability

**Card reward state includes:**
- Card choices: index, id, name, type, energy cost, star cost (Regent), description, rarity, upgrade status, keywords
- Skip availability

**Treasure state includes:**
- Player summary: character, HP, gold
- Relics: index, id, name, description, rarity, keywords
- Proceed button state
- Chest is auto-opened when state is queried

## `POST /api/v1/singleplayer`

**Play a card:**
```json
{
  "action": "play_card",
  "card_index": 0,
  "target": "jaw_worm_0"
}
```
- `card_index`: 0-based index in hand (from GET response)
- `target`: entity_id of the target (required for `AnyEnemy` cards, omit for self-targeting/AoE cards)

**Use a potion:**
```json
{
  "action": "use_potion",
  "slot": 0,
  "target": "jaw_worm_0"
}
```
- `slot`: potion slot index (from GET response)
- `target`: entity_id of the target (required for `AnyEnemy` potions, omit otherwise)

**End turn:**
```json
{ "action": "end_turn" }
```

**Select a card from hand during combat selection:**
```json
{ "action": "combat_select_card", "card_index": 0 }
```
- `card_index`: 0-based index of the card in the selectable hand (from GET response)
- Used when a card effect prompts "Select a card to exhaust/discard/etc."

**Confirm in-combat card selection:**
```json
{ "action": "combat_confirm_selection" }
```
- Confirms the current in-combat hand card selection
- Only works when the confirm button is enabled (enough cards selected)

**Claim a reward:**
```json
{ "action": "claim_reward", "index": 0 }
```
- `index`: 0-based index of the reward on the rewards screen (from GET response)
- Gold, potion, and relic rewards are claimed immediately
- Card rewards open the card selection screen (state changes to `card_reward`)

**Select a card reward:**
```json
{ "action": "select_card_reward", "card_index": 1 }
```
- `card_index`: 0-based index of the card to add to the deck (from GET response)

**Skip card reward:**
```json
{ "action": "skip_card_reward" }
```

**Proceed:**
```json
{ "action": "proceed" }
```
- Proceeds from the current screen to the map
- Works from: rewards screen, rest site, shop (auto-closes inventory), treasure room
- Does NOT work for events — use `choose_event_option` with the Proceed option's index

**Choose a rest site option:**
```json
{ "action": "choose_rest_option", "index": 0 }
```
- `index`: 0-based index of the enabled option (from GET response)
- Options include Rest (heal), Smith (upgrade a card), and relic-granted options

**Purchase a shop item:**
```json
{ "action": "shop_purchase", "index": 0 }
```
- `index`: 0-based index of the item in the shop inventory (from GET response)
- Item must be stocked and affordable
- Shop inventory is auto-opened if not already open

**Choose an event option:**
```json
{ "action": "choose_event_option", "index": 0 }
```
- `index`: 0-based index of the unlocked option (from GET response)
- Works for both regular events and ancients (after dialogue)

**Advance ancient dialogue:**
```json
{ "action": "advance_dialogue" }
```
- Clicks through dialogue text in ancient events
- Call repeatedly until `in_dialogue` becomes `false` and options appear

**Choose a map node:**
```json
{ "action": "choose_map_node", "index": 0 }
```
- `index`: 0-based index from the `next_options` array in the map state
- Node types: Monster, Elite, Boss, RestSite, Shop, Treasure, Unknown, Ancient

**Select a card in the selection screen:**
```json
{ "action": "select_card", "index": 0 }
```
- `index`: 0-based index of the card in the grid (from GET response)
- For grid screens (transform, upgrade, select): toggles selection. When enough cards are selected, a preview may appear automatically
- For choose-a-card screens (potions, effects): picks immediately

**Confirm card selection:**
```json
{ "action": "confirm_selection" }
```
- Confirms the current selection (from preview or main confirm button)
- Works with upgrade previews (single and multi), transform previews, and generic confirm buttons
- Not needed for choose-a-card screens where picking is immediate

**Cancel card selection:**
```json
{ "action": "cancel_selection" }
```
- If a preview is showing (upgrade/transform), goes back to the selection grid
- For choose-a-card screens, clicks the skip button (if available)
- Otherwise, closes the card selection screen (only if cancellation is allowed)

**Select a relic:**
```json
{ "action": "select_relic", "index": 0 }
```
- `index`: 0-based index of the relic (from GET response)
- Used for boss relic selection. Pick is immediate.

**Skip relic selection:**
```json
{ "action": "skip_relic_selection" }
```

**Claim a treasure relic:**
```json
{ "action": "claim_treasure_relic", "index": 0 }
```
- `index`: 0-based index of the relic (from GET response)
- Chest is auto-opened when state is queried; this claims a revealed relic

### Error responses

All errors return:
```json
{
  "status": "error",
  "error": "Description of what went wrong"
}
```

---

## `GET /api/v1/multiplayer`

Query parameters:
| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `format`  | `json`, `markdown` | `json` | Response format |

Returns the multiplayer game state. Shares the same `state_type` values as singleplayer, with these additions:

**Additional top-level fields:**
- `game_mode`: always `"multiplayer"`
- `net_type`: network service type (e.g., `"SteamMultiplayer"`)
- `player_count`: number of players in the run
- `local_player_slot`: index of the local player in the players array
- `players`: summary of all players (character, HP, gold, alive status, local flag)

**Battle state additions:**
- `all_players_ready`: whether all players have submitted end turn
- `players[]`: full state for the local player, summary (HP, block, energy, status, relics, potions) for others
- Each player entry includes `is_local`, `is_alive`, and `is_ready_to_end_turn`

**Map state additions:**
- `votes[]`: per-player map node votes (`player`, `is_local`, `voted`, `vote_col`, `vote_row`)
- `all_voted`: whether all players have voted

**Event state additions:**
- `is_shared`: whether the event is a shared vote
- `votes[]` (shared events only): per-player option votes
- `all_voted`: whether all players have voted

**Treasure state additions:**
- `is_bidding_phase`: whether relics are revealed and bidding is active
- `bids[]`: per-player relic bids (`player`, `is_local`, `voted`, `vote_relic_index`)
- `all_bid`: whether all players have bid
- Chest is auto-opened when state is queried (same as singleplayer)

## `POST /api/v1/multiplayer`

Supports all the same actions as the singleplayer endpoint (play_card, use_potion, choose_map_node, etc.), plus these multiplayer-specific actions:

**End turn (vote):**
```json
{ "action": "end_turn" }
```
- In multiplayer, this is a vote — the turn only ends when ALL players submit
- Returns an error if already submitted (use `undo_end_turn` to retract first)

**Undo end turn:**
```json
{ "action": "undo_end_turn" }
```
- Retracts the end-turn vote so the player can continue playing cards
- Only works if the turn hasn't actually ended yet (i.e., not all players committed)

All other actions (`play_card`, `use_potion`, `choose_map_node`, `choose_event_option`, etc.) work identically to their singleplayer counterparts but are routed through multiplayer sync.
