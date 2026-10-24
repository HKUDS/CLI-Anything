# cli-anything-vlc

Agent-native CLI for **VLC**. Define a media job (inputs, transcode options, output)
as structured JSON, then run it through the real VLC engine — transcode to file,
stream over the network, or extract a still frame. Every command supports `--json`
for machine-readable output and a stateful REPL with undo/redo.

## Installation

```bash
pip install -e .
```

**Prerequisites:**

- Python 3.10+
- VLC must be installed and on your `PATH`:
  - macOS: `brew install --cask vlc`
  - Debian/Ubuntu: `apt install vlc`
  - Windows: install from <https://www.videolan.org/vlc/> and ensure `vlc.exe` is on `PATH`
    (or set `VLC_BINARY` to its absolute path)

## Usage

```bash
# Show help
cli-anything-vlc --help

# Start the interactive REPL (default; just run the command with no subcommand)
cli-anything-vlc

# Build a job and transcode it (scripted / agent mode)
cli-anything-vlc project new -o job.json
cli-anything-vlc --project job.json add-input in.mp4
cli-anything-vlc --project job.json set-output out.mp4 --format mp4
cli-anything-vlc --project job.json set-option vcodec h264
cli-anything-vlc --project job.json set-option vbitrate 800
cli-anything-vlc --project job.json transcode --json

# Inspect media without transcoding
cli-anything-vlc info in.mp4 --json
```

## Command groups

| Group | Commands |
|---|---|
| `project` | `new`, `show` |
| job mutation | `add-input`, `set-output`, `set-option`, `set-stream`, `set-snapshot`, `clear` |
| run / inspect | `transcode`, `stream`, `snapshot`, `info`, `doctor` |
| REPL only | `open`, `save`, `undo`, `redo` |

> `open`, `save`, `undo` and `redo` exist **only inside the REPL** (run the CLI with no
> subcommand). The root command exposes `--json`, `--project`, `--version` and `--help`;
> the mutation and run commands above are available both as subcommands and in the REPL.

## For AI agents

1. Always pass `--json` for parseable output.
2. Check exit codes — `0` success, non-zero error.
3. Pass absolute paths for all file arguments.
4. `info` parsing of VLC `--stats` is best-effort; treat missing fields as "unknown".
5. Verify outputs exist after `transcode` / `snapshot`.

## Examples

Copy-paste agent workflows (transcode / stream / snapshot / info / doctor) live in
[`examples/agent-workflows.md`](examples/agent-workflows.md).

## Version

1.0.0
