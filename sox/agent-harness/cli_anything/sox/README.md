# CLI-Anything · Sox

A structured CLI harness wrapping SoX audio processing with JSON output, session management, and an interactive REPL.

## Installation

```bash
cd /tmp/CLI-Anything/sox/agent-harness
pip install . --break-system-packages
```

## Usage

```bash
cli-anything-sox --help
cli-anything-sox repl
cli-anything-sox info audio.wav
cli-anything-sox convert audio.wav audio.mp3 --sample-rate 44100
```

## Commands

- `info` — Audio file metadata
- `convert` — Convert format/bitrate/channels
- `trim` — Trim audio segments
- `concat` — Concatenate audio files
- `mix` — Mix audio files together
- `speed` — Change playback speed
- `pitch` — Shift pitch in semitones
- `tempo` — Change tempo without pitch
- `volume` — Adjust volume (dB)
- `normalize` — Normalize levels
- `reverse` — Reverse audio
- `fade` — Apply fade in/out
- `silence` — Remove silence
- `stat` — Detailed statistics
- `spectrogram` — Generate spectrogram images
- `synth` — Generate test tones
- `effects` — List available effects
