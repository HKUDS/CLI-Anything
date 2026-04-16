# cli-anything-drawio

A CLI harness for **Draw.io** — create, edit, and export diagrams from the command line.

Designed for AI agents and power users who need to generate diagrams programmatically.

## Prerequisites

- **Python 3.10+**
- **draw.io desktop app** (for PNG/PDF/SVG export):
  - macOS: `brew install --cask drawio`
  - Linux: `snap install drawio`
  - Windows: `winget install JGraph.Draw`

Note: The CLI can create and manipulate `.drawio` files without the desktop app installed. The app is only needed for rasterized export (PNG, PDF, SVG).

## Installation

```bash
cd drawio/agent-harness
pip install -e .
```

## Usage

### One-shot commands

```bash
# Create a new diagram
cli-anything-drawio project new --preset letter -o diagram.drawio

# Add shapes
cli-anything-drawio --project diagram.drawio shape add rectangle --label "Server"
cli-anything-drawio --project diagram.drawio shape add cylinder --label "Database" --x 300 --y 100

# Connect shapes
cli-anything-drawio --project diagram.drawio connect add <source_id> <target_id>

# Export
cli-anything-drawio --project diagram.drawio export render output.png -f png
cli-anything-drawio --project diagram.drawio export render output.svg -f svg
```

### JSON mode (for AI agents)

```bash
cli-anything-drawio --json project new -o diagram.drawio
cli-anything-drawio --json --project diagram.drawio shape add rectangle --label "API"
cli-anything-drawio --json --project diagram.drawio shape list
```

### Interactive REPL

```bash
cli-anything-drawio
# or
cli-anything-drawio repl --project diagram.drawio
```

## Command Reference

| Group | Command | Description |
|-------|---------|-------------|
| `project` | `new`, `open`, `save`, `info`, `xml`, `presets` | Project lifecycle |
| `shape` | `add`, `remove`, `list`, `label`, `move`, `resize`, `style`, `info`, `types` | Shape operations |
| `connect` | `add`, `remove`, `label`, `style`, `list`, `styles` | Connector operations |
| `page` | `add`, `remove`, `rename`, `list` | Multi-page management |
| `export` | `render`, `formats` | Export to PNG/PDF/SVG/XML |
| `session` | `status`, `undo`, `redo`, `save-state`, `list` | Session management |

## Shape Types

rectangle, rounded, ellipse, diamond, triangle, hexagon, cylinder, cloud, parallelogram, process, document, callout, note, actor, text

## Edge Styles

straight, orthogonal, curved, entity-relation

## Running Tests

```bash
cd drawio/agent-harness
python3 -m pytest cli_anything/drawio/tests/ -v
```
