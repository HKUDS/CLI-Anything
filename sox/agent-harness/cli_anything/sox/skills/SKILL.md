# Sox Skill

## Overview
Audio processing and manipulation using SoX (Sound eXchange). Supports format conversion, effects, analysis, and synthesis.

## When to use
- Converting between audio formats (WAV, MP3, FLAC, OGG, etc.)
- Trimming, concatenating, or mixing audio files
- Adjusting speed, pitch, tempo, or volume
- Applying effects like fade, normalize, reverse
- Analyzing audio statistics or generating spectrograms
- Generating test tones or signals
- Removing silence from recordings

## Capabilities
- **Format conversion**: Convert between any SoX-supported audio formats
- **Editing**: Trim, concat, mix, reverse, silence removal
- **Effects**: Speed, pitch, tempo, volume, normalize, fade
- **Analysis**: File info, detailed statistics, spectrograms
- **Synthesis**: Generate sine, square, sawtooth, and noise signals
- **Batch**: List available SoX effects

## Requirements
- SoX installed (`apt install sox`)

## Example usage
```bash
cli-anything-sox info recording.wav
cli-anything-sox convert recording.wav recording.mp3 --sample-rate 44100
cli-anything-sox trim song.mp3 clip.wav --start 30 --duration 10
cli-anything-sox normalize loud.wav quiet_loud.wav
cli-anything-sox spectrogram audio.wav spec.png
cli-anything-sox synth tone.wav --type sine --frequency 440 --duration 3
```
