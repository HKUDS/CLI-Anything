# Darktable: Project-Specific Analysis & SOP

## Architecture Summary

Darktable is an open-source RAW photo processing application that uses a non-destructive editing model. RAW files are never modified; instead, edits are stored as metadata (XMP sidecars) and applied during export.

## CLI Strategy: darktable-cli

Darktable provides `darktable-cli` for headless batch processing. Our harness wraps this tool:

```bash
darktable-cli input.cr2 output.jpg --width 1920 --quality 95
darktable-cli input.cr2 output.jpg photo.cr2.xmp  # apply sidecar edits
darktable-cli input.cr2 output.jpg --style "My Style"  # apply preset style
```

## Command Map

| GUI Action | CLI Command |
|-----------|-------------|
| Import & Export | `export <input> <output>` |
| View EXIF | `info <file>` |
| Batch Export | `batch <inputs...> --output-dir DIR` |
| Apply Style | `styles export <input> <output> --style NAME` |
| Create Sidecar | `xmp create <input>` |
| Apply Sidecar | `xmp apply <xmp> <input> <output>` |

## Test Coverage

1. **Unit tests** (test_core.py): Session, presets, style listing
2. **E2E tests** (test_full_e2e.py): CLI subprocess invocation
