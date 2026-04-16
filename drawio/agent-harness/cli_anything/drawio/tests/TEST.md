# Draw.io CLI — Test Plan & Results

## Test Plan

### Unit Tests (test_core.py)

**XML Utilities (TestDrawioXml)**
- Create blank diagram with correct structure
- System cells (id=0, id=1) always present
- No user cells in blank diagram
- Add vertex with all attributes
- Add edge with source/target
- Remove cell
- Remove vertex also removes connected edges
- Find cell by ID (found and not found)
- Update cell label
- Move cell
- Resize cell
- Get cell info
- Get vertices vs edges
- Write and parse file roundtrip

**Style Parsing (TestStyleParsing)**
- Parse empty style
- Parse key=value pairs
- Parse base style (no value)
- Build style from dict
- Parse-build roundtrip
- Set style property on cell
- Remove style property from cell

**Shape Presets (TestShapePresets)**
- All 15 shape types create valid cells (parametrized)
- All 4 edge styles create valid edges (parametrized)

**Multi-Page Operations (TestPages)**
- Single page by default
- Add page
- Remove page
- Cannot remove last page
- Rename page
- Shapes on different pages are independent

**Session (TestSession)**
- New session is not open
- New project opens session
- Undo/redo single operation
- Multiple undo
- Save and open roundtrip
- Save with no project raises error
- Open nonexistent file raises error
- Status shows correct counts

**Project Module (TestProject)**
- New project with default preset
- New project with all presets
- Invalid preset raises error
- Custom page size
- Save and open roundtrip
- Project info
- Project info with no project raises error
- List presets

**Shapes Module (TestShapes)**
- Add shape
- Add shape with no project raises error
- List shapes
- Remove shape
- Remove nonexistent shape raises error
- Update label
- Move shape
- Resize shape
- Set style
- Get shape info
- List shape types
- All 15 shape types via module (parametrized)
- Undo add shape

**Connectors Module (TestConnectors)**
- Add connector
- Invalid source raises error
- Invalid target raises error
- List connectors
- Remove connector
- Update connector label
- Set connector style
- List edge styles
- All 4 edge styles via module (parametrized)

**Pages Module (TestPagesModule)**
- List pages
- Add page
- Remove page
- Rename page

**Export Module (TestExport)**
- List formats
- Export to XML (no draw.io CLI needed)
- Export with no project raises error
- Invalid format raises error
- File exists raises error

**Complex Workflows (TestWorkflows)**
- Build complete flowchart (4 shapes, 3 connectors, save/reopen)
- Build styled diagram (custom colors, font, shadow)
- Multi-page workflow
- Undo/redo across multiple operations
- Export XML workflow with content verification

### E2E Tests (test_full_e2e.py)

**File Roundtrip (TestFileRoundtrip)**
- Empty diagram save/reopen
- Complex diagram (6 shapes, 4 connectors, styles) roundtrip
- Multi-page diagram roundtrip

**XML Export Verification (TestXmlExport)**
- Export XML with valid structure
- Export XML preserves styles

**Real Draw.io Export (TestRealExport)** — requires draw.io installed
- Export to PNG with magic bytes verification
- Export to SVG with content verification
- Export to PDF with magic bytes verification

**CLI Subprocess (TestCLISubprocess)**
- --help output
- project new --json
- project info --json
- shape add --json
- shape list --json
- shape types --json
- connect styles --json
- export formats --json
- page list --json
- session status --json
- project presets --json
- export XML via subprocess

**Real-World Workflows (TestRealWorldWorkflows)**
- 3-tier web architecture diagram (5 shapes, 4 connectors, styles)
- Entity-relationship diagram (3 entities, 2 relations)
- Decision tree / flowchart (5 nodes, 5 edges)
- Multi-page technical documentation (3 pages, multiple shapes)

## Test Results

```
drawio:  138 passed, 3 skipped (116 unit + 22 e2e)
         3 skipped: real draw.io export (PNG/SVG/PDF) — requires draw.io desktop app
```

**100% pass rate on all available tests.**
