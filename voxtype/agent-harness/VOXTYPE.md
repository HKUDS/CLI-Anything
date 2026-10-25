# VOXTYPE.md — Software-Specific SOP

## Software

**Voxtype** (<https://voxtype.io>, source: <https://github.com/peteonrails/voxtype>)
is a push-to-talk voice-to-text daemon for Linux (Wayland-first, X11 too). It is a
Rust binary: a hotkey or compositor keybinding starts recording, audio is captured
via cpal (PipeWire/PulseAudio/ALSA), transcribed by a local ASR engine
(whisper.cpp by default; Parakeet/Moonshine/SenseVoice/... via ONNX features),
post-processed (replacements, spoken punctuation, filler filtering) and typed into
the focused window (wtype → dotool → ydotool → clipboard fallback chain).

Its "GUI" surfaces are the interactive configuration TUI (`voxtype configure`), the
OSD overlay, the Waybar/Quickshell status widgets and the global hotkey. This
harness gives agents structured, headless control over everything those surfaces do.

## Phase 1 — Codebase Analysis

### Backend engine

| Layer | Source | Notes |
|-------|--------|-------|
| CLI (clap) | `src/cli/*.rs` | `daemon`, `transcribe`, `setup`, `config`, `info`, `status`, `record`, `meeting`, `check-update` |
| Config | `src/config/*.rs`, `src/config/schema.rs` | TOML at `~/.config/voxtype/config.toml`; 187 allowlisted dotted keys with types and ranges |
| Config mutation | `src/config_set.rs` | `toml_edit`-based, comment-preserving, atomic + validated (same code the TUI uses) |
| Daemon state | `src/state.rs`, `src/status_json.rs` | Idle → Recording → Transcribing → Outputting; state file in `$XDG_RUNTIME_DIR/voxtype/state` |
| Record control | `src/cli/record.rs` | `record start/stop/toggle/cancel` → SIGUSR1/SIGUSR2 + override files to the daemon PID |
| Transcription | `src/transcribe/*`, `src/app/transcribe_file.rs` | `voxtype transcribe FILE.wav` runs VAD + engine + text pipeline |
| Meetings | `src/meeting/*` | SQLite index `meetings/index.db` + per-meeting dir with `metadata.json` / `transcript.json`; exporters txt/md/json/srt/vtt |
| Setup | `src/setup/*` | model download (NDJSON progress), GPU, systemd, VAD, compositor |

### GUI action → CLI mapping

| GUI / interactive action | voxtype CLI | Harness command |
|--------------------------|-------------|-----------------|
| TUI: edit a setting | `voxtype config set KEY VALUE` | `config set KEY VALUE` (+ undo/redo) |
| TUI: reset a setting | `voxtype config unset KEY` | `config unset KEY` |
| TUI: browse settings | `voxtype config schema --json` | `config schema [--section]` / `config keys` |
| TUI: engine/model picker | `voxtype info models --json`, `setup --download --model` | `info models`, `setup download MODEL` |
| TUI: device picker | `voxtype info devices --json` | `info devices` |
| Hotkey press/release | `voxtype record start/stop` | `daemon record start/stop/toggle/cancel` |
| Waybar widget | `voxtype status --format json --extended` | `daemon status` |
| systemd tray / restart | `systemctl --user ... voxtype` | `daemon service status/start/stop/restart` |
| Meeting mode panel | `voxtype meeting ...` | `meeting ...` |
| "Transcribe this file" | `voxtype transcribe FILE` | `transcribe file` / `transcribe batch` |

### Data model

- **Config**: TOML file. All harness writes go through `voxtype config set/unset`
  (never hand-edited) so comments survive and invalid values are rejected by the
  real validator (exit 2 = user error, exit 1 = I/O).
- **Meetings**: `index.db` (tables `meetings`, `speaker_labels`) + directory per
  meeting. The harness *reads* the index directly (voxtype's `meeting list` has no
  JSON mode) and *writes* only when importing pre-recorded audio as a new meeting,
  using exactly the schema voxtype creates. All exports/labels go through voxtype.

### Undo system

Voxtype has no undo. The harness adds one at the config layer: before every
`config set/unset` it records the key's literal `file_value` (from
`voxtype config get KEY --json`); undo restores it via `config set` (or `unset`
when the key was absent).

## Phase 2 — CLI Architecture

### State model ("project" = workspace)

A workspace JSON file (`--project ws.json`) holds:

```json
{
  "format": "cli-anything-voxtype/workspace-v1",
  "name": "dictation-tuning",
  "config_path": "/path/to/config.toml",   // null = voxtype's default resolution
  "overrides": {"language": "en", "model": "base.en"},  // per-run transcribe flags
  "history": [ {op, key, old, new, ts} ],   // config mutations (undo stack)
  "redo": [],
  "transcriptions": [ {file, text, duration_secs, ...} ]
}
```

One-shot mutations auto-save the workspace; `--dry-run` skips the save **and**
applies config changes to a scratch copy of the config so voxtype still validates
them without touching the real file.

### Command groups

| Group | Commands |
|-------|----------|
| `project` | `new`, `info`, `set-config`, `override`, `clear-overrides` |
| `config` | `show`, `get`, `set`, `unset`, `schema`, `keys`, `path`, `replace` (word replacements) |
| `transcribe` | `file`, `batch`, `history`, `export` |
| `meeting` | `list`, `show`, `export`, `delete`, `label`, `summarize`, `import`, `start`, `stop`, `pause`, `resume`, `status` |
| `daemon` | `status`, `record start/stop/toggle/cancel`, `service status/start/stop/restart`, `accel` |
| `info` | `version`, `engines`, `models`, `devices`, `variants`, `styles` |
| `setup` | `check`, `download`, `set-model`, `vad` |
| `session` | `status`, `history`, `undo`, `redo` |
| `repl` | interactive mode (default with no subcommand) |

All commands accept the global `--json` flag.

### Rendering / backend rule

The harness never transcribes, validates config, or formats meeting exports
itself. Every one of those calls `/usr/bin/voxtype` (override with `$VOXTYPE_BIN`).
Non-WAV or non-16 kHz audio is normalized with `ffmpeg` to 16 kHz mono PCM before
being handed to `voxtype transcribe` (voxtype only reads WAV).

### Safety

- `daemon record start` makes the live daemon capture the microphone and type text
  into the focused window. Agents should prefer `--clipboard` or `--file`.
- `meeting delete` always passes `--force` to voxtype (no TTY prompt); the harness
  requires `--yes`.
