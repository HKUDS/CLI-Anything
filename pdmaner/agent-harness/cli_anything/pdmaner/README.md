# cli-anything-pdmaner

CLI harness for **PDManer** (元数建模) — a database modeling tool.

Command-line interface to create, read, update, and manage database models
in PDManer project files (`.chnr.json`).

## Features

- **Project management** — create, open, save project files
- **Entity management** — add/update/delete database tables with fields and indexes
- **View management** — database views referencing entities
- **ER Diagram** — add tables and relations to diagrams
- **Data Dictionary** — manage code-value mappings
- **Domain management** — data type domains with database mappings
- **DDL Export** — generate CREATE TABLE statements for various databases
- **JSON output** — all commands support `--json` for agent consumption
- **REPL mode** — interactive session with undo/redo
- **Session** — state management with undo/redo history

## Installation

```bash
pip install -e .
```

Requires Python 3.9+ and Click.

## Usage

### One-shot commands

```bash
# Create a new project
cli-anything-pdmaner --json project new --name mydb --output mydb.chnr.json

# Open an existing project
cli-anything-pdmaner --project mydb.chnr.json entity list

# Add an entity
cli-anything-pdmaner --project mydb.chnr.json entity add --defkey user --defname "用户表"

# Add a field
cli-anything-pdmaner --project mydb.chnr.json entity add-field user \
  --defkey id --type BIGINT --pk --notnull --autoinc --comment "主键ID"

cli-anything-pdmaner --project mydb.chnr.json entity add-field user \
  --defkey name --type VARCHAR --len 64 --notnull --comment "姓名"

# Export DDL
cli-anything-pdmaner --project mydb.chnr.json export ddl --db MySQL

# Export to SQL file
cli-anything-pdmaner --project mydb.chnr.json export sql -o output.sql --db MySQL
```

### JSON mode (for agent consumption)

```bash
cli-anything-pdmaner --json --project mydb.chnr.json entity list
cli-anything-pdmaner --json --project mydb.chnr.json entity get user
cli-anything-pdmaner --json --project mydb.chnr.json export ddl
```

### Interactive REPL

```bash
cli-anything-pdmaner
cli-anything-pdmaner repl mydb.chnr.json
```

## Command Reference

| Group | Commands |
|-------|----------|
| `project` | new, open, save, info |
| `entity` | list, get, add, update, delete, add-field, update-field, delete-field, add-index, delete-index |
| `view` | list, add, delete |
| `diagram` | list, add, delete, add-table, add-relation |
| `dict` | list, add, delete, add-item, delete-item |
| `domain` | list, add, delete, mappings, supports |
| `export` | ddl, sql |
| `session` | status, undo, redo, save |

## Project File Format

PDManer projects are JSON files with `.chnr.json` extension. The CLI
manipulates these files directly — no PDManer GUI required.

## License

ISC
