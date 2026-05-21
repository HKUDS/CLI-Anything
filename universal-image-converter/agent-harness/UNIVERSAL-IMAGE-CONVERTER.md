# Universal Image Converter: Project-Specific Analysis & SOP

## Architecture Summary

Universal Image Converter is a Python-based desktop application for converting
images between formats. It uses Tkinter/ttkbootstrap for its GUI and Pillow
for the core image conversion engine.

```
┌──────────────────────────────────────────────┐
│          Universal Image Converter GUI        │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │  File Picker  │  │  Format Selector     │  │
│  │  (Tkinter)    │  │  (ttkbootstrap)      │  │
│  └──────┬───────┘  └────────┬─────────────┘  │
│         │                   │                 │
│  ┌──────┴───────────────────┴─────────────┐  │
│  │          converter.py                   │  │
│  │    Pillow-based image conversion        │  │
│  └──────────────────┬─────────────────────┘  │
└─────────────────────┼────────────────────────┘
                      │
          ┌───────────┴──────────┐
          │       Pillow (PIL)    │
          │  Image I/O + resizing │
          └───────────────────────┘
```

## CLI Strategy: Pure Pillow

Unlike GIMP (which has complex layer stacks and GEGL), the Universal Image
Converter's operations are straightforward:

1. **Pillow** — handles all image I/O (PNG, JPEG, WebP, TIFF, BMP, ICO, GIF)
   and basic transformations (resize, mode conversion).
2. **pillow-heif** (optional) — adds HEIC/HEIF read support.

No external tools are required — Pillow covers all conversion needs.

## Core Operations via Pillow

### Image I/O
| Operation | Pillow API |
|-----------|-----------|
| Open image | `Image.open(path)` |
| Save image | `image.save(path, format, **params)` |
| Probe image | `Image.open(path)` + attribute access |
| Close image | `image.close()` |

### Transformations
| Operation | Pillow API |
|-----------|-----------|
| Resize | `image.resize((w, h), resample)` |
| Thumbnail | `image.thumbnail((w, h), resample)` |
| Mode convert | `image.convert("RGB"/"RGBA"/"L")` |
| Alpha removal | `background.paste(img, mask=alpha)` |

## Supported Formats

| Format | Ext | Pillow ID | Input | Output | Alpha | Lossless |
|--------|-----|-----------|-------|--------|-------|----------|
| PNG | .png | PNG | Yes | Yes | Yes | Yes |
| JPEG | .jpg | JPEG | Yes | Yes | No | No |
| WebP | .webp | WEBP | Yes | Yes | Yes | Both |
| TIFF | .tiff | TIFF | Yes | Yes | Yes | Yes |
| BMP | .bmp | BMP | Yes | Yes | No | Yes |
| ICO | .ico | ICO | Yes | Yes | Yes | Yes |
| GIF | .gif | GIF | Yes | Yes | Yes | Yes |
| HEIC | .heic | HEIF | Yes | No | — | — |

## Command Map: GUI Action → CLI Command

| GUI Action | CLI Command |
|-----------|-------------|
| Select file(s) + choose format → Convert | `convert -i <files> -o <dir> -f <format>` |
| Select folder + choose format → Convert All | `convert -d <dir> -o <dir> -f <format>` |
| View file info | `info <path>` |
| List supported formats | `formats` |
| Set quality | `convert ... -q <preset>` |
| Resize before convert | `convert ... -w <pixels> -h <pixels>` |

## Quality Presets

| Preset | JPEG Quality | PNG Compress | WebP | Use Case |
|--------|-------------|-------------|------|----------|
| lossless | 100 | 0 | lossless | Archive, print |
| high | 92 | 3 | quality=85 | Web, sharing |
| medium | 80 | 6 | quality=85 | Email, thumbnails |
| low | 50 | 9 | quality=85 | Previews, drafts |

## Rendering Gap Assessment: **Low**

- All operations work via Pillow directly
- The original tool's GUI features (drag-and-drop, theme toggle) are irrelevant
  for CLI use
- HEIC input requires the optional `pillow-heif` package
- No layer or filter operations needed — pure format conversion
