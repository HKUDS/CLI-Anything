# Krita: Project-Specific Analysis & SOP

## Architecture Summary

Krita is a professional open-source digital painting application. `.kra` files are ZIP archives containing:
- `maindoc.xml` — document metadata, layer tree, dimensions
- `mergedimage.png` — flattened preview
- `layerXXXX/` — individual layer content as PNG

## CLI Strategy: krita --export + ZIP parsing

Krita provides `krita --export` for format conversion. For layer inspection, we parse the ZIP directly:

```bash
krita --export artwork.kra --output output.png
krita --export artwork.kra --output output.png --flatten
```

## Command Map

| GUI Action | CLI Command |
|-----------|-------------|
| File Info | `info <file>` |
| Export | `export <input> <output>` |
| List Layers | `layer list <file>` |
| Export Layer | `layer export <file> --index N --output OUT` |
| Flatten | `flatten <input> <output>` |
| New Canvas | `create --width W --height H --output FILE` |

## Test Coverage

1. **Unit tests** (test_core.py): Session, canvas creation, presets
2. **E2E tests** (test_full_e2e.py): CLI subprocess invocation
