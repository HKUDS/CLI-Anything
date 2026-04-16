# Inkscape: Project-Specific Analysis & SOP

## Architecture Summary

Inkscape is a vector graphics editor whose native format is **SVG (XML)**. This is
a major advantage -- we can directly parse, generate, and manipulate SVG files
using Python's `xml.etree.ElementTree` module. No binary format parsing needed.

```
┌─────────────────────────────────────────────────┐
│                 Inkscape GUI                     │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐   │
│  │  Canvas   │ │  Layers  │ │  Object Props │   │
│  │  (GTK)    │ │  (GTK)   │ │  (GTK)        │   │
│  └────┬──────┘ └────┬─────┘ └──────┬────────┘   │
│       │             │              │             │
│  ┌────┴─────────────┴──────────────┴──────────┐  │
│  │        SVG Document Object Model           │  │
│  │  XML tree of <svg>, <rect>, <circle>,      │  │
│  │  <path>, <text>, <g> elements              │  │
│  └─────────────────┬──────────────────────────┘  │
│                    │                             │
│  ┌─────────────────┴──────────────────────────┐  │
│  │       lib2geom (geometry engine)           │  │
│  │  Path operations, boolean ops, transforms  │  │
│  └─────────────────┬──────────────────────────┘  │
└────────────────────┼────────────────────────────┘
                     │
          ┌──────────┴────────────┐
          │  Cairo/librsvg        │
          │  (SVG rendering)      │
          │  + File format I/O    │
          └───────────────────────┘
```

## CLI Strategy: Direct SVG Manipulation

Unlike GIMP (which has a complex binary .xcf format) or Blender (binary .blend),
Inkscape's SVG format is plain XML. Our strategy:

1. **xml.etree.ElementTree** -- Python's standard XML library for SVG parsing
   and generation. This is our primary engine.
2. **Pillow** -- For PNG rasterization of basic shapes (rect, circle, text, etc.)
3. **Inkscape CLI** -- If available, use `inkscape --actions` for advanced
   operations (PDF export, path boolean ops, text-to-path conversion).

### Why SVG is Ideal for CLI Manipulation

- **Human-readable** -- SVG is XML text, not binary
- **1:1 mapping** -- SVG elements map directly to Inkscape's GUI objects
- **CSS styling** -- Fill, stroke, opacity are CSS properties we can parse/set
- **Standard transforms** -- translate(), rotate(), scale() are SVG attributes
- **DOM structure** -- Layers are <g> elements, gradients in <defs>, etc.
- **Browser viewable** -- Generated SVG can be opened in any browser

## The Project Format (.inkscape-cli.json)

We maintain a JSON project file alongside SVG for state tracking:

```json
{
  "version": "1.0",
  "name": "my_drawing",
  "document": {
    "width": 1920,
    "height": 1080,
    "units": "px",
    "viewBox": "0 0 1920 1080",
    "background": "#ffffff"
  },
  "objects": [
    {
      "id": "rect1",
      "name": "MyRect",
      "type": "rect",
      "x": 100, "y": 100,
      "width": 200, "height": 150,
      "style": "fill:#ff0000;stroke:#000;stroke-width:2",
      "transform": "translate(10, 20) rotate(45)",
      "layer": "layer1"
    }
  ],
  "layers": [
    {
      "id": "layer1",
      "name": "Layer 1",
      "visible": true,
      "locked": false,
      "opacity": 1.0,
      "objects": ["rect1"]
    }
  ],
  "gradients": [
    {
      "id": "linearGradient1",
      "type": "linear",
      "x1": 0, "y1": 0, "x2": 1, "y2": 0,
      "stops": [
        {"offset": 0, "color": "#ff0000", "opacity": 1},
        {"offset": 1, "color": "#0000ff", "opacity": 1}
      ]
    }
  ],
  "metadata": {
    "created": "2024-01-01T00:00:00",
    "modified": "2024-01-01T00:00:00",
    "software": "inkscape-cli 1.0"
  }
}
```

