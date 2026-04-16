# LibreOffice CLI -- Standard Operating Procedure

## Overview

The LibreOffice CLI harness provides command-line document editing for
Writer (word processor), Calc (spreadsheet), and Impress (presentations).
It produces real ODF files (ZIP archives with XML) that can be opened by
LibreOffice and other ODF-compatible applications.

## Architecture

```
cli/
  __init__.py
  __main__.py              # python3 -m cli.libreoffice_cli entry point
  libreoffice_cli.py       # Click CLI with groups and REPL
  core/
    __init__.py
    document.py            # create/open/save/info/profiles
    writer.py              # paragraphs, headings, lists, tables, page breaks
    calc.py                # sheets, cells, formulas
    impress.py             # slides, elements
    styles.py              # named styles, apply to content
    export.py              # ODF, HTML, text export
    session.py             # undo/redo state management
  utils/
    __init__.py
    odf_utils.py           # ODF XML generation and ZIP packaging
  tests/
    __init__.py
    test_core.py           # 60+ unit tests
    test_full_e2e.py       # 40+ E2E tests with ODF validation
```

## Project Format

Documents are stored as JSON project files (`.lo-cli.json`) with this structure:

- **Writer**: `{"type": "writer", "content": [...], "styles": {...}, "settings": {...}}`
- **Calc**: `{"type": "calc", "sheets": [...], "styles": {...}, "settings": {...}}`
- **Impress**: `{"type": "impress", "slides": [...], "styles": {...}, "settings": {...}}`

## Key Design Decisions

1. **Python stdlib only** (plus click): No Pillow, numpy, or LibreOffice needed
2. **Real ODF output**: ZIP files with proper mimetype, content.xml, styles.xml, meta.xml, manifest.xml
3. **Undo/redo**: Deep-copy snapshots before every mutation
4. **Multi-format**: Same CLI handles Writer, Calc, and Impress
5. **JSON mode**: `--json` flag for agent consumption

## Running

```bash
cd /root/cli-anything/libreoffice/agent-harness
pip install click
python3 -m cli.libreoffice_cli --help
python3 -m pytest cli/tests/ -v
```

## Common Workflows

### Create a Writer document and export to ODF
```bash
python3 -m cli.libreoffice_cli document new --type writer -n "Report" -o report.json
python3 -m cli.libreoffice_cli --project report.json writer add-heading -t "Title" -l 1
python3 -m cli.libreoffice_cli --project report.json writer add-paragraph -t "Body text"
python3 -m cli.libreoffice_cli --project report.json export render report.odt -p odt --overwrite
```

### Create a spreadsheet
```bash
python3 -m cli.libreoffice_cli document new --type calc -o budget.json
python3 -m cli.libreoffice_cli --project budget.json calc set-cell A1 "Revenue" --type string
python3 -m cli.libreoffice_cli --project budget.json calc set-cell B1 "50000" --type float
python3 -m cli.libreoffice_cli --project budget.json export render budget.ods -p ods --overwrite
```

### Create a presentation
```bash
python3 -m cli.libreoffice_cli document new --type impress -o deck.json
python3 -m cli.libreoffice_cli --project deck.json impress add-slide -t "Welcome" -c "Hello"
python3 -m cli.libreoffice_cli --project deck.json export render deck.odp -p odp --overwrite
```
