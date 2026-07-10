# Evaluation Pipeline — cli-anything-rekordbox

## Smoke
`pytest cli_anything/rekordbox/tests/`

## Manual integration (requires Rekordbox 6/7 installed)
1. `cli-anything-rekordbox status` → expect non-zero `track_count`
2. `cli-anything-rekordbox library search "Demo"` → expect default Pioneer demo tracks
3. `cli-anything-rekordbox playlist create eval-test` → expect `created`
4. `cli-anything-rekordbox playlist add eval-test --track-title "Demo Track 1"` → expect `added`
5. `cli-anything-rekordbox playlist clear eval-test` → expect removed > 0

## MIDI integration (requires virtual MIDI port + rekordbox open + mapping enabled)
6. `cli-anything-rekordbox install-mapping` → expect at least one path written
7. (manual) Enable LoopBe Internal MIDI in rekordbox prefs
8. `cli-anything-rekordbox deck eq --deck 1 --hi 0.5 --mid 0.5 --lo 0.5 --port LoopBe`
9. Observe in rekordbox: deck 1 EQ knobs set to noon