## SVG Element Mapping

| SVG Element | Inkscape Tool | CLI Command |
|-------------|--------------|-------------|
| `<rect>` | Rectangle | `shape add-rect` |
| `<circle>` | Circle | `shape add-circle` |
| `<ellipse>` | Ellipse | `shape add-ellipse` |
| `<line>` | Line | `shape add-line` |
| `<polygon>` | Polygon | `shape add-polygon` |
| `<path>` | Bezier/Pen | `shape add-path` |
| `<text>` | Text | `text add` |
| `<g>` | Layer/Group | `layer add` |
| `<linearGradient>` | Gradient | `gradient add-linear` |
| `<radialGradient>` | Gradient | `gradient add-radial` |
| CSS `style` | Fill/Stroke | `style set-fill`, `style set-stroke` |
| `transform` | Transform | `transform translate/rotate/scale` |

## Command Map: GUI Action -> CLI Command

| GUI Action | CLI Command |
|-----------|-------------|
| File -> New | `document new --width W --height H` |
| File -> Open | `document open <path>` |
| File -> Save | `document save [path]` |
| File -> Export PNG | `export png <output>` |
| File -> Export SVG | `export svg <output>` |
| Draw Rectangle | `shape add-rect --x X --y Y --width W --height H` |
| Draw Circle | `shape add-circle --cx X --cy Y --r R` |
| Draw Star | `shape add-star --points 5 --outer-r 50 --inner-r 25` |
| Edit -> Transform | `transform translate/rotate/scale INDEX` |
| Object -> Fill/Stroke | `style set-fill INDEX COLOR` |
| Layer -> Add | `layer add --name "Name"` |
| Layer -> Reorder | `layer reorder FROM TO` |
| Path -> Union | `path union A B` |
| Path -> Difference | `path difference A B` |
| Path -> Object to Path | `path convert INDEX` |
| Text Tool | `text add --text "Content" --x X --y Y` |
| Edit -> Undo | `session undo` |
| Edit -> Redo | `session redo` |

## Rendering Pipeline

### SVG Generation
1. Create root `<svg>` element with dimensions, viewBox, namespaces
2. Add `<defs>` with gradient definitions
3. Add `<g>` elements for each layer (with inkscape:groupmode="layer")
4. Add shape/text/path elements inside their layer groups
5. Apply style attributes, transforms, gradient references

### PNG Rendering (Pillow)
1. Create blank image at document dimensions
2. For each visible layer (bottom to top):
   - For each object in layer:
     - Parse style (fill, stroke, stroke-width)
     - Draw shape using Pillow's ImageDraw
3. Save as PNG

### Rendering Gap Assessment: **Low**
- SVG is the native format, so SVG export is exact
- PNG rendering via Pillow handles basic shapes (rect, circle, ellipse, line, text)
- Complex SVG features (filters, clip paths, masks) need Inkscape for rendering
- Path boolean operations are stored as metadata; Inkscape needed for actual computation

## Export Formats

| Format | Method | Fidelity |
|--------|--------|----------|
| SVG | Direct XML generation | Exact |
| PNG | Pillow (basic) / Inkscape (full) | Basic shapes / Full |
| PDF | Inkscape CLI | Full |
| EPS | Inkscape CLI | Full |

## Test Coverage Plan

1. **Unit tests** (`test_core.py`): Synthetic data, no real files needed
   - Document create/open/save/info
   - Shape add/remove/duplicate/list for all types
   - Text add/set properties
   - Style set/get for all properties
   - Transform translate/rotate/scale/skew
   - Layer add/remove/reorder/move objects
   - Path boolean operations
   - Gradient create/apply
   - Session undo/redo
   - SVG utility functions

2. **E2E tests** (`test_full_e2e.py`): Real SVG generation
   - SVG XML validity (well-formed, correct namespaces)
   - Document roundtrip (JSON save/load)
   - SVG export and parse-back
   - PNG export (pixel verification)
   - Multi-step workflow scenarios
   - CLI subprocess invocation
