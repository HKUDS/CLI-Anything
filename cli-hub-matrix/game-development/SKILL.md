---
name: cli-hub-matrix-game-development
description: >-
  Capability-based multi-tool matrix for game development: engine, 3D/2D/audio assets,
  AI-generated assets, agent playtesting, packaging, store publishing, and telemetry.
---

# Game Development Matrix (S4 — v2 capability-based)

Scenario **S4**. All asset-creation capabilities covered via the S3/S5 stacks; the structural gap is **distribution** (Steam/itch/console stores) and alternative engines (Unity/Unreal).

Schema: [`docs/cli-matrix/matrix_registry.schema.md`](../../docs/cli-matrix/matrix_registry.schema.md). Matrix plan: [`docs/cli-matrix/cli-matrix-plan.md`](../../docs/cli-matrix/cli-matrix-plan.md).

## Install

```bash
cli-hub matrix install game-development
cli-hub matrix info    game-development
```

---

## Decision rubric

1. **Available & adequate** — ranked by quality then inverse cost.
2. **Free-to-install** — Python libs / native binaries without credentials.
3. **Harness / public CLI install** — when warranted.
4. **Paid API escalation** — only when lower tiers can't meet the bar, env holds the key, or the user consents.

---

## Preflight

```bash
cli-hub list --json
python - <<'PY'
import importlib.util
for m in ("pygame","arcade","panda3d","ursina","trimesh","pygltflib","PIL",
          "pydub","librosa","music21","mido","abjad","diffusers","replicate",
          "posthog","gymnasium"):
    print(m, importlib.util.find_spec(m) is not None)
PY
for b in godot blender aseprite butler steamcmd ffmpeg pyinstaller; do
  command -v "$b" >/dev/null && echo "$b: yes" || echo "$b: no"
done
for e in STEAM_USERNAME STEAM_PASSWORD ITCH_API_KEY EPIC_DEV_TOKEN \
         PLAY_CONSOLE_KEY APP_STORE_CONNECT_KEY \
         REPLICATE_API_TOKEN OPENAI_API_KEY STABILITY_API_KEY IDEOGRAM_API_KEY \
         POSTHOG_API_KEY GAMEANALYTICS_KEY PLAYFAB_TITLE_KEY SENTRY_DSN; do
  [ -n "${!e}" ] && echo "$e: set" || echo "$e: unset"
done
```

---

## Suggest-to-user template

```
To enable <capability> via <provider>, please set <ENV_VAR>.
  Cost: <cost notes>
  Quality: <quality tier>
Reply 'skip' to fall back to <next provider>.
```

Example: *To publish to Steam, please install `steamcmd` and set `STEAM_USERNAME` + `STEAM_PASSWORD` (a dedicated build account is strongly recommended). Cost: one-time $100 Steamworks fee. Reply 'skip' to fall back to itch.io via `butler` which only needs `ITCH_API_KEY`.*

---

## Capabilities

### `game.engine` — engine authoring / project manipulation

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-godot` | harness-cli | Godot installed | free | sota | yes |
| `pygame` | python | pkg | free | good | yes |
| `arcade` | python | pkg | free | good | yes |
| `panda3d` | python | pkg | free | high | yes |
| `ursina` | python | pkg | free | good | yes |
| Unity / Unreal | — | — | — | — | — |

### `asset.3d` — 3D game assets

See S3 matrix. Primary: `cli-anything-blender`, `cli-anything-freecad`, `trimesh`, `pygltflib`.

### `asset.2d` — sprites, tiles, UI art

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-krita` | harness-cli | Krita installed | free | sota | yes |
| `cli-anything-inkscape` | harness-cli | Inkscape installed | free | sota | yes |
| `Pillow` | python | pkg | free | good | yes |
| `aseprite` | native | binary (commercial) | paid | sota | yes |
| `pyxel` | python | pkg | free | good | yes |
| OpenAI GPT-Image-1 | api | `OPENAI_API_KEY` | metered | sota | no |
| Scenario GG | api | `SCENARIO_API_KEY` | paid | sota | no |
| Leonardo AI | api | `LEONARDO_API_KEY` | paid | high | no |

### `asset.audio` — sfx and gameplay audio

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-audacity` | harness-cli | Audacity | free | high | yes |
| `pydub` / `librosa` / `soundfile` | python | pkg | free | good | yes |
| `sfxr` / `jsfxr` | native | binary | free | good | yes |
| ElevenLabs SFX | api | `ELEVENLABS_API_KEY` | paid | sota | no |
| Mubert | api | `MUBERT_API_KEY` | metered | high | no |

### `asset.notation` — music notation / score export

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-musescore` | harness-cli | MuseScore installed | free | sota | yes |
| `music21` | python | pkg | free | high | yes |
| `mido` | python | pkg | free | good | yes |
| `abjad` | python | pkg | free | high | yes |

