---
name: >-
  cli-anything-scribus
description: >-
  Command-line interface for Scribus — Desktop publishing and document creation from the command line...
---

# cli-anything-scribus

A command-line interface for desktop publishing via Scribus. Designed for AI agents and power users.

## Installation

```bash
pip install cli-anything-scribus
```

**Prerequisites:**
- Python 3.10+
- `scribus` must be installed: `apt install scribus`

## Usage

```bash
cli-anything-scribus create output.sla --width 210 --height 297 --pages 4
cli-anything-scribus info document.sla
cli-anything-scribus export input.sla output.pdf --preset print
cli-anything-scribus page list document.sla
cli-anything-scribus page add document.sla --output updated.sla
cli-anything-scribus text-add document.sla --page 0 --x 10 --y 10 --width 100 --height 20 --content "Hello" --output out.sla
cli-anything-scribus image-add document.sla --page 0 --x 0 --y 0 --width 50 --height 50 --image photo.jpg --output out.sla
cli-anything-scribus layer list document.sla
cli-anything-scribus layer add document.sla --name "Overlay" --output out.sla
cli-anything-scribus font-list
```

## Command Reference

| Command | Description |
|---------|-------------|
| `create` | Create new document |
| `info` | Get SLA file info |
| `export` | Export SLA to PDF |
| `page add` | Add page |
| `page list` | List pages |
| `text-add` | Add text frame |
| `image-add` | Add image frame |
| `layer list` | List layers |
| `layer add` | Add layer |
| `font-list` | List available fonts |
| `pdf-export` | Export specific pages to PDF |

## Version

1.0.0
