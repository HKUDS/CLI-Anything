# LibreOffice CLI

A stateful command-line interface for document editing, producing real ODF
files (ZIP archives with XML). Designed for AI agents and power users who
need to create and manipulate Writer, Calc, and Impress documents without
a GUI or LibreOffice installation.

## Prerequisites

- Python 3.10+
- `click` (CLI framework)

No other dependencies required -- uses Python stdlib (`zipfile`,
`xml.etree.ElementTree`, `json`) for ODF generation.

## Install Dependencies

```bash
pip install click
```

## How to Run

All commands are run from the `agent-harness/` directory.

### One-shot commands

```bash
# Show help
python3 -m cli.libreoffice_cli --help

# Create a new Writer document
python3 -m cli.libreoffice_cli document new --type writer --name "Report" -o report.json

# Create with a page profile
python3 -m cli.libreoffice_cli document new --profile a4_portrait -o project.json

# Open a project and show info
python3 -m cli.libreoffice_cli --project project.json document info

# JSON output (for agent consumption)
python3 -m cli.libreoffice_cli --json --project project.json document info
```

### Interactive REPL

```bash
python3 -m cli.libreoffice_cli repl
python3 -m cli.libreoffice_cli repl --project my_project.json
```

Inside the REPL, type `help` for all available commands.

## Command Reference

### Document

```bash
document new [--type writer|calc|impress] [--name N] [--profile P] [-o path]
document open <path>
document save [path]
document info
document profiles
document json
```

Available profiles: `a4_portrait`, `a4_landscape`, `letter_portrait`,
`letter_landscape`, `legal_portrait`, `presentation_16_9`, `presentation_4_3`

### Writer (Word Processor)

```bash
writer add-paragraph [--text T] [--position P] [--font-size S] [--bold] [--italic] [--alignment A]
writer add-heading [--text T] [--level 1-6] [--position P]
writer add-list [--items I ...] [--style bullet|number] [--position P]
writer add-table [--rows R] [--cols C] [--position P]
writer add-page-break [--position P]
writer remove <index>
writer list
writer set-text <index> <text>
```

### Calc (Spreadsheet)

```bash
calc add-sheet [--name N] [--position P]
calc remove-sheet <index>
calc rename-sheet <index> <name>
calc set-cell <ref> <value> [--type string|float] [--sheet S] [--formula F]
calc get-cell <ref> [--sheet S]
calc list-sheets
```

### Impress (Presentations)

```bash
impress add-slide [--title T] [--content C] [--position P]
impress remove-slide <index>
impress set-content <index> [--title T] [--content C]
impress list-slides
impress add-element <slide_index> [--type text_box] [--text T] [--x X] [--y Y]
```

### Styles

```bash
style create <name> [--family paragraph|text] [--parent P] [--prop key=value ...]
style modify <name> [--prop key=value ...]
style list
style apply <style_name> <content_index>
style remove <name>
```

Style properties: `font_size`, `font_name`, `bold`, `italic`, `underline`,
`color`, `alignment`, `line_height`, `margin_top`, `margin_bottom`

### Export

```bash
export presets
export preset-info <name>
export render <output> [--preset odt|ods|odp|html|text] [--overwrite]
```

### Session

```bash
session status
session undo
session redo
session history
```

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
python3 -m cli.libreoffice_cli --json --project p.json writer list
```

## Running Tests

```bash
cd agent-harness
python3 -m pytest cli/tests/test_core.py -v        # Unit tests
python3 -m pytest cli/tests/test_full_e2e.py -v     # E2E tests (ODF validation)
python3 -m pytest cli/tests/ -v                      # All tests
```

## Example Workflow

```bash
# Create a Writer document
python3 -m cli.libreoffice_cli document new --type writer --name "Quarterly Report" -o report.json

# Add content
python3 -m cli.libreoffice_cli --project report.json writer add-heading -t "Q1 Report" -l 1
python3 -m cli.libreoffice_cli --project report.json writer add-paragraph -t "Revenue grew by 15%."
python3 -m cli.libreoffice_cli --project report.json writer add-table --rows 3 --cols 2
python3 -m cli.libreoffice_cli --project report.json writer add-list -i "Product A" -i "Product B"

# Create and apply a style
python3 -m cli.libreoffice_cli --project report.json style create "Emphasis" --prop bold=true --prop color=#cc0000
python3 -m cli.libreoffice_cli --project report.json style apply "Emphasis" 1

# Save and export
python3 -m cli.libreoffice_cli --project report.json document save
python3 -m cli.libreoffice_cli --project report.json export render report.odt --preset odt --overwrite
python3 -m cli.libreoffice_cli --project report.json export render report.html --preset html --overwrite
```

## ODF Format

Exported ODF files are valid ZIP archives containing:
- `mimetype` (uncompressed, first entry) -- identifies the document type
- `content.xml` -- document content in ODF XML
- `styles.xml` -- document styles
- `meta.xml` -- metadata (title, author, dates)
- `META-INF/manifest.xml` -- manifest of all files

These files can be opened by LibreOffice, Apache OpenOffice, and other
ODF-compatible applications.
