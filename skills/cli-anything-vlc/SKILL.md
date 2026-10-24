---
name: "cli-anything-vlc"
description: "Agent-native CLI for VLC — define media jobs (transcode, stream, snapshot) as structured JSON and run them through the real VLC engine, with --json output and an undo/redo REPL."
---

# cli-anything-vlc

Agent-native CLI for **VLC**. Define a media job (inputs, transcode options, output) as
structured JSON, then run it through the real VLC engine — transcode to file, stream over
the network, or extract a still frame. Every command supports `--json` for
machine-readable output and a stateful REPL with undo/redo.

## Installation

```bash
pip install cli-anything-vlc
```

**Prerequisites:**

- Python 3.10+
- VLC media player (v3.0+) installed and on `PATH`:
  - macOS: `brew install --cask vlc`
  - Debian/Ubuntu: `apt install vlc`
  - Windows: install from <https://www.videolan.org/vlc/> and ensure `vlc.exe` is on `PATH`
    (or set `VLC_BINARY` to its absolute path)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-vlc --help

# Start the interactive REPL (default; run with no subcommand)
cli-anything-vlc

# Create a job spec and inspect it
cli-anything-vlc project new -o job.json
cli-anything-vlc --project job.json --json project show
```

## Command Groups

### Cli

| Command | Description |
|---------|-------------|
| `add-input` | Append an input media file to the job. |
| `set-output` | Set the output file (and optional container format). |
| `set-option` | Set a transcode option (vcodec, acodec, vbitrate, abitrate, scale, width, height, fps, channels, samplerate). |
| `set-stream` | Configure network streaming for the job. |
| `set-snapshot` | Configure still-frame extraction for the job. |
| `clear` | Reset the job to defaults. |
| `transcode` | Transcode the job's first input to its output via the real VLC engine. |
| `stream` | Stream the job's input over the network via the real VLC engine. |
| `snapshot` | Extract a still frame from the job's input via the real VLC engine. |
| `info` | Probe a media file via VLC (best-effort metadata parse). |
| `doctor` | Verify the environment (VLC presence). |

### Project

| Command | Description |
|---------|-------------|
| `new` | Create a new empty job spec file. |
| `show` | Print the current job spec (from `--project`). |

## Examples

### Build and transcode a job (agent flow)

```bash
cli-anything-vlc project new -o job.json
cli-anything-vlc --project job.json add-input in.mp4
cli-anything-vlc --project job.json set-output out.mp4 --format mp4
cli-anything-vlc --project job.json set-option vcodec h264
cli-anything-vlc --project job.json set-option vbitrate 800
cli-anything-vlc --json --project job.json transcode
```

### Interactive REPL

```bash
cli-anything-vlc
# help / undo / redo / transcode
```

Full copy-paste workflows (transcode / stream / snapshot / info / doctor) are in
[`examples/agent-workflows.md`](https://github.com/HKUDS/CLI-Anything/tree/main/vlc/agent-harness/examples/agent-workflows.md).

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json`** for parseable output.
2. **Check return codes** — `0` success, non-zero error.
3. **Parse stderr** for error messages on failure.
4. **Use absolute paths** for all file operations.
5. **Verify outputs exist** after `transcode` / `snapshot`.

## Version

1.0.0
