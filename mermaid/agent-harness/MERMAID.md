# Mermaid Live Editor - CLI Harness Analysis

## Software Overview

**Mermaid Live Editor** is the official browser editor for Mermaid diagrams. It edits Mermaid source text, previews diagrams in real time, generates shareable URLs, and renders diagrams through the Mermaid renderer service.

## Architecture

### State model

The live editor centers around a serialized state object. The fields relevant to the CLI are:

- `code`: Mermaid diagram source
- `mermaid`: Mermaid config JSON string
- `updateDiagram`: whether the view should refresh
- `rough`: rough-sketch rendering toggle
- `panZoom`: pan/zoom enablement
- `grid`: editor grid toggle

For the CLI harness, this state is stored as a JSON project file with a `.mermaid.json` suffix.

### Native share/render format

The live editor serializes its state as:

1. compact JSON
2. zlib compression
3. URL-safe base64
4. `pako:` prefix

That serialized token is used by the official endpoints:

- Edit URL: `https://mermaid.live/edit#<serialized>`
- View URL: `https://mermaid.live/view#<serialized>`
- SVG URL: `https://mermaid.ink/svg/<serialized>`
- PNG URL: `https://mermaid.ink/img/<serialized>?type=png`

## Backend strategy

This harness uses the same renderer path that Mermaid Live Editor uses in production. The backend module generates the same serialized state payload and invokes the official Mermaid renderer endpoint.

That keeps the harness aligned with the actual application instead of inventing a parallel diagram format.

## CLI scope

- `project new/open/save/info/samples`
- `diagram set/show`
- `export render/share`
- `session status/undo/redo`
- REPL mode by default

## Expected validation

The CLI should prove that an agent can:

1. create a Mermaid project
2. update diagram text
3. inspect current source
4. generate live-editor share/view URLs
5. render a real SVG and PNG artifact
