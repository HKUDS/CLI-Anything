# GIMP CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 5 | 66 | Unit tests for project, layers, filters, canvas, session |
| `test_full_e2e.py` | 9 | 37 | E2E workflows with real image I/O and pixel verification |
| **Total** | **14** | **103** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No external files or disk I/O required.

### TestProject (9 tests)
- Create project with defaults, custom dimensions, and named profiles
- Reject invalid color modes and negative/zero dimensions
- Save to JSON and re-open roundtrip
- Open nonexistent file raises error
- Get project info and list available profiles

### TestLayers (19 tests)
- Add single and multiple layers; add at specific position
- Reject invalid blend mode and out-of-range opacity
- Remove layer by index; reject invalid index
- Duplicate layer, move layer between positions
- Set properties: opacity, visible, name; reject invalid property
- Get single layer and list all layers
- Verify layer IDs are unique across additions
- Solid color layer and text layer creation

### TestFilters (16 tests)
- List all available filters; list by category
- Get filter info; unknown filter raises error
- Validate filter params with defaults; reject out-of-range values; reject unknown filter
- Add filter to layer; reject invalid layer index; reject unknown filter name
- Remove filter from layer
- Set filter param on existing filter
- List filters on a layer
- All registered filters have a valid engine field

### TestCanvas (11 tests)
- Resize canvas with default and custom anchor
- Reject invalid (zero/negative) canvas size
- Scale canvas proportionally
- Crop canvas; reject out-of-bounds and invalid crop regions
- Set color mode; reject invalid mode
- Set DPI
- Get canvas info returns correct dimensions/mode/DPI

### TestSession (11 tests)
- Create session; set and get project; get project when none set raises error
- Undo/redo cycle preserves state
- Undo on empty stack is no-op; redo on empty stack is no-op
- New snapshot clears redo stack
- Session status reports undo/redo depth
- Save session to file
- List history entries
- Max undo limit enforced

## End-to-End Tests (`test_full_e2e.py`)

E2E tests use real files: PNG images via PIL/Pillow, numpy arrays for pixel-level verification.

### TestProjectLifecycle (3 tests)
- Create, save, and open project roundtrip preserving all fields
- Project with layers survives save/load roundtrip
- Project info reflects accurate layer counts after additions

### TestLayerOperations (2 tests)
- Add layer from a real image file (PIL Image saved to temp file)
- Multiple layers maintain correct ordering

### TestFilterRendering (7 tests)
- Brightness filter increases pixel values (verified with numpy mean)
- Contrast filter increases pixel spread (verified with numpy std)
- Invert filter flips all color values
- Gaussian blur reduces high-frequency content
- Sepia filter applies correct color cast
- Multiple filters chain together correctly
- Horizontal flip mirror-reverses pixel columns

### TestExportFormats (4 tests)
- Export to JPEG produces valid JPEG file
- Export to WebP produces valid WebP file
- Export to BMP produces valid BMP file
- Overwrite protection prevents clobbering existing files

### TestBlendModes (3 tests)
- Multiply mode darkens output compared to base layer
- Screen mode brightens output compared to base layer
- Difference mode produces expected pixel delta

### TestCanvasRendering (1 test)
- Scale canvas and export; verify output image dimensions match

### TestMediaProbing (5 tests)
- Probe PNG file returns correct dimensions and format
- Probe JPEG file returns correct info
- Probe nonexistent file raises error
- Check media reports all files present
- Check media reports missing files

### TestSessionIntegration (2 tests)
- Undo reverses a layer addition
- Undo reverses a filter addition

### TestCLISubprocess (7 tests)
- `--help` prints usage info
- `project new` creates a project
- `project new --json` returns valid JSON output
- `project profiles` lists available profiles
- `filter list-available` lists all filters
- `export presets` lists export presets
- Full workflow via JSON CLI (create, add layer, add filter, export)

### TestRealWorldWorkflows (5 tests)
- Photo editing workflow: open image, adjust brightness/contrast, apply sharpen, export
- Collage workflow: create canvas, add multiple image layers, position them, export
- Text overlay workflow: add text layer over image, style it, export
- Batch filter workflow: apply same filter chain to multiple layers
- Save and load complex project with many layers, filters, and settings

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.11, pytest-9.0.2, pluggy-1.5.0
rootdir: ./CLI-Anything
plugins: langsmith-0.5.1, anyio-4.12.0
collected 103 items

test_core.py   66 passed
test_full_e2e.py   37 passed

============================= 103 passed in 3.05s ==============================
```
