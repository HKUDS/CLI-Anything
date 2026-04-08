# sketch-harness

CLI tool to generate `.sketch` files from JSON design specs — a [CLI-Anything](https://github.com/anthropics/CLI-Anything) harness for Sketch.

## Installation

```bash
cd sketch/agent-harness
npm install
```

Requires **Node.js >= 16**.

## Commands

### `build` — Generate a .sketch file from a JSON spec

```bash
node src/cli.js build --input <spec.json> --output <output.sketch> [--tokens <tokens.json>]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--input, -i` | Yes | Path to JSON design spec |
| `--output, -o` | Yes | Output .sketch file path |
| `--tokens, -t` | No | Custom tokens file (overrides spec-level tokens) |

### `list-styles` — List available predefined styles

```bash
node src/cli.js list-styles [--tokens <tokens.json>]
```

## JSON Spec Format

```json
{
  "tokens": "./tokens/default.json",
  "pages": [
    {
      "name": "Page Name",
      "artboards": [
        {
          "name": "Artboard Name",
          "width": 375,
          "height": 812,
          "backgroundColor": "#FFFFFF",
          "layout": { "type": "vertical-stack", "paddingTop": 80, "paddingHorizontal": 24, "gap": 16 },
          "layers": [
            { "type": "text", "name": "title", "value": "Hello", "style": "$heading1" },
            { "type": "rectangle", "name": "btn", "width": "fill", "height": 48, "style": "$primaryButton",
              "label": { "value": "Submit", "style": "$buttonText" } },
            { "type": "group", "name": "row", "layout": { "type": "horizontal-stack", "gap": 12 },
              "children": [ ] }
          ]
        }
      ]
    }
  ]
}
```

### Layer Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `text` | Text layer | `value`, `style` (fontSize, color, textAlign...) |
| `rectangle` | Rectangle | `style` (backgroundColor, cornerRadius...), `label` |
| `oval` | Ellipse / Circle | Same as rectangle |
| `group` | Container | `children`, `layout` |
| `line` | Line | `color`, `thickness` |
| `spacer` | Invisible spacer | `height` |

### Layout Modes

- **vertical-stack** — Children flow top-to-bottom. Supports `gap`, `paddingTop`/`paddingBottom`/`paddingHorizontal`, `alignItems` (left / center / right).
- **horizontal-stack** — Children flow left-to-right. Supports `gap`, `justifyContent` (start / center / end / space-between), `alignItems` (top / center / bottom).
- **absolute** — Children positioned manually via `x` / `y`.

### Sizing

- `width: "fill"` — Stretch to fill parent container width.
- Text layers without explicit dimensions are auto-sized based on font size.

## Design Tokens

Reference tokens in `style` fields with the `$` prefix:

| Syntax | Resolves to |
|--------|-------------|
| `"style": "$heading1"` | `tokens.styles.$heading1` (full style object) |
| `"color": "$primary"` | `tokens.colors.primary` |
| `"cornerRadius": "$lg"` | `tokens.radius.lg` |

See [`tokens/default.json`](tokens/default.json) for the built-in token set (colors, spacing, radius, shadows, typography styles).

## Examples

Three example specs are included in [`examples/`](examples/):

```bash
# Mobile login page
node src/cli.js build -i examples/login-page.json -o output/login-page.sketch

# Desktop dashboard
node src/cli.js build -i examples/dashboard.json -o output/dashboard.sketch

# Card list
node src/cli.js build -i examples/card-list.json -o output/card-list.sketch

# Build all examples at once
npm run build:all
```

## Tests

```bash
npm test
```

Runs Jest tests that verify `.sketch` output is a valid ZIP containing the expected Sketch document structure.

## Project Structure

```
src/
  cli.js          # CLI entry point (Commander.js)
  builder.js      # Orchestrates spec → Sketch file generation
  layout.js       # Layout engine (vertical/horizontal/absolute stacking)
  primitives.js   # Layer primitives (text, rectangle, oval, line, group)
tokens/
  default.json    # Built-in design token set
examples/         # Sample JSON specs
output/           # Generated .sketch files
tests/
  build.test.js   # Build pipeline tests
```

## Agent Workflow

1. Write a JSON spec describing your design.
2. Run `node src/cli.js build -i spec.json -o design.sketch`.
3. Verify the output file was generated (valid ZIP).
4. Open in Sketch or [Lunacy](https://icons8.com/lunacy) (free, cross-platform) to inspect the result.