### `ai.gen-asset` — AI-generated art/audio for games

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-comfyui` | harness-cli | ComfyUI installed | free | high | yes |
| `jimeng` | public-cli | bin | metered | high | no |
| `diffusers` | python | pkg + weights | free | good | yes |
| `replicate` | python | `REPLICATE_API_TOKEN` | metered | high | no |
| Scenario GG | api | `SCENARIO_API_KEY` | paid | sota | no |
| Leonardo AI | api | `LEONARDO_API_KEY` | paid | high | no |
| OpenAI GPT-Image-1 | api | `OPENAI_API_KEY` | metered | sota | no |
| Stability | api | `STABILITY_API_KEY` | metered | high | no |

### `playtest.agent` — agent-driven play / testing

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-slay-the-spire-ii` | harness-cli | StS II + bridge mod | free | sota | yes |
| `gymnasium` envs | python | pkg | free | high | yes |
| Headless game + scripted input (e.g. Godot `--headless` with GUT) | harness-cli | Godot | free | good | yes |

Distinctive capability — very few agent stacks can drive a live GUI game loop.

### `build.package` — package a game binary / bundle

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-godot` (export presets) | harness-cli | Godot export templates | free | sota | yes |
| `pyinstaller` (pygame/arcade) | python | pkg | free | good | yes |
| `butler` (itch packager) | native | binary | free | high | yes |

### `publish.store` — upload a build to a store

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `steamcmd` | native | binary + Steam account + app ID | paid (fee) | sota | no |
| `butler` (itch.io) | native | binary + `ITCH_API_KEY` | free | high | no |
| Epic Games Services | api | `EPIC_DEV_TOKEN` | paid | high | no |
| Google Play Developer | api | `PLAY_CONSOLE_KEY` + service account | paid | high | no |
| App Store Connect | api | `APP_STORE_CONNECT_KEY` | paid | high | no |

**Known gap** — no harness-level abstraction; escalate via the suggest-to-user template with platform-specific preflight.

### `telemetry.ingest` — gameplay analytics / crash reports

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `sentry` | public-cli | bin + `SENTRY_DSN` | free-paid | high | no |
| `posthog` | python | pkg + `POSTHOG_API_KEY` | free-paid | high | no |
| GameAnalytics | api | `GAMEANALYTICS_KEY` | free | good | no |
| Unity Analytics | api | Unity project token | metered | high | no |
| PlayFab | api | `PLAYFAB_TITLE_KEY` | metered | high | no |

---

## Recipes

- **`godot-jam-game`** — minimal end-to-end for a game jam.
  Uses: `game.engine`, `asset.2d`, `asset.audio`, `build.package`, (optional `publish.store`).

- **`agent-bot`** — train / evaluate an agent against an existing game.
  Uses: `playtest.agent`, `telemetry.ingest`.

- **`ai-indie-short`** — AI-generated art + simple engine loop.
  Uses: `ai.gen-asset`, `asset.2d`, `game.engine`, `asset.audio`, `build.package`.

- **`steam-release`** — ship to Steam with crash reporting.
  Uses: `build.package`, `publish.store`, `telemetry.ingest`.

- **`music-driven-game`** — composed score integrated with gameplay.
  Uses: `asset.notation`, `asset.audio`, `game.engine`.

- **`reality-to-game`** — photogrammetry asset → import → ship.
  Uses: (S3 `photogrammetry.reconstruct`), `asset.3d`, `game.engine`, `build.package`.

---

## Known gaps

- **`publish.store`** — Steam/itch/console wrappers are native-only; escalate with explicit credentials.
- **`game.engine` for Unity/Unreal** — only Godot harness exists.
- **`telemetry.ingest`** — Sentry works; no first-party for GameAnalytics/PlayFab.
- **`asset.notation`** — uniquely strong (MuseScore) but rarely used in practice; keep as a differentiator.

---

## Agent guidance

- **Start in Godot** unless the user has explicitly asked for Unity/Unreal — it's the only engine we harness.
- **Keep asset pipelines deterministic** — re-runnable seeds for `ai.gen-asset`, versioned source `.aseprite`/`.krita` files, scriptable Blender bakes.
- **`playtest.agent` needs a bridge.** Most commercial games lack API access; agents should ask the user if modding is permitted before attempting.
- **Version builds immediately.** `build.package` output goes into `builds/<version>/` with a manifest so `publish.store` has deterministic uploads.
- **Don't auto-publish.** `publish.store` must always be gated behind explicit user confirmation — uploading a broken build is expensive to roll back.
