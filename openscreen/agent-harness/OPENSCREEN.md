# Openscreen: Project-Specific Analysis & SOP

## Architecture Summary

Openscreen is an Electron-based screen recording editor built with React, PixiJS,
and the WebCodecs API. It records screen captures and provides a timeline editor
for adding zoom effects, speed changes, trims, annotations, crop, and backgrounds.

```
┌──────────────────────────────────────────────────────────────┐
│  Openscreen Electron App (GUI)                               │
│  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │  React UI Components │  │  Video Editor (PixiJS canvas) │  │
│  │  - Timeline          │  │  - Zoom transform             │  │
│  │  - Settings panel    │  │  - Motion blur filter         │  │
│  │  - Annotations       │  │  - Shadow compositing         │  │
│  └──────────┬───────────┘  └──────────────┬───────────────┘  │
│             │                              │                  │
│  ┌──────────▼──────────────────────────────▼───────────────┐  │
│  │  WebCodecs Pipeline                                     │  │
│  │  web-demuxer → VideoDecoder → FrameRenderer → Encoder   │  │
│  │                                          → mediabunny   │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    .openscreen (JSON) project file
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  CLI Harness (this project)                                  │
│  ┌─────────────────────┐  ┌──────────────────────────────┐   │
│  │  Click CLI + REPL   │  │  ffmpeg backend              │   │
│  │  - Project CRUD     │  │  - crop+scale (zoom)         │   │
│  │  - Region management│  │  - setpts+atempo (speed)     │   │
│  │  - Session/undo     │  │  - concat (segments)         │   │
│  └──────────┬──────────┘  │  - overlay (background)      │   │
│             │              └──────────────┬───────────────┘   │
│             ▼                             ▼                   │
│         JSON state                   Rendered MP4            │
└──────────────────────────────────────────────────────────────┘
```

## The .openscreen Project Format

Openscreen saves projects as JSON files with the `.openscreen` extension.
The CLI harness reads and writes this format directly.

### Structure

```json
{
  "version": 2,
  "media": {
    "screenVideoPath": "/path/to/recording.webm",
    "webcamVideoPath": "/path/to/webcam.webm"
  },
  "editor": {
    "wallpaper": "gradient_dark",
    "shadowIntensity": 0,
    "showBlur": false,
    "motionBlurAmount": 0,
    "borderRadius": 12,
    "padding": 50,
    "cropRegion": { "x": 0, "y": 0, "width": 1, "height": 1 },
    "zoomRegions": [
      {
        "id": "zoom_1",
        "startMs": 2500,
        "endMs": 5000,
        "depth": 3,
        "focus": { "cx": 0.7, "cy": 0.3 },
        "focusMode": "manual"
      }
    ],
    "speedRegions": [
      { "id": "speed_1", "startMs": 10000, "endMs": 15000, "speed": 2.0 }
    ],
    "trimRegions": [
      { "id": "trim_1", "startMs": 0, "endMs": 500 }
    ],
    "annotationRegions": [],
    "aspectRatio": "16:9",
    "exportQuality": "good",
    "exportFormat": "mp4"
  }
}
```

### Key Concepts

| Concept | JSON Path | Description |
|---------|-----------|-------------|
| Zoom | `editor.zoomRegions[]` | Camera zoom with focus point and depth 1-6 |
| Speed | `editor.speedRegions[]` | Playback speed 0.25x-2.0x for time ranges |
| Trim | `editor.trimRegions[]` | Cut out sections of the recording |
| Crop | `editor.cropRegion` | Normalized 0-1 rectangle for visible area |
| Annotation | `editor.annotationRegions[]` | Text/image/arrow overlays |
| Background | `editor.wallpaper` | Gradient, solid color, or blur |
| Padding | `editor.padding` | 0-100, space around video in canvas |

## CLI Strategy

### What We Manipulate Directly
- The `.openscreen` JSON project file (read, write, modify all fields)
- Region arrays (zoom, speed, trim, annotation) — add, remove, list
- Editor settings (wallpaper, padding, aspect ratio, quality)

### What We Delegate to ffmpeg
- Video probing (ffprobe)
- Segment rendering (crop, scale, speed changes)
- Segment concatenation
- Background compositing (color overlay)
- Frame extraction (for thumbnails)

## The Rendering Pipeline

### 1. Segment-based rendering (primary approach)

```
Source video
  → Split into segments at region boundaries
  → For each segment:
      → Apply crop (if zoom: crop to focus region)
      → Scale to target resolution
      → Apply speed change (setpts + atempo)
      → Encode as H.264 MP4
  → Concatenate all segments (stream copy)
  → Composite onto background canvas (color overlay)
  → Final output MP4
```

### 2. Zoom implementation

The GUI uses PixiJS `zoompan` with smooth easing. The CLI approximates this
with `crop+scale`: for a zoom depth of 3 (1.8x), we crop a 1/1.8-sized region
centered on the focus point, then scale it back up to target resolution.

### 3. Speed implementation

Speed regions use ffmpeg's `setpts` (video) and `atempo` (audio) filters.
For speeds outside atempo's 0.5-2.0 range, filters are chained.

## Command Map: GUI Action → CLI Command

| GUI Action | CLI Command |
|-----------|-------------|
| Record screen | (external — use macOS screen recording or Openscreen app) |
| Open project | `project open <path>` |
| Save project | `project save [-o path]` |
| Set background | `project set wallpaper gradient_dark` |
| Set padding | `project set padding 40` |
| Set aspect ratio | `project set aspectRatio 16:9` |
| Add zoom region | `zoom add --start 2500 --end 5000 --depth 3 --focus-x 0.7 --focus-y 0.3` |
| Add speed region | `speed add --start 10000 --end 15000 --speed 2.0` |
| Trim section | `trim add --start 0 --end 500` |
| Add text annotation | `annotation add-text --start 5000 --end 7000 --text "Click here"` |
| Crop video | `crop set --x 0.1 --y 0.1 --width 0.8 --height 0.8` |
| Export video | `export render output.mp4` |
| Undo | `session undo` |

## Verified Workflow: Demo Video Enhancement

1. `project new -v ~/Desktop/recording.mov`
2. `zoom add --start 2500 --end 5000 --depth 3 --focus-x 0.8 --focus-y 0.3`
3. `speed add --start 10000 --end 15000 --speed 2.0`
4. `trim add --start 0 --end 500`
5. `project set wallpaper gradient_dark`
6. `project set padding 40`
7. `export render ~/Desktop/demo.mp4`

**Verification results:**
- Output: 1920x1080 H.264 MP4
- Zoom region correctly crops and scales source
- Speed region reduces segment duration by expected factor
- Trim region excluded from output
- Background composited with centered video and padding

## Test Coverage

**101 total tests** across two suites:
- `test_core.py` (78 tests): Session, project, zoom, speed, trim, crop, annotation, integration
- `test_full_e2e.py` (23 tests): Real ffmpeg rendering, CLI subprocess, media probing
