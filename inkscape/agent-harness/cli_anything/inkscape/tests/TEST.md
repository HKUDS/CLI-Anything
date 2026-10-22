# Inkscape CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 11 | 150 | Unit tests for SVG utils, document, shapes, text, styles, transforms, layers, paths, gradients, export, session |
| `test_full_e2e.py` | 5 | 47 | E2E workflows: SVG XML validity, document lifecycle, export, design workflows, CLI subprocess |
| **Total** | **16** | **197** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No Inkscape installation required.

### TestSVGUtils (13 tests)
- Parse CSS style string into dict; parse empty style
- Serialize style dict back to string; serialize empty dict
- Style parse/serialize roundtrip
- Validate color: hex, named colors, rgb() notation; reject invalid colors
- Generate unique element IDs
- Create SVG XML element with attributes
- Serialize SVG document to string
- Find or create `<defs>` element

### TestDocument (17 tests)
- Create document with defaults, custom dimensions, named profile, icon profile
- Reject invalid units and negative/zero dimensions
- Default document has one default layer
- Save to SVG and re-open roundtrip
- Open nonexistent file raises error
- Get document info; set canvas size; reject invalid canvas size
- Set units; reject invalid units
- List available profiles; verify all valid unit types
- Convert project data to SVG XML representation

### TestShapes (23 tests)
- Add rect, circle, ellipse, line, polygon, path, star with valid params
- Reject invalid dimensions (negative width/height, zero radius, empty polygon/path, too-few star points, negative star radius)
- Add rect with custom style and rounded corners
- Remove object by index; reject on empty list and invalid index
- Duplicate object creates independent copy
- List all objects; get object by index
- Unique IDs across all objects
- Objects added to correct layer
- All shape types are registered in the shape type registry

### TestText (11 tests)
- Add text element with content, position, font
- Reject empty text
- Reject invalid font size (zero/negative)
- Set text content, font family, font size on existing text
- Reject invalid font weight and invalid text property
- Reject text operations on non-text objects
- List only text objects
- Text style attribute rebuilt correctly after property changes

### TestStyles (13 tests)
- Set fill color; set stroke color with width
- Reject negative stroke width
- Set opacity; reject out-of-range opacity
- Set arbitrary CSS style property; reject invalid property name; reject invalid choice value
- Get computed style for object
- List all available style properties
- Set fill-opacity; reject invalid fill-opacity range

### TestTransforms (17 tests)
- Translate object by x,y
- Rotate by angle; rotate with custom center point
- Scale uniformly; scale non-uniformly; reject zero scale
- Skew X; skew Y
- Compound (chained) transforms accumulate
- Set transform directly from string
- Clear all transforms
- Parse transform string into structured list
- Parse empty transform string
- Serialize transform list back to string; serialize empty list

### TestLayers (16 tests)
- Add layer; add layer with unique auto-names
- Reject invalid opacity on layer
- Remove layer; reject removing last layer
- Move object between layers
- Set layer properties: visible, locked, opacity, name; reject invalid property
- List layers; reorder layers; get layer by index
- Removing a layer moves its objects to another layer

### TestPaths (13 tests)
- Boolean operations: union, intersection, difference, exclusion
- Reject boolean on same object; reject invalid index
- Convert shapes to path: rect, circle, ellipse, line, polygon
- Convert path to path is no-op
- List available path operations

### TestGradients (12 tests)
- Add linear gradient with defaults and custom stops
- Add radial gradient
- Reject invalid stop list (empty, missing offset, out-of-range offset)
- Apply gradient as fill; apply gradient as stroke; reject invalid target
- List gradients; get gradient by index; remove gradient
- Reject invalid gradient units

### TestExport (2 tests)
- List export presets
- All presets have a format field

### TestSession (13 tests)
- Create session; set/get project; get project when none set raises error
- Undo/redo cycle; undo empty; redo empty
- Snapshot clears redo stack
- Session status reports depth
- Save session to file
- List history; max undo enforced
- Undo reverses shape addition

## End-to-End Tests (`test_full_e2e.py`)

E2E tests generate real SVG XML and validate structure, export to SVG/PNG with PIL, and test CLI subprocess.

### TestSVGValidity (11 tests)
- Empty document SVG is valid XML (parsed by xml.etree)
- SVG has XML declaration
- SVG has correct width/height dimensions
- SVG has viewBox attribute
- SVG has Inkscape namespace declaration
- SVG with shapes is valid XML
- SVG with text elements is valid XML
- SVG with gradients (including defs) is valid XML
- SVG with multiple layers is valid XML
- SVG with transforms is valid XML
- SVG with radial gradient is valid XML

