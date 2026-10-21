---
name: "cli-anything-pdmaner"
description: "PDManer CLI — command-line database modeling with entity/view/diagram/dict management and DDL export"
---

# cli-anything-pdmaner

CLI harness for **PDManer (元数建模)** — an open-source database modeling tool.
Manipulate `.chnr.json` project files for entity, view, ER diagram, dictionary, and
domain management. Generate DDL for MySQL, PostgreSQL, Oracle, and more.

## Prerequisites

- Python 3.9+
- Click 8.0+

```bash
pip install -e .
```

## Command Groups

### project — Project Management

| Command | Description |
|---------|-------------|
| `project new -n <name> [-d describe] [-o path]` | Create new project |
| `project open <path>` | Open existing .chnr.json |
| `project save [-o path]` | Save current project |
| `project info` | Show project summary |

### entity — Entity (Table) Management

| Command | Description |
|---------|-------------|
| `entity list` | List all entities |
| `entity get <id>` | Get entity details |
| `entity add -k <defkey> [-n defname] [-c comment] [-t type]` | Add entity |
| `entity update <id> [-k defkey] [-n defname] [-c comment]` | Update entity |
| `entity delete <id>` | Delete entity |
| `entity add-field <entity> -k <defkey> [options]` | Add field to entity |
| `entity update-field <entity> <field> [options]` | Update field |
| `entity delete-field <entity> <field>` | Delete field |
| `entity add-index <entity> -k <defkey> [-f fields...] [--unique]` | Add index |
| `entity delete-index <entity> <index>` | Delete index |

Field options: `--type`, `--len`, `--scale`, `--pk/--no-pk`, `--notnull/--null`,
`--autoinc/--no-autoinc`, `--comment`, `--default`

### export — DDL Export

| Command | Description |
|---------|-------------|
| `export ddl [-d db] [-e entity] [--drop]` | Generate CREATE TABLE DDL |
| `export sql -o <path> [-d db] [--drop]` | Export DDL to SQL file |

### view — View Management

| Command | Description |
|---------|-------------|
| `view list` | List all views |
| `view add -k <defkey> [-n defname]` | Add view |
| `view delete <id>` | Delete view |

### diagram — ER Diagram

| Command | Description |
|---------|-------------|
| `diagram list` | List diagrams |
| `diagram add -k <defkey> [-n defname] [-t type]` | Add diagram |
| `diagram delete <id>` | Delete diagram |
| `diagram add-table <diagram> <entity> [--x X] [--y Y]` | Add table node |
| `diagram add-relation <diagram> -s <src> -t <tgt> --source-field <f> --target-field <f> [-r rel]` | Add ER edge |

### dict — Dictionary

| Command | Description |
|---------|-------------|
| `dict list` | List dictionaries |
| `dict add -k <defkey> [-n defname]` | Add dictionary |
| `dict delete <id>` | Delete dictionary |
| `dict add-item <dict> -k <defkey> [-n defname]` | Add dictionary item |
| `dict delete-item <dict> <item>` | Delete dictionary item |

### domain — Data Type Domain

| Command | Description |
|---------|-------------|
| `domain list` | List domains |
| `domain add -k <defkey> [-n defname] [-a applyfor] [-l len] [-s scale]` | Add domain |
| `domain delete <id>` | Delete domain |
| `domain mappings` | List data type mappings |
| `domain supports` | List supported DB types |

### session — Session

| Command | Description |
|---------|-------------|
| `session status` | Show session state |
| `session undo` | Undo last change |
| `session redo` | Redo last undone change |
| `session save` | Save current project |

## Agent Usage

All commands support `--json` for machine-readable output. Use `--project <path>`
to operate on a specific project file in one-shot mode.

```bash
# JSON mode — all output is parseable JSON
cli-anything-pdmaner --json --project mydb.chnr.json entity list
cli-anything-pdmaner --json --project mydb.chnr.json export ddl

# Full pipeline example
cli-anything-pdmaner --json project new -n mydb -o mydb.chnr.json
cli-anything-pdmaner --json --project mydb.chnr.json entity add -k users -n "Users"
cli-anything-pdmaner --json --project mydb.chnr.json entity add-field users -k id --type BIGINT --pk --notnull --autoinc
cli-anything-pdmaner --json --project mydb.chnr.json export sql -o output.sql --db MySQL
```

## Project File Format

`.chnr.json` files are JSON with this top-level structure:
- `entities[]` — data tables with fields, indexes, correlations
- `views[]` — database views
- `diagrams[]` — ER canvas with table nodes and relation edges
- `dicts[]` — data dictionaries (code-value mappings)
- `domains[]` — data type domain definitions
- `dataTypeMapping.mappings[]` — type mappings per database
- `viewGroups[]` — logical groups of entities/views/diagrams
- `profile` — settings, database types, code templates, naming rules
