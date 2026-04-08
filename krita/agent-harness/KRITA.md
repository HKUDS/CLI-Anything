# Krita — Agent Harness SOP

## Software Overview

**Krita** is a professional open-source digital painting application by KDE.
It supports raster graphics, vector graphics, and animation with a
non-destructive layer system, 90+ blending modes, and full ICC color management.

## Architecture Analysis

### Backend Engine
- **Core**: Qt-based (Qt5/Qt6) with OpenGL/RHI hardware acceleration
- **Image processing**: `libs/image/KisImage` — multi-threaded, tile-based
- **Color management**: `libs/pigment/` — full ICC profile support
- **Brush engines**: pixel, MyPaint, sketch with pressure/tilt dynamics

### CLI Interface
Krita supports headless batch operations:
```bash
krita --export --export-filename output.png input.kra
krita --export-sequence --export-filename frame_.png input.kra
krita --new-image RGBA,U8,1920,1080 --export --export-filename blank.png
```

### Python Scripting API (libkis)
Full programmatic access via embedded Python:
- `Krita.instance()` — singleton root
- `Document` — create, open, save, export, manipulate layers
- `Node` — layer/mask hierarchy with pixel data access
- `Filter` — apply effects programmatically
- `Selection` — rectangle, feather, invert operations
- `ManagedColor` — color space aware color values

### Native File Format (.kra)
ZIP archive containing:
- `mimetype` — `application/x-kra`
- `maindoc.xml` — document structure (layers, dimensions, colorspace)
- `documentinfo.xml` — Dublin Core metadata
- `layers/layerN.png` — pixel data per layer
- `annotations/icc/` — embedded ICC profiles

## Command Map

| GUI Action | CLI Command | Backend |
|-----------|-------------|---------|
| File → New | `project new` | Creates project JSON |
| File → Open | `project open` | Loads project JSON |
| File → Save | `project save` | Saves project JSON |
| File → Export | `export render` | `krita --export` |
| Layer → Add | `layer add` | Updates project state |
| Layer → Remove | `layer remove` | Updates project state |
| Filter → Apply | `filter apply` | `krita --script` |
| Image → Resize | `canvas resize` | Updates project state |
| Image → Scale | `canvas scale` | Updates project state |
| Edit → Undo | `session undo` | Session state |
| Edit → Redo | `session redo` | Session state |
| View → Info | `project info` | Reads project JSON |
| Animation → Export | `export animation` | `krita --export-sequence` |

## Rendering Approach

The CLI generates valid .kra files from project JSON, then invokes the real
Krita executable for export. This ensures all Krita filters, blending modes,
and color management are applied correctly by the actual rendering engine.

Pipeline: **Project JSON → .kra file → Krita --export → Final output**

## System Requirements

- **Krita** must be installed on the system
- **Python 3.10+** for the CLI harness
- Supported platforms: Windows, macOS, Linux
