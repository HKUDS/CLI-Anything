---
name: >-
  cli-anything-obs-studio
description: >-
  Command-line interface for OBS Studio scene collections, sources, filters, and output settings.
---

# cli-anything-obs-studio

CLI harness for OBS Studio scene collection JSON projects.

## Installation

```bash
pip install cli-anything-obs-studio
```

## Usage

```bash
cli-anything-obs-studio project new --name "stream" -o stream.json
cli-anything-obs-studio --project stream.json scene add --name "BRB"
cli-anything-obs-studio --project stream.json source add video_capture --name "Webcam"
cli-anything-obs-studio --project stream.json filter add chroma_key -S Webcam -p similarity=400
cli-anything-obs-studio --project stream.json output streaming --service twitch --key live_xxx
```

Use `--json` for machine-readable output.