### TestDocumentLifecycle (8 tests)
- Create, save, open roundtrip preserves all fields
- Document with objects roundtrip preserves shape data
- Document with styles roundtrip preserves CSS properties
- Document with layers roundtrip preserves layer structure
- Document with gradients roundtrip preserves gradient definitions
- Document info is complete and accurate
- Complex document roundtrip with shapes, text, layers, gradients, styles
- SVG and JSON representations stay in sync after modifications

### TestExport (8 tests)
- Export to SVG produces valid file on disk
- SVG overwrite protection prevents clobbering
- Exported SVG is valid XML
- Render to PNG produces valid image file (verified with PIL)
- Render to PNG with custom dimensions
- PNG overwrite protection
- Render document with shapes produces non-blank image
- Render star shape produces visible pixels

### TestWorkflows (9 tests)
- Logo design: shapes + text + gradients + layers, export to SVG
- Infographic: multiple shapes with styles, text labels, organized layout
- Multi-layer workflow: background, content, and overlay layers with objects
- Transform workflow: translate, rotate, scale objects in sequence
- Style workflow: set fill, stroke, opacity on multiple objects
- Path operations workflow: create shapes, perform boolean union/difference
- Undo/redo workflow: add objects, undo removals, redo additions
- Gradient workflow: create gradients, apply to shapes, export
- Full document export: complex document with all features, export to SVG and PNG

### TestCLISubprocess (12 tests)
- `--help` prints usage
- `document new` creates document
- `document new --json` outputs valid JSON
- `document profiles` lists profiles
- `shape types` lists all shape types
- `style list-properties` lists CSS properties
- `export presets` lists presets
- `path list-operations` lists boolean operations
- Full workflow via JSON CLI
- CLI error handling returns proper exit codes
- Gradient commands via CLI
- Transform commands via CLI
- Layer commands via CLI

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.11, pytest-9.0.2, pluggy-1.5.0
rootdir: /root/cli-anything
plugins: langsmith-0.5.1, anyio-4.12.0
collected 197 items

test_core.py   150 passed
test_full_e2e.py   47 passed

============================= 197 passed in 1.93s ==============================
```

## Project ID allocation follow-up (PR #567)

`test_project_ids.py` adds 55 public-API regression cases. They cover operation
counts for repeated shape/gradient creation; returned-dictionary ID edits;
mapping mutators including partially failing updates; list insertion, slice and
deletion operations; retained external references; equal-length replacement;
duplicate IDs; copy/deepcopy aliasing; reset; JSON reopen; SVG serialization; and
session undo/redo.

At the original PR head `b0b47edf008888b5808f23b41637590254d250c7`, the initial
52-case selection produced **2 failed, 50 passed**. The final fixed selection produced
**55 passed**, and the existing core suite produced **169 passed**.

Actual core API measurements on Windows / Python 3.12.12, three plain timing
runs per size (median seconds; profiling/counting performed separately):

| Allocations | ID item reads before | ID item reads after | Rect before / after (s) | Linear gradient before / after (s) |
|---:|---:|---:|---:|---:|
| 1,000 | 500,500 | 1 | 0.0105367 / 0.0023271 | 0.0115150 / 0.0019807 |
| 2,000 | 2,001,000 | 1 | 0.0437036 / 0.0043137 | 0.0470259 / 0.0039665 |
| 4,000 | 8,002,000 | 1 | 0.1697078 / 0.0084796 | 0.1848005 / 0.0080804 |
| 8,000 | 32,004,000 | 1 | 0.9205239 / 0.0167863 | 0.8473457 / 0.0162363 |
| 10,000 | 50,005,000 | 1 | 1.2784924 / 0.0203612 | 1.3308895 / 0.0209283 |

Reads count `dict.get` calls on existing items during `generate_id`, excluding
the project mapping. After the fix, collection append/index maintenance still
does linear work. Timing includes the complete `add_rect` or
`add_linear_gradient` loop. Arbitrary external plain collections retain a
conservative scan, and edits to tracked IDs may invalidate other document
indexes. No private index attributes are serialized into project JSON.

The full affected suite was run without installing Inkscape: **276 passed,
5 failed**. The unchanged baseline was **221 passed, 5 failed**. Both runs fail
only Inkscape discovery, version, native PNG, PDF, and dimensioned PNG tests.
Those backend checks remain unverified; the failures were not skipped or
weakened. Independent review reported no blocking issues and independently
reran the 224 core/regression tests successfully.
