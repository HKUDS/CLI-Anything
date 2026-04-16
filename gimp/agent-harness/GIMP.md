# GIMP: Project-Specific Analysis & SOP

## Architecture Summary

GIMP (GNU Image Manipulation Program) is a GTK-based raster image editor built on
the **GEGL** (Generic Graphics Library) processing engine and **Babl** color management.

```
┌──────────────────────────────────────────────┐
│                  GIMP GUI                    │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │  Canvas   │ │  Layers  │ │   Filters   │  │
│  │  (GTK)    │ │  (GTK)   │ │   (GTK)     │  │
│  └────┬──────┘ └────┬─────┘ └──────┬──────┘  │
│       │             │              │          │
│  ┌────┴─────────────┴──────────────┴───────┐ │
│  │       PDB (Procedure Database)          │ │
│  │  500+ registered procedures for all     │ │
│  │  image operations, filters, I/O         │ │
│  └─────────────────┬───────────────────────┘ │
│                    │                          │
│  ┌─────────────────┴───────────────────────┐ │
│  │       GEGL Processing Engine            │ │
│  │  DAG-based image processing pipeline    │ │
│  │  70+ built-in operations               │ │
│  └─────────────────┬───────────────────────┘ │
└────────────────────┼─────────────────────────┘
                     │
         ┌───────────┴──────────┐
         │  Babl (color mgmt)   │
         │  + GEGL operations   │
         │  + File format I/O   │
         └──────────────────────┘
```

## CLI Strategy: Pillow + External Tools

Unlike Shotcut (which manipulates XML project files), GIMP's native .xcf format
is a complex binary format. Our strategy:

1. **Pillow** — Python's standard imaging library. Handles image I/O (PNG, JPEG,
   TIFF, BMP, GIF, WebP, etc.), pixel manipulation, basic filters, color
   adjustments, drawing, and compositing. This is our primary engine.
2. **GEGL CLI** — If available, use `gegl` command for advanced operations.
3. **GIMP batch mode** — If `gimp` is installed, use `gimp -i -b` for XCF
   operations and advanced filters via Script-Fu/Python-Fu.

### Why Not XCF Directly?

