# cli-anything-krita

CLI harness for **Krita** — the professional open-source digital painting application.

## Prerequisites

- **Python 3.10+**
- **Krita** installed on your system:
  - **Windows**: Download from [krita.org](https://krita.org/en/download/)
  - **macOS**: `brew install --cask krita`
  - **Linux**: `sudo apt install krita` or `flatpak install org.kde.krita`

## Installation

```bash
cd krita/agent-harness
pip install -e .
```

## Usage

### One-shot commands

```bash
# Create a new project
cli-anything-krita project new -n "My Painting" -w 2048 -h 2048 -o project.json

# Add layers
cli-anything-krita --project project.json layer add "Sketch" -t paintlayer
cli-anything-krita --project project.json layer add "Colors" -t paintlayer --opacity 200
cli-anything-krita --project project.json layer add "Background" -t paintlayer

# Apply filters
cli-anything-krita --project project.json filter apply blur -l "Background"

# Export to PNG
cli-anything-krita --project project.json export render output.png -p png --overwrite

# JSON output mode (for AI agents)
cli-anything-krita --json --project project.json project info
cli-anything-krita --json --project project.json layer list
```

### Interactive REPL

```bash
# Start REPL (default when no subcommand given)
cli-anything-krita

# Start REPL with a project loaded
cli-anything-krita --project project.json
```

### Command groups

| Group | Commands | Description |
|-------|----------|-------------|
| `project` | `new`, `open`, `save`, `info` | Project management |
| `layer` | `add`, `remove`, `list`, `set` | Layer stack management |
| `filter` | `apply`, `list` | Filters and effects |
| `canvas` | `resize`, `info` | Canvas properties |
| `export` | `render`, `animation`, `presets`, `formats` | Export and rendering |
| `session` | `undo`, `redo`, `history` | Undo/redo state |
| `status` | — | Current status overview |

### Export presets

| Preset | Format | Description |
|--------|--------|-------------|
| `png` | PNG | Full alpha, compression 6 |
| `png-web` | PNG | Optimized for web |
| `jpeg` | JPEG | Quality 90 |
| `jpeg-web` | JPEG | Quality 75 |
| `tiff` | TIFF | Uncompressed |
| `psd` | PSD | Photoshop compatible |
| `pdf` | PDF | Document export |
| `svg` | SVG | Vector export |
| `webp` | WebP | Quality 85 |

## How it works

1. **Project JSON** stores the document state (layers, filters, canvas settings)
2. **Build .kra** generates a valid Krita archive from the project state
3. **Krita --export** invokes the real Krita application for rendering
4. **Output verification** checks the exported file for correctness

The CLI is an interface TO Krita, not a replacement. All rendering is done by Krita's engine.
