# Scribus CLI

Desktop publishing from the command line via `scribus --python-script` and `.sla` XML parsing.

## Prerequisites

- Python 3.10+
- `scribus` (apt install scribus)
- `click` (CLI framework)
- `prompt_toolkit` (optional, for REPL)

## Install

```bash
pip install click prompt_toolkit
```

## Commands

```bash
# Create document
scribus_cli create output.sla --width 210 --height 297 --pages 4

# Get file info
scribus_cli info document.sla

# Export to PDF
scribus_cli export input.sla output.pdf --preset print

# List pages
scribus_cli page list document.sla

# Add page
scribus_cli page add document.sla --output updated.sla

# Add text frame
scribus_cli text-add document.sla --page 0 --x 10 --y 10 --width 100 --height 20 --content "Hello" --output out.sla

# Add image frame
scribus_cli image-add document.sla --page 0 --x 0 --y 0 --width 50 --height 50 --image photo.jpg --output out.sla

# List layers
scribus_cli layer list document.sla

# List fonts
scribus_cli font-list

# REPL
scribus_cli repl
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli_anything/scribus/tests/ -v
```
