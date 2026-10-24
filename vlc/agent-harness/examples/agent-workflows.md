# cli-anything-vlc — Agent Workflows

Copy-pasteable invocations for common agent tasks. Every command supports `--json`
for machine-readable output. Requires the real VLC binary on `PATH` (or set
`VLC_BINARY` to the absolute path).

## 1. Transcode a file (audio or video)

```bash
cli-anything-vlc project new -o job.json
cli-anything-vlc --project job.json add-input input.mp4
cli-anything-vlc --project job.json set-output output.mp4 --format mp4
cli-anything-vlc --project job.json set-option vcodec h264
cli-anything-vlc --project job.json set-option acodec mp3
cli-anything-vlc --project job.json set-option abitrate 128
cli-anything-vlc --json --project job.json transcode
```

Friendly codec names are resolved to VLC's native ids automatically:
`wav → s16l`, `aac → mp4a`, `h264/x264 → h264`, `mpeg4/mp4 → mp4v`, …
Verified working: `wav`, `mp3`, `aac` (mp4a), `flac`, `opus`.

## 2. Probe a media file

```bash
cli-anything-vlc --json info input.mp4
```

Returns `path`, `returncode`, and best-effort `size_bytes` / parsed stats.

## 3. Stream over UDP (bounded for tests/demos)

```bash
cli-anything-vlc --project job.json set-stream --protocol udp --dst 127.0.0.1 --port 6004 --mux ts
cli-anything-vlc --json --project job.json stream --run-time 5
```

Omit `--run-time` for a persistent stream. `rtp` / `http` protocols are also supported.

## 4. Extract a thumbnail frame (video input required)

```bash
cli-anything-vlc --project job.json add-input clip.mp4
cli-anything-vlc --project job.json set-snapshot --path ./frames --time 2.0 --ratio 1
cli-anything-vlc --json --project job.json snapshot
```

Uses VLC's `scene` video filter; emits a PNG still at the requested time.

## 5. Health check

```bash
cli-anything-vlc --json doctor
# -> {"checks": [{"check": "vlc binary", "ok": true, "path": "/usr/bin/vlc"}], "ready": true}   (exit 0)
# -> {"checks": [{"check": "vlc binary", "ok": false, "detail": "VLC not found on PATH..."}],
#     "ready": false}                                                                          (exit 1)
```

`doctor` reports `ready` plus one entry per check in `checks`; each entry carries `ok`
and either `path` (success) or `detail` (failure). A `VLC_BINARY` that runs but is not
VLC is reported as a failed check, not as ready.

## Undo / redo

The harness keeps a command history. In the REPL (`cli-anything-vlc` with no
subcommand) type `undo` / `redo`, or drive it programmatically via the `Session`
in `core/session.py`.
