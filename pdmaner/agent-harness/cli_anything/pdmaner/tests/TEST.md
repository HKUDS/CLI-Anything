# TEST.md — cli-anything-pdmaner Test Plan & Results

## Test Inventory Plan

| File | Planned Tests | Type |
|------|--------------|------|
| `test_core.py` | 59 | Unit tests (synthetic data) |
| `test_full_e2e.py` | 16 | E2E + CLI subprocess tests |

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
- Domain resolution — resolves `domain.applyFor` and `field.baseType` against
  `dataTypeMapping.mappings[].id` / `defKey`, with len/scale fallback
- Real PDManer project fixture with UUID-based mapping keys
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

### Workflow 5: Diagram Operations
1. `diagram add-table` accepts a diagram id and entity id without shadowing the module
2. `diagram add-relation` resolves entity id/defKey before looking up canvas cells
3. Verify the relation is persisted on the correct diagram

### Workflow 6: Read-Only Commands
1. Read-only commands (`info`, `list`, `show`, `export`) do not rewrite the project file
2. Mutating commands still auto-save and update `updatedAt`
3. Verify file mtime/content is untouched after read-only invocation

---

## Test Results

```
============================= 75 passed in 11.4s ==============================

test_core.py (59 tests):
  TestProject: 7 passed
  TestEntity: 14 passed
  TestExport: 8 passed
  TestDict: 5 passed
  TestDomain: 4 passed
  TestDiagram: 4 passed
  TestView: 2 passed
  TestSession: 8 passed
  TestExportDomainMapping: 7 passed

test_full_e2e.py (16 tests):
  TestCLISubprocess: 15 passed (help, project_new_json, project_open_and_info,
    entity_list_empty, entity_add, entity_get, add_field, export_ddl,
    dict_operations, view_operations, domain_operations, full_workflow,
    diagram_add_table_and_relation, read_only_command_does_not_rewrite_project,
    mutating_command_still_autosaves)
  TestE2EInMemory: 1 passed (full_workflow_programmatic)
```

### Summary
- **Total**: 75 tests
- **Pass rate**: 100%
- **Execution time**: ~11.4s
- **Coverage**: All core modules tested (project, entity, export, dict, domain, diagram, view, session)
- **E2E coverage**: Full workflow tested via subprocess (CLI commands with --json output),
  including diagram relations and read-only/mutating save behavior
