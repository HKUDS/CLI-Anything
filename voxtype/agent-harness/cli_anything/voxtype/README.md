# cli-anything-voxtype

An agent-friendly CLI for **[Voxtype](https://voxtype.io)**, the push-to-talk
voice-to-text daemon for Linux. It wraps the real `voxtype` binary to give
structured, `--json`-capable control over:

- **Configuration**: read, set and unset any of voxtype's 187 settings. voxtype's
  own validator checks every change, and inside a workspace each change can be undone and redone.
- **Transcription**: transcribe audio files in any format ffmpeg can read, singly or
  in batches, with export to txt/md/json/jsonl/csv.
- **Meetings**: list, show, export (text/markdown/json/srt/vtt), label speakers,
  delete, summarize, and **import pre-recorded audio as a native voxtype meeting**.
- **Daemon**: status, recording control (`start/stop/toggle/cancel`), and the
  systemd user service.
- **Introspection**: engines, models, audio devices, binary variants, OSD styles,
  and dependency checks.

## Requirements

Both of these are hard dependencies. Nothing is reimplemented in Python.

| Dependency | Why | Install |
|------------|-----|---------|
| `voxtype` ≥ 1.1 | all config, transcription and meeting operations | `yay -S voxtype-bin` (Arch), or packages from <https://voxtype.io> |
| a whisper model | transcription | `voxtype setup --download --model base.en` |
| `ffmpeg` | converting non-WAV input to 16 kHz mono | `pacman -S ffmpeg` / `apt install ffmpeg` |

Set `$VOXTYPE_BIN` to use a voxtype binary that isn't on PATH.

## Install

```bash
cd voxtype/agent-harness
pip install -e .            # or: pip install -e ".[dev]" for pytest
which cli-anything-voxtype
```

## Usage

```bash
# REPL (default when no subcommand is given)
cli-anything-voxtype

# Introspection
cli-anything-voxtype --json daemon status
cli-anything-voxtype info engines
cli-anything-voxtype info models --installed
cli-anything-voxtype config schema --section Text

# Transcribe
cli-anything-voxtype transcribe file memo.m4a
cli-anything-voxtype --json transcribe file call.wav --vad --vad-backend energy
cli-anything-voxtype transcribe batch ~/recordings -o transcripts.csv

# A workspace pins a config file and keeps undo history
cli-anything-voxtype project new -o tuning.json --config ~/.config/voxtype/config.toml
cli-anything-voxtype --project tuning.json config replace add "vox type" voxtype
cli-anything-voxtype --project tuning.json config set text.spoken_punctuation true
cli-anything-voxtype --project tuning.json session history
cli-anything-voxtype --project tuning.json session undo

# Check a change without writing anything
cli-anything-voxtype --dry-run config set audio.feedback.volume 0.4

# Meetings from recordings
cli-anything-voxtype meeting import part1.wav part2.wav -t "Design review" --speakers 0,1
cli-anything-voxtype meeting label latest 1 Alice
cli-anything-voxtype meeting export latest -f srt -o review.srt

# Daemon control (start/toggle capture the microphone)
cli-anything-voxtype daemon record start --output-mode clipboard
cli-anything-voxtype daemon record stop
cli-anything-voxtype daemon service restart
```

### Global options

| Option | Meaning |
|--------|---------|
| `--json` | Machine-readable output on stdout. Errors are printed as `{"error", "type", "returncode"}`. |
| `--project FILE` | Workspace: the target config file, transcription overrides, undo history and transcription log. Saved automatically after each one-shot command. |
| `--config FILE` | Operate on this voxtype `config.toml`; takes precedence over the workspace's. |
| `--dry-run` | Config changes go to a scratch copy (voxtype still validates them). The workspace isn't saved. Destructive actions are only reported. |

### Exit codes

`0` success · `1` runtime or I/O error · `2` invalid key or value (voxtype's own contract).

### Notes

- Most config keys need a daemon restart before they take effect
  (`restart_required: true` in the JSON). Use `daemon service restart`.
- With the whisper engine, `--vad` only takes effect after `setup vad` downloads the
  Silero model. `--vad-backend energy` works with no download.
- Pure silence comes back as a short hallucination such as "you" unless VAD is on.

## Tests

```bash
cd voxtype/agent-harness
python -m pytest cli_anything/voxtype/tests/test_core.py -v            # unit, no voxtype needed
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/voxtype/tests/ -v -s   # full suite, real voxtype
```

The E2E tests write only to temporary config files and temporary meeting storage.
See `tests/TEST.md` for the plan and results.