XCF is a tile-based binary format with compression, layers, channels, paths,
and GEGL filter graphs. Parsing it from scratch is extremely complex (5000+ lines
of C in GIMP's xcf-load.c). Instead:
- For new projects, we build layer stacks in memory using Pillow
- For XCF import/export, we delegate to GIMP batch mode if available
- Our "project file" is a JSON manifest tracking layers, operations, and history

## The Project Format (.gimp-cli.json)

Since we can't easily manipulate XCF directly, we use a JSON project format:

```json
{
  "version": "1.0",
  "name": "my_project",
  "canvas": {
    "width": 1920,
    "height": 1080,
    "color_mode": "RGB",
    "background": "#ffffff",
    "dpi": 300
  },
  "layers": [
    {
      "id": 0,
      "name": "Background",
      "type": "image",
      "source": "/path/to/image.png",
      "visible": true,
      "opacity": 1.0,
      "blend_mode": "normal",
      "offset_x": 0,
      "offset_y": 0,
      "filters": [
        {"name": "brightness", "params": {"factor": 1.2}},
        {"name": "gaussian_blur", "params": {"radius": 3}}
      ]
    },
    {
      "id": 1,
      "name": "Text Layer",
      "type": "text",
      "text": "Hello World",
      "font": "Arial",
      "font_size": 48,
      "color": "#000000",
      "visible": true,
      "opacity": 0.8,
      "blend_mode": "normal",
      "offset_x": 100,
      "offset_y": 50,
      "filters": []
    }
  ],
  "selection": null,
  "guides": [],
  "metadata": {}
}
```

## Core Operations via Pillow

### Image I/O
| Operation | Pillow API |
|-----------|-----------|
| Open image | `Image.open(path)` |
| Save image | `image.save(path, format)` |
| Create blank | `Image.new(mode, (w,h), color)` |
| Convert mode | `image.convert("RGB"/"L"/"RGBA")` |
| Resize | `image.resize((w,h), resample)` |
| Crop | `image.crop((l, t, r, b))` |
| Rotate | `image.rotate(angle, expand=True)` |
| Flip | `image.transpose(Image.FLIP_LEFT_RIGHT)` |

### Filters & Adjustments
| Operation | Pillow API |
|-----------|-----------|
| Brightness | `ImageEnhance.Brightness(img).enhance(factor)` |
| Contrast | `ImageEnhance.Contrast(img).enhance(factor)` |
| Saturation | `ImageEnhance.Color(img).enhance(factor)` |
| Sharpness | `ImageEnhance.Sharpness(img).enhance(factor)` |
| Gaussian blur | `image.filter(ImageFilter.GaussianBlur(radius))` |
| Box blur | `image.filter(ImageFilter.BoxBlur(radius))` |
| Unsharp mask | `image.filter(ImageFilter.UnsharpMask(radius, percent, threshold))` |
| Find edges | `image.filter(ImageFilter.FIND_EDGES)` |
| Emboss | `image.filter(ImageFilter.EMBOSS)` |
| Contour | `image.filter(ImageFilter.CONTOUR)` |
| Detail | `image.filter(ImageFilter.DETAIL)` |
| Smooth | `image.filter(ImageFilter.SMOOTH_MORE)` |
| Grayscale | `ImageOps.grayscale(image)` |
| Invert | `ImageOps.invert(image)` |
| Posterize | `ImageOps.posterize(image, bits)` |
| Solarize | `ImageOps.solarize(image, threshold)` |
| Autocontrast | `ImageOps.autocontrast(image)` |
| Equalize | `ImageOps.equalize(image)` |
| Sepia | Custom kernel via `ImageOps.colorize()` |

### Compositing & Drawing
| Operation | Pillow API |
|-----------|-----------|
| Paste layer | `Image.alpha_composite(base, overlay)` |
| Blend modes | Custom implementations (multiply, screen, overlay, etc.) |
| Draw rectangle | `ImageDraw.rectangle(xy, fill, outline)` |
| Draw ellipse | `ImageDraw.ellipse(xy, fill, outline)` |
| Draw text | `ImageDraw.text(xy, text, font, fill)` |
| Draw line | `ImageDraw.line(xy, fill, width)` |

## Blend Modes

Pillow doesn't natively support Photoshop/GIMP blend modes. We implement the
most common ones using NumPy-style pixel math:

| Mode | Formula |
|------|---------|
| Normal | `top` (with alpha compositing) |
| Multiply | `base * top / 255` |
| Screen | `255 - (255-base)*(255-top)/255` |
| Overlay | `if base < 128: 2*base*top/255 else: 255 - 2*(255-base)*(255-top)/255` |
| Soft Light | Photoshop-style formula |
| Hard Light | Overlay with base/top swapped |
| Difference | `abs(base - top)` |
| Darken | `min(base, top)` |
| Lighten | `max(base, top)` |
| Color Dodge | `base / (255 - top) * 255` |
| Color Burn | `255 - (255-base) / top * 255` |

## Command Map: GUI Action -> CLI Command

| GUI Action | CLI Command |
|-----------|-------------|
| File -> New | `project new --width 1920 --height 1080 [--mode RGB]` |
| File -> Open | `project open <path>` |
| File -> Save | `project save [path]` |
| File -> Export As | `export render <output> [--format png] [--quality 95]` |
| Image -> Canvas Size | `canvas resize --width W --height H` |
| Image -> Scale Image | `canvas scale --width W --height H` |
| Image -> Crop to Selection | `canvas crop --left L --top T --right R --bottom B` |
| Image -> Mode -> RGB | `canvas mode RGB` |
| Layer -> New Layer | `layer new [--name "Layer"] [--width W] [--height H]` |
| Layer -> Duplicate | `layer duplicate <index>` |
| Layer -> Delete | `layer remove <index>` |
| Layer -> Flatten Image | `layer flatten` |
| Layer -> Merge Down | `layer merge-down <index>` |
| Move layer | `layer move <index> --to <position>` |
| Set layer opacity | `layer set <index> opacity <value>` |
| Set blend mode | `layer set <index> mode <mode>` |
| Toggle visibility | `layer set <index> visible <true/false>` |
| Layer -> Add from File | `layer add-from-file <path> [--name N] [--position P]` |
| Filters -> Blur -> Gaussian | `filter add gaussian_blur --layer L --param radius=5` |
| Colors -> Brightness-Contrast | `filter add brightness --layer L --param factor=1.2` |
| Colors -> Hue-Saturation | `filter add saturation --layer L --param factor=1.3` |
| Colors -> Invert | `filter add invert --layer L` |
| Draw text on layer | `draw text --layer L --text "Hi" --x 10 --y 10 --font Arial --size 24` |
| Draw rectangle | `draw rect --layer L --x1 0 --y1 0 --x2 100 --y2 100 --fill "#ff0000"` |
| View layers | `layer list` |
| View project info | `project info` |
| Undo | `session undo` |
| Redo | `session redo` |

## Filter Registry

### Image Adjustments
| CLI Name | Pillow Implementation | Key Parameters |
|----------|----------------------|----------------|
| `brightness` | `ImageEnhance.Brightness` | `factor` (1.0 = neutral, >1 = brighter) |
| `contrast` | `ImageEnhance.Contrast` | `factor` (1.0 = neutral) |
| `saturation` | `ImageEnhance.Color` | `factor` (1.0 = neutral, 0 = grayscale) |
| `sharpness` | `ImageEnhance.Sharpness` | `factor` (1.0 = neutral, >1 = sharper) |
| `autocontrast` | `ImageOps.autocontrast` | `cutoff` (0-49, percent to clip) |
| `equalize` | `ImageOps.equalize` | (no params) |
| `invert` | `ImageOps.invert` | (no params) |
| `posterize` | `ImageOps.posterize` | `bits` (1-8) |
| `solarize` | `ImageOps.solarize` | `threshold` (0-255) |
| `grayscale` | `ImageOps.grayscale` | (no params) |
| `sepia` | Custom colorize | `strength` (0.0-1.0) |

### Blur & Sharpen
| CLI Name | Pillow Implementation | Key Parameters |
|----------|----------------------|----------------|
| `gaussian_blur` | `ImageFilter.GaussianBlur` | `radius` (pixels) |
| `box_blur` | `ImageFilter.BoxBlur` | `radius` (pixels) |
| `unsharp_mask` | `ImageFilter.UnsharpMask` | `radius`, `percent`, `threshold` |
| `smooth` | `ImageFilter.SMOOTH_MORE` | (no params) |

### Stylize
| CLI Name | Pillow Implementation | Key Parameters |
|----------|----------------------|----------------|
| `find_edges` | `ImageFilter.FIND_EDGES` | (no params) |
| `emboss` | `ImageFilter.EMBOSS` | (no params) |
| `contour` | `ImageFilter.CONTOUR` | (no params) |
| `detail` | `ImageFilter.DETAIL` | (no params) |

### Transform
| CLI Name | Pillow Implementation | Key Parameters |
|----------|----------------------|----------------|
| `rotate` | `Image.rotate` | `angle` (degrees), `expand` (bool) |
| `flip_h` | `Image.transpose(FLIP_LEFT_RIGHT)` | (no params) |
| `flip_v` | `Image.transpose(FLIP_TOP_BOTTOM)` | (no params) |
| `resize` | `Image.resize` | `width`, `height`, `resample` (nearest/bilinear/bicubic/lanczos) |
| `crop` | `Image.crop` | `left`, `top`, `right`, `bottom` |

## Export Formats

| Format | Extension | Quality Param | Notes |
|--------|-----------|---------------|-------|
| PNG | .png | `compress_level` (0-9) | Lossless, supports alpha |
| JPEG | .jpg/.jpeg | `quality` (1-95) | Lossy, no alpha |
| WebP | .webp | `quality` (1-100) | Both lossy/lossless |
| TIFF | .tiff | `compression` (none/lzw/jpeg) | Professional |
| BMP | .bmp | (none) | Uncompressed |
| GIF | .gif | (none) | 256 colors max |
| ICO | .ico | (none) | Icon format |
| PDF | .pdf | (none) | Multi-page possible |

## Rendering Pipeline

For GIMP CLI, "rendering" means flattening the layer stack with all filters
applied and exporting to a target format.

### Pipeline Steps:
1. Start with canvas (background color or transparent)
2. For each visible layer (bottom to top):
   a. Load/create the layer content
   b. Apply all layer filters in order
   c. Position at layer offset
   d. Composite onto canvas using blend mode and opacity
3. Export final composited image

### Rendering Gap Assessment: **Medium**
- Most operations (resize, crop, filters, compositing) work via Pillow directly
- Advanced GEGL operations (high-pass filter, wavelet decompose) not available
- No XCF round-trip without GIMP installed
- Blend modes require custom implementation but are mathematically straightforward

## Test Coverage Plan

1. **Unit tests** (`test_core.py`): Synthetic data, no real images needed
   - Project create/open/save/info
   - Layer add/remove/reorder/properties
   - Filter application and parameter validation
   - Canvas operations (resize, scale, crop, mode conversion)
   - Session undo/redo
   - JSON project serialization/deserialization

2. **E2E tests** (`test_full_e2e.py`): Real images
   - Full workflow: create project, add layers, apply filters, export
   - Format conversion (PNG->JPEG, etc.)
   - Blend mode compositing verification
   - Filter effect pixel-level verification
   - Multi-layer compositing
   - Text rendering
   - CLI subprocess invocation
