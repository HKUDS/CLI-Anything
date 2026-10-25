---
name: "cli-anything-voxtype"
description: >-
  Command-line interface for Voxtype, the push-to-talk voice-to-text daemon for Linux.
  Use it to transcribe audio files, read and change voxtype settings (validated by voxtype,
  with undo/redo), build and export meeting transcripts (srt/vtt/json/markdown) with
  speaker labels, and check or control the running daemon, all with --json output.
---

# cli-anything-voxtype

Structured, headless control of [Voxtype](https://voxtype.io). Every operation calls the
real `voxtype` binary: settings are validated by voxtype's own schema, transcription runs
voxtype's engine and text pipeline, and meeting exports use voxtype's exporters.

## Installation

```bash
pip install cli-anything-voxtype      # or: pip install -e voxtype/agent-harness
```

**Prerequisites (hard dependencies):**
- Python 3.10+
- `voxtype` ≥ 1.1 on PATH (or `$VOXTYPE_BIN`): `yay -S voxtype-bin`, or packages from https://voxtype.io
- At least one model: `voxtype setup --download --model base.en`
- `ffmpeg`, for non-WAV input: `pacman -S ffmpeg` / `apt install ffmpeg`

## Usage

```bash
cli-anything-voxtype --help                 # all groups
cli-anything-voxtype                        # interactive REPL
cli-anything-voxtype --json daemon status   # cheap state probe
```

Global options (put them **before** the subcommand):

| Option | Meaning |
|--------|---------|
| `--json` | JSON on stdout, including errors: `{"error", "type", "returncode"}` |
| `--project FILE` | Workspace: target config file, transcription overrides, undo history. Auto-saved after each one-shot command. |
| `--config FILE` | voxtype `config.toml` to operate on (takes precedence over the workspace's) |
| `--dry-run` | Validate config changes against a scratch copy; write nothing |

Exit codes: `0` ok · `1` runtime/I/O error · `2` invalid key or value (from voxtype).

## Command Groups

### Project

Workspace management (config target, transcription overrides, history).

| Command | Description |
|---------|-------------|
| `new` | Create a new workspace file. |
| `info` | Show the open workspace. |
| `set-config` | Point the workspace at a voxtype config file. |
| `override` | Pin a transcription flag for this workspace (model, language, vad, ...); no KEY lists them. |
| `clear-overrides` | Remove every transcription override. |

### Config

Read and change voxtype settings (validated by voxtype).

| Command | Description |
|---------|-------------|
| `path` | Show which config file is in use. |
| `show` | Print the resolved configuration. |
| `get` | Print one key's effective value (and its literal file value). |
| `set` | Set KEY to VALUE (undoable inside a workspace). |
| `unset` | Remove KEY from the config file, restoring its default. |
| `schema` | Describe settable keys: type, choices, ranges, current value. |
| `sections` | List schema sections and key counts. |

### Config Replace

Word replacements applied to every transcript (text.replacements).

| Command | Description |
|---------|-------------|
| `list` | List spoken → written replacements. |
| `add` | Replace SPOKEN with WRITTEN in transcripts. |
| `remove` | Remove a replacement. |

### Transcribe

Transcribe audio files with voxtype's engine and text pipeline.

| Command | Description |
|---------|-------------|
| `file` | Transcribe one audio file (any format ffmpeg reads). |
| `batch` | Transcribe many files, directories or globs. |
| `history` | Show transcriptions recorded in the workspace. |
| `export` | Export the workspace's transcription history. |
| `clear` | Forget the workspace's transcription history. |

### Meeting

Meeting transcripts: list, export, label speakers, import audio.

| Command | Description |
|---------|-------------|
| `list` | List stored meetings (newest first). |
| `show` | Show a meeting (ID, unique prefix, or 'latest'). |
| `export` | Export a meeting transcript via voxtype's exporters. |
| `label` | Name a speaker (SPEAKER_00 or 0) in a meeting. |
| `delete` | Delete a meeting and its files. |
| `summarize` | AI summary via voxtype (needs Ollama or a remote API configured). |
| `import` | Create a meeting from pre-recorded audio files (transcribed by voxtype). |
| `start` | Start live meeting transcription (daemon). |
| `stop` | Stop the live meeting. |
| `pause` | Pause the live meeting. |
| `resume` | Resume the live meeting. |
| `status` | Live meeting status. |

### Daemon

The running voxtype daemon: status, recording, service.

| Command | Description |
|---------|-------------|
| `status` | Daemon state (idle/recording/transcribing/stopped), model, device. |
| `service` | systemd user service control. |
| `accel` | Is the running daemon GPU-accelerated? |

### Daemon Record

Control recording (like the hotkey). start/toggle capture the mic!

| Command | Description |
|---------|-------------|
| `start` | Start recording. |
| `toggle` | Toggle recording. |
| `stop` | Stop recording and transcribe. |
| `cancel` | Cancel recording/transcription without output. |

### Info

Install and runtime information.

| Command | Description |
|---------|-------------|
| `version` | voxtype and harness versions. |
| `engines` | Transcription engines and which are compiled in. |
| `models` | Downloadable and installed models. |
| `devices` | Audio capture devices. |
| `variants` | Installed binary variants. |
| `styles` | Installed OSD styles. |

### Setup

Dependency checks and model downloads.

| Command | Description |
|---------|-------------|
| `check` | Run voxtype's dependency check. |
| `download` | Download a model (names from 'info models'). |
| `set-model` | Make an installed model the default. |
| `vad` | Download the Silero VAD model. |

### Session

Workspace session: status, history, undo/redo.

| Command | Description |
|---------|-------------|
| `status` | Session state. |
| `history` | Config changes recorded in the workspace (most recent last). |
| `undo` | Revert the last config change. |
| `redo` | Re-apply the last undone change. |
| `save` | Save the workspace now (REPL mode does not auto-save). |

## Examples

### Transcribe audio

```bash
cli-anything-voxtype --json transcribe file /abs/path/memo.m4a
# -> {"text": "...", "words": 42, "duration_secs": 17.3, "no_speech": false, "converted": true, ...}

# Skip silent files reliably (energy VAD needs no model download)
cli-anything-voxtype --json transcribe file /abs/call.wav --vad --vad-backend energy

# Whole folder (wav/mp3/flac/ogg/opus/m4a/...) into a CSV
cli-anything-voxtype --json transcribe batch /abs/recordings -r -o /abs/out.csv
```

### Change settings safely, with undo

```bash
cli-anything-voxtype project new -o /abs/ws.json --config ~/.config/voxtype/config.toml
cli-anything-voxtype --json config schema --search punctuation        # find the key and its type
cli-anything-voxtype --json --dry-run config set audio.feedback.volume 0.4   # validate only
cli-anything-voxtype --json --project /abs/ws.json config set text.spoken_punctuation true
cli-anything-voxtype --project /abs/ws.json config replace add "vox type" voxtype
cli-anything-voxtype --json --project /abs/ws.json session history
cli-anything-voxtype --json --project /abs/ws.json session undo
cli-anything-voxtype daemon service restart     # most keys report restart_required: true
```

### Meeting minutes from recordings

```bash
cli-anything-voxtype --json meeting import /abs/a.wav /abs/b.wav -t "Design review" --speakers 0,1 --gap-ms 500
cli-anything-voxtype meeting label latest 1 Alice
cli-anything-voxtype --json meeting export latest -f srt -o /abs/review.srt
cli-anything-voxtype --json meeting show latest          # full transcript JSON
cli-anything-voxtype meeting delete <id> --yes
```

### Daemon

```bash
cli-anything-voxtype --json daemon status               # state: idle|recording|transcribing|...
cli-anything-voxtype daemon record start --output-mode clipboard
cli-anything-voxtype daemon record stop
```

## For AI Agents

1. **Always pass `--json`** and parse stdout. Errors are JSON on stdout too, with a non-zero exit.
2. **Look before you write**: `config schema --search X` gives the exact key, type, choices
   and range. `config get KEY` returns both `value` (effective) and `file_value` (literal, or `null` = default).
3. **Use a workspace (`--project`) for any config change** you might need to revert.
   `session undo` restores the previous literal value, or removes the key if it was absent.
4. **Use `--dry-run`** to test a value. voxtype validates it on a scratch copy, and invalid
   values exit with code 2.
5. **Restart to apply**: when a change reports `restart_required: true`, the running daemon
   only picks it up after `daemon service restart`. `transcribe` always reads the file fresh.
6. **Don't start recording unless asked**: `daemon record start/toggle` and `meeting start`
   use the live microphone, and by default type into the focused window. Prefer
   `--output-mode clipboard` or `--file PATH`.
7. **Silence**: whisper may return a hallucination such as "you" for silent audio. Pass
   `--vad --vad-backend energy` and check `no_speech`.
8. **Meeting IDs** accept a full UUID, a unique prefix, or `latest`.
9. **Use absolute paths**, and check that export files exist (`file_size` is reported).

## Version

1.0.0
