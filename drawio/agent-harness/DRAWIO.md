# Draw.io — CLI Harness Analysis & SOP

## Software Overview

**Draw.io** (diagrams.net) is a free, open-source diagramming tool. The desktop version is built on Electron and supports creating flowcharts, architecture diagrams, ER diagrams, UML, network diagrams, and more.

## Architecture

### File Format: mxGraph XML (.drawio)

Draw.io uses an XML-based format built on the mxGraph library:

```xml
<mxfile host="cli-anything" agent="cli-anything-drawio/1.0.0">
  <diagram id="..." name="Page-1">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10"
                  page="1" pageWidth="850" pageHeight="1100">
      <root>
        <mxCell id="0"/>                              <!-- root container -->
        <mxCell id="1" parent="0"/>                   <!-- default layer -->
        <mxCell id="v_123" value="Server"             <!-- shape (vertex) -->
                style="rounded=1;fillColor=#dae8fc;"
                vertex="1" parent="1">
          <mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>
        </mxCell>
        <mxCell id="e_456" value="query"              <!-- connector (edge) -->
                style="edgeStyle=orthogonalEdgeStyle;"
                edge="1" source="v_123" target="v_789" parent="1">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Key properties:**
- Plain-text XML — fully parseable and writable by the CLI
- Multi-page support: multiple `<diagram>` elements under `<mxfile>`
- System cells: `id="0"` (root) and `id="1"` (default layer) are always present
- Shapes: `<mxCell vertex="1">` with `<mxGeometry>` for position/size
- Edges: `<mxCell edge="1" source="..." target="...">`
- Styles: semicolon-delimited key=value pairs in the `style` attribute

### Rendering Pipeline

**Primary: draw.io desktop CLI**
```
.drawio file → draw.io --export --format png → rendered image
```

The desktop Electron app supports headless export:
- `draw.io --export input.drawio --output out.png --format png`
- `draw.io --export input.drawio --output out.pdf --format pdf`
- `draw.io --export input.drawio --output out.svg --format svg`

**Fallback: direct XML write**
When draw.io CLI is not installed, the CLI saves the `.drawio` file directly.
Users can open it in draw.io (web or desktop) for manual export.

## CLI Strategy

### What we manipulate directly (no GUI needed):
- **Project lifecycle**: create blank XML, parse existing files, write to disk
- **Shapes**: add/remove/move/resize `<mxCell vertex="1">` elements
- **Connectors**: add/remove `<mxCell edge="1">` with source/target references
- **Styles**: parse/modify the `style` attribute string
- **Pages**: add/remove/rename `<diagram>` elements
- **Labels**: set the `value` attribute on any cell

### What we delegate to draw.io CLI:
- **Raster export**: PNG, PDF rendering (requires the Electron app)
- **SVG export**: Vector rendering with proper font/text handling

## Shape Registry

| CLI Name | Style Base | Description |
|----------|-----------|-------------|
| rectangle | `rounded=0;whiteSpace=wrap;html=1` | Standard rectangle |
| rounded | `rounded=1;whiteSpace=wrap;html=1` | Rounded rectangle |
| ellipse | `ellipse;whiteSpace=wrap;html=1` | Circle/oval |
| diamond | `rhombus;whiteSpace=wrap;html=1` | Decision diamond |
| triangle | `triangle;whiteSpace=wrap;html=1` | Triangle |
| hexagon | `shape=hexagon;...` | Hexagon |
| cylinder | `shape=cylinder3;...` | Database cylinder |
| cloud | `ellipse;shape=cloud;...` | Cloud shape |
| parallelogram | `shape=parallelogram;...` | Parallelogram |
| process | `shape=process;...` | Process box |
| document | `shape=document;...` | Document shape |
| callout | `shape=callout;...` | Speech callout |
| note | `shape=note;...` | Sticky note |
| actor | `shape=mxgraph.basic.person;...` | Person/actor |
| text | `text;html=1;align=center;...` | Text label |

## Edge Style Registry

| CLI Name | Style | Description |
|----------|-------|-------------|
| straight | `edgeStyle=none` | Straight line |
| orthogonal | `edgeStyle=orthogonalEdgeStyle;rounded=0` | Right-angle routing |
| curved | `edgeStyle=orthogonalEdgeStyle;curved=1;rounded=1` | Curved routing |
| entity-relation | `edgeStyle=entityRelationEdgeStyle` | ER diagram style |

## Style Properties

Common style keys applicable to shapes and connectors:

| Key | Values | Description |
|-----|--------|-------------|
| fillColor | `#rrggbb` | Shape fill color |
| strokeColor | `#rrggbb` | Border/line color |
| fontColor | `#rrggbb` | Text color |
| fontSize | integer | Font size in points |
| fontStyle | 0/1/2/4 | 0=normal, 1=bold, 2=italic, 4=underline |
| opacity | 0-100 | Opacity percentage |
| rounded | 0/1 | Rounded corners |
| shadow | 0/1 | Drop shadow |
| dashed | 0/1 | Dashed border/line |
| strokeWidth | number | Border/line width |
| endArrow | classic/block/open/none | Arrow head style |
| startArrow | classic/block/open/none | Arrow tail style |

## Test Coverage

- **Unit tests**: XML manipulation, style parsing, all shape/edge presets, session undo/redo, multi-page operations, complex workflows
- **E2E tests**: file roundtrip, XML export verification, real draw.io export (PNG/SVG/PDF with magic byte checks), CLI subprocess, real-world diagram scenarios
