# TEST.md — cli-anything-pdmaner Test Plan & Results

## Test Inventory Plan

| File | Planned Tests | Type |
|------|--------------|------|
| `test_core.py` | 25+ | Unit tests (synthetic data) |
| `test_full_e2e.py` | 15+ | E2E + CLI subprocess tests |

## Unit Test Plan

### `project.py`
- `create_project()` — creates valid project with name, describe, timestamps
- `open_project()` — reads existing JSON, adds _path and _modified
- `save_project()` — writes to file, updates timestamps
- `get_project_info()` — returns correct counts
- Edge: missing path, empty entities

### `entity.py`
- `add_entity()` — adds entity to project with correct structure
- `get_entity()` — finds by id and defKey
- `delete_entity()` — removes entity and cleans diagrams/viewGroups
- `add_field()` — adds field with all properties
- `update_field()` — updates specific field properties
- `delete_field()` — removes field
- `add_index()` / `delete_index()` — index CRUD
- Edge: duplicate defKey, delete non-existent

### `export_.py`
- `generate_ddl()` — generates correct CREATE TABLE from entities
- `_format_type()` — correct length/scale for VARCHAR, DECIMAL, etc.
- `export_sql()` — writes to file
- Edge: entity without fields, VARCHAR without length

### `dict_.py`
- `add_dict()` / `get_dict()` / `delete_dict()`
- `add_dict_item()` / `delete_dict_item()`
- Edge: duplicate items

### `session.py`
- `Session.create()` / `Session.load()` — initializes session
- `Session.undo()` / `Session.redo()` — history navigation
- `Session.save()` — persists to file
- `Session.status()` — reports correct state
- Edge: undo at beginning, redo at end

## E2E Test Plan

### Workflow 1: Project Creation Pipeline
1. Create new project via CLI
2. Add 2 entities with fields
3. Add ER diagram with relation
4. Export DDL
5. Verify DDL contains expected SQL statements

### Workflow 2: CRUD Operations
1. Create project
2. Add entity -> verify count
3. Add fields -> verify field list
4. Update field -> verify change
5. Delete field -> verify removal
6. Delete entity -> verify cleanup

### Workflow 3: JSON Mode
1. All commands return valid JSON with --json flag
2. JSON output is parseable

### Workflow 4: CLI Subprocess
1. `cli-anything-pdmaner --help` exits 0
2. `cli-anything-pdmaner --json project new -n test -o <path>` creates valid JSON
3. `cli-anything-pdmaner --json --project <path> entity list` returns valid JSON
4. Full pipeline via subprocess: create -> add entity -> add field -> export ddl

---

## Test Results

```
============================= 64 passed in 6.18s ==============================

test_core.py (51 tests):
  TestProject: 7 passed
  TestEntity: 14 passed
  TestExport: 8 passed
  TestDict: 5 passed
  TestDomain: 4 passed
  TestDiagram: 3 passed
  TestView: 2 passed
  TestSession: 8 passed

test_full_e2e.py (13 tests):
  TestCLISubprocess: 12 passed (help, project_new_json, project_open_and_info,
    entity_list_empty, entity_add, entity_get, add_field, export_ddl,
    dict_operations, view_operations, domain_operations, full_workflow)
  TestE2EInMemory: 1 passed (full_workflow_programmatic)
```

### Summary
- **Total**: 64 tests
- **Pass rate**: 100%
- **Execution time**: ~6.2s
- **Coverage**: All core modules tested (project, entity, export, dict, domain, diagram, view, session)
- **E2E coverage**: Full workflow tested via subprocess (CLI commands with --json output)
