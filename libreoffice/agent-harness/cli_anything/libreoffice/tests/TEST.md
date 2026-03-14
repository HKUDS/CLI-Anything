# LibreOffice CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 6 | 96 | Unit tests for document, Writer, Calc, Impress, styles, session |
| `test_full_e2e.py` | 9 | 47 | E2E workflows: ODF ZIP structure, XML validity, export formats, CLI subprocess |
| **Total** | **15** | **143** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No LibreOffice installation required.

### TestDocument (15 tests)
- Create Writer, Calc, and Impress documents
- Create with custom name and named profile (A4, Letter)
- Reject invalid document type and invalid profile
- Save and open roundtrip
- Open nonexistent file raises error; open invalid file raises error
- Get document info for Writer and Calc
- List available profiles
- Metadata populated on creation (title, created date)

### TestWriter (18 tests)
- Add paragraph with default and custom style
- Add heading; headings support levels 1-6; reject invalid level
- Add bullet list and numbered list; reject invalid list style
- Add table with dimensions; add table with initial data; reject invalid table dimensions
- Add page break
- Add content at specific position; reject invalid position
- Remove content by index; reject remove on empty document
- List all content elements; get content by index
- Set text content on paragraph; reject set text on table element
- Writer operations reject Calc documents

### TestCalc (13 tests)
- Add sheet; reject duplicate sheet name
- Remove sheet; reject removing last sheet
- Rename sheet
- Set cell with string, float, and formula values
- Get cell value; get empty cell returns None
- Clear cell
- Reject invalid cell reference (bad format)
- List sheets; get sheet data as grid
- Calc operations reject Writer documents
- Cell references are case-insensitive

### TestImpress (13 tests)
- Add slide; add slide at specific position
- Remove slide; reject remove on empty presentation
- Set slide content (title, body text)
- Add element to slide (textbox, image, shape); remove element
- Move slide to new position
- Duplicate slide creates independent copy
- List slides; get slide by index
- Impress operations reject Writer documents
- Reject invalid element type

### TestStyles (11 tests)
- Create style with family and properties
- Reject duplicate style name; reject invalid family; reject invalid property
- Modify existing style properties; reject modify on nonexistent style
- Remove style
- List styles; get style by name
- Apply style to Writer content; reject apply on non-Writer document; reject nonexistent style

### TestSession (13 tests)
- Create session; set/get project; get project when none set raises error
- Undo/redo cycle; undo empty; redo empty
- Snapshot clears redo stack
- Session status reports depth
- Save session to file
- List history; max undo enforced
- Multiple undo operations in sequence

## End-to-End Tests (`test_full_e2e.py`)

E2E tests produce real ODF files (ODT/ODS/ODP) and validate ZIP structure, XML content, and export to HTML/text.

### TestODFStructure (10 tests)
- ODT file is a valid ZIP archive
- Mimetype entry is first in ZIP and stored uncompressed
- Mimetype content matches `application/vnd.oasis.opendocument.text`
- ODT contains required files: content.xml, styles.xml, meta.xml, META-INF/manifest.xml
- content.xml is valid XML
- styles.xml is valid XML
- meta.xml is valid XML
- ODF validate utility passes
- ODS file has correct structure and mimetype
- ODP file has correct structure and mimetype

### TestWriterE2E (4 tests)
- Full document with paragraphs, headings, tables, lists exports to valid ODT
- Styled paragraph appears in ODT content.xml
- Export to HTML produces valid HTML with content
- Export to plain text produces readable text

### TestCalcE2E (3 tests)
- Multi-sheet spreadsheet exports to valid ODS with correct cell data in XML
- Export to HTML produces table markup
- Export to plain text produces CSV-like output

### TestImpressE2E (3 tests)
- Multi-slide presentation exports to valid ODP
- Presentation with elements (textboxes, images) in ODP
- Export to HTML produces slide content

### TestExportEdgeCases (10 tests)
- Overwrite protection prevents clobbering existing files
- Overwrite allowed when force flag is set
- Export empty Writer document
- Export empty Calc document
- Export empty Impress document
- Export with ODT preset
- Export with HTML preset
- Export with text preset
- Reject invalid export preset
- List all export presets

### TestStylesInODF (2 tests)
- Custom style appears in ODT styles.xml
- Page layout properties appear in styles.xml

### TestProjectLifecycle (3 tests)
- Create, save, open roundtrip preserves all content
- Complex project roundtrip with paragraphs, headings, tables, styles
- Calc project roundtrip preserves sheets, cells, and formulas

### TestSessionIntegration (4 tests)
- Undo reverses paragraph addition
- Undo reverses cell value change
- Undo reverses slide addition
- Undo reverses style creation

### TestCLISubprocess (8 tests)
- `--help` prints usage
- `document new` creates document
- `document new --json` outputs valid JSON
- `document profiles` lists profiles
- `export presets` lists presets
- Full Writer workflow via JSON CLI
- Calc workflow via JSON CLI
- Impress workflow via JSON CLI

### TestODFContent (7 tests)
- Writer heading appears in content.xml with correct outline level
- Writer table appears in content.xml with rows and cells
- Writer list appears in content.xml with list items
- Calc cells appear in content.xml with correct values
- Impress slides appear in content.xml as draw:page elements
- meta.xml has document title
- manifest.xml has required media-type entries

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.11, pytest-9.0.2, pluggy-1.5.0
rootdir: ~/cli-anything
plugins: langsmith-0.5.1, anyio-4.12.0
collected 143 items

test_core.py   96 passed
test_full_e2e.py   47 passed

============================= 143 passed in 2.25s ==============================
```
