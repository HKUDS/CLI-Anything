# Scribus: Project-Specific Analysis & SOP

## Architecture Summary

Scribus is an open-source desktop publishing application. `.sla` files are XML documents describing pages, frames, layers, and styling. Scribus provides `scribus --python-script` for headless operations.

## CLI Strategy: SLA XML + Python scripting

For read operations, we parse `.sla` XML directly. For write operations, we generate Python scripts and execute via `scribus --python-script`:

```bash
scribus -g -py script.py  # run Python script headlessly
```

## Command Map

| GUI Action | CLI Command |
|-----------|-------------|
| New Document | `create <output> --width W --height H --pages N` |
| Document Info | `info <file>` |
| Export PDF | `export <input> <output> --preset print` |
| Add Page | `page add <file> --output OUT` |
| Add Text | `text-add <file> --page N --x X --y Y --width W --height H --content TEXT --output OUT` |
| Add Image | `image-add <file> --page N --x X --y Y --width W --height H --image PATH --output OUT` |

## Test Coverage

1. **Unit tests** (test_core.py): Session, document creation, SLA parsing
2. **E2E tests** (test_full_e2e.py): CLI subprocess invocation
