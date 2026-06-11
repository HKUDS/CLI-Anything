# cli-anything-wavetone

Agent-native CLI harness for WaveTone 2.61 on Windows.

WaveTone is a transcription support tool for audio files. It analyzes
spectrograms and fundamental frequency, supports key and chord detection, note
editing, and GUI-driven MIDI/text/WAVE export. This harness creates a structured
project manifest, probes audio files, records labels and tempo metadata, and
launches the real WaveTone executable.

## Install

```bash
cd wavetone/agent-harness
pip install -e .
```

Set the backend path if WaveTone is not on the default portable path:

```powershell
$env:WAVETONE_HOME = "C:\Users\you\Desktop\wavetone2.6.1"
# or
$env:WAVETONE_EXE = "C:\Users\you\Desktop\wavetone2.6.1\wavetone.exe"
```

## Usage

```bash
cli-anything-wavetone --json wavetone doctor
cli-anything-wavetone --json project new song.wav -o song.wt.json
cli-anything-wavetone --project song.wt.json --json audio probe
cli-anything-wavetone --project song.wt.json --json project set-tempo --bpm 128
cli-anything-wavetone --project song.wt.json --json project add-label verse --time 32.5
cli-anything-wavetone --project song.wt.json --json wavetone launch
```

Running `cli-anything-wavetone` with no subcommand opens the REPL.

## Backend Truthfulness

This harness calls the actual `wavetone.exe`. It does not reimplement
WaveTone's analysis, transcription, or export engine. WaveTone 2.61 does not
document a headless scripting interface, so analysis and export remain GUI menu
flows. The JSON project is an agent-facing control and planning layer around the
real application.

## Tests

```bash
cd wavetone/agent-harness
python -m pytest cli_anything/wavetone/tests/ -v
```

The default test run skips real WaveTone backend tests so CI and contributors
without WaveTone can still run the CLI-only suite. To opt into the real Windows
smoke, set `CLI_ANYTHING_WAVETONE_REAL_BACKEND=1` plus `WAVETONE_EXE` or
`WAVETONE_HOME` pointing at a WaveTone 2.61 extraction with `wavetone.exe` and
the bundled `data` directory. E2E subprocess tests run the in-tree
`python -m cli_anything.wavetone.wavetone_cli` module by default and do not
silently prefer an installed `cli-anything-wavetone` from `PATH`.
