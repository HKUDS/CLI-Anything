# quietshrink Agent Harness — Tests

## Harness unit tests (this repo)

The harness ships with 15 unit/smoke tests under `cli_anything/quietshrink/tests/test_cli.py`. They exercise the harness layer (command wiring, JSON output schema, error paths, subprocess interface) without invoking ffmpeg or the bash CLI.

```bash
pip install -e '.[dev]'
pytest cli_anything/quietshrink/tests/ -v
```

Test groups:

- `TestVersionAndHelp` — `--version`, `--help`, no-args behavior
- `TestPresets` — text + JSON output, schema, all 4 presets present
- `TestFindBashCli` — `$PATH` resolution, error when missing
- `TestDoctor` — environment checks (ffmpeg, hevc_videotoolbox, bash CLI)
- `TestProbe` — ffprobe wiring, missing file, metadata extraction
- `TestCompress` — quality flag passthrough, JSON output, bash failure handling

All 15 tests pass on Python 3.10+ with no external dependencies (bash CLI and ffmpeg are mocked).

## Bash CLI tests (upstream)

The encoding logic itself lives in the standalone quietshrink bash CLI, which has 6 smoke tests passing on macos-latest CI:

```
test: --help
  ✓ help shows USAGE section
  ✓ help mentions tiny preset
  ✓ help mentions transparent preset
test: --version
  ✓ version output mentions quietshrink
test: missing input file
  ✓ correctly errors on missing file
test: invalid quality preset
  ✓ correctly errors on invalid preset

Results: 6 passed, 0 failed
```

CI: <https://github.com/achiya-automation/quietshrink/actions>
Test source: <https://github.com/achiya-automation/quietshrink/blob/main/tests/test_cli.sh>

## Manual end-to-end verification

After installing both the harness (`pip install …`) and the bash CLI (`install.sh`):

```bash
# Verify environment
cli-anything-quietshrink doctor --json
# Expected: { "checks": [...], "ready": true }

# Probe a real video
cli-anything-quietshrink probe ~/Desktop/recording.mov --json
# Expected: codec, dimensions, duration, size

# Compress
cli-anything-quietshrink compress input.mov output.mov --json
# Expected: input_size, output_size, saved_percent, encoding_speed
```

## Hardware requirements (compress only)

- macOS Apple Silicon (M1/M2/M3/M4) — for the hardware HEVC encoder
- ffmpeg 6+ with `hevc_videotoolbox` enabled (`brew install ffmpeg`)

Intel Macs and Linux work without hardware acceleration; ffmpeg falls back to `libx265` (software), which defeats the "quiet computer" promise but still produces correct output.
