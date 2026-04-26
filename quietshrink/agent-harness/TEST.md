# quietshrink Agent Harness — Tests

This is a thin wrapper around the standalone `quietshrink` bash CLI. The bash CLI itself has its own smoke test suite at <https://github.com/achiya-automation/quietshrink/blob/main/tests/test_cli.sh> with 6 passing tests verified in CI on macos-latest.

## Smoke tests covered by upstream

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

## Harness-level integration

The Python harness shells out to the bash CLI and re-emits its JSON output. Tests are intentionally minimal because:

1. The encoding logic lives in the bash CLI, validated upstream.
2. The harness's job is JSON conformance + agent ergonomics.
3. End-to-end behavior is verified by running `cli-anything-quietshrink doctor --json` post-install.

## Manual verification

```bash
# After install:
cli-anything-quietshrink doctor --json
# Expected: { "checks": [...], "ready": true }

# Probe a real video:
cli-anything-quietshrink probe ~/Desktop/some-recording.mov --json
# Expected: codec, dimensions, duration, size

# Compress:
cli-anything-quietshrink compress input.mov output.mov --json
# Expected: input_size, output_size, saved_percent, encoding_speed
```

## Hardware requirements

- macOS Apple Silicon (M1/M2/M3/M4) — for hardware HEVC encoder
- ffmpeg 6+ with `hevc_videotoolbox` enabled (`brew install ffmpeg`)

Intel Macs and Linux work without hardware acceleration; the underlying ffmpeg falls back to `libx265` (software), which defeats the "quiet computer" promise but still produces correct output.
