# TEST.md — cli-anything-freecad Test Plan and Results

## Test Inventory Plan

| Test File | Type | Estimated Tests |
|-----------|------|----------------|
| `test_core.py` | Unit tests | ~45 tests |
| `test_full_e2e.py` | E2E + CLI subprocess | ~15 tests |

## Unit Test Plan (`test_core.py`)

### document.py (~8 tests)
- Create document with defaults
- Create document with profile
- Create document with invalid profile → ValueError
- Open document from file
- Open document from invalid path → FileNotFoundError
- Save document and verify file content
- Get document info with parts/sketches/bodies
- List profiles returns all presets

### parts.py (~10 tests)
- Add box with defaults
- Add all primitive types (cylinder, sphere, cone, torus, wedge)
- Add part with custom position and rotation
- Add part with custom params
- Add part with invalid type → ValueError
- Remove part by index
- Remove part with invalid index → IndexError
- Transform part position/rotation
- Boolean cut operation
- Boolean fuse and common operations

### sketch.py (~8 tests)
- Create sketch on XY plane
- Create sketch on XZ/YZ planes
- Add line to sketch
- Add circle to sketch
- Add rectangle (generates 4 lines + 4 constraints)
- Add arc to sketch
- Add distance constraint with value
- Close sketch

### body.py (~7 tests)
- Create body
- Pad body with sketch
- Pocket body
- Fillet body
- Chamfer body
- Revolution body
- List bodies and get body details

### materials.py (~7 tests)
- Create material with defaults
- Create material from preset
- Create material with custom color
- Assign material to part
- Set material property (color, metallic, roughness)
- Invalid property → ValueError
- List presets

### session.py (~6 tests)
- Session status with no project
- Set project and verify status
- Snapshot and undo
- Undo/redo cycle
- Save session to file
- History listing

## E2E Test Plan (`test_full_e2e.py`)

### Intermediate file tests (~5 tests)
- Create full project JSON and verify structure
- Build complex model (multiple parts, booleans, materials)
- Generate FreeCAD macro and validate syntax
- Project save/load roundtrip
- Multi-step workflow (document → parts → booleans → materials → export)

### True backend tests (~5 tests — require FreeCAD installed)
- Export simple box to STEP and validate format
- Export multi-part model to STL and validate
- Export to FCStd native format
- Full workflow: create → add parts → boolean → export STEP
- Verify file sizes are reasonable

### CLI subprocess tests (~5 tests)
- `--help` returns 0
- `--json document new` creates valid JSON
- `--json part add box` returns part data
- `--json part list` shows all parts
- Full workflow via subprocess: new → add → boolean → export

## Realistic Workflow Scenarios

### Scenario 1: Mechanical Part with Hole
Simulates creating a base plate with a mounting hole.
1. `document new` → create project
2. `part add box` → base plate
3. `part add cylinder` → hole template
4. `part boolean cut` → subtract hole from plate
5. `material create --preset steel` → assign material
6. `export render output.step` → export

### Scenario 2: Sketch-Based Extrusion
Simulates creating a bracket from a sketch.
1. `document new` → create project
2. `sketch new --plane XY` → create sketch
3. `sketch add-rect` → profile shape
4. `sketch add-circle` → hole in profile
5. `body new` → create body
6. `body pad` → extrude sketch
7. `body fillet` → round edges
8. `export render output.step` → export

### Scenario 3: Multi-Part Assembly
Simulates assembling multiple components.
1. `document new` → create project
2. Add multiple parts with different positions
3. Apply materials (steel, aluminum)
4. Create boolean unions where needed
5. Export to STEP

---

## Test Results

**Date**: 2026-03-22
**Platform**: Windows 11 — Python 3.14.2 — pytest 9.0.2
**Command**: `python -m pytest cli_anything/freecad/tests/ -v --tb=no`

```
cli_anything/freecad/tests/test_core.py::TestDocument::test_create_default PASSED
cli_anything/freecad/tests/test_core.py::TestDocument::test_create_with_profile PASSED
cli_anything/freecad/tests/test_core.py::TestDocument::test_create_invalid_profile PASSED
cli_anything/freecad/tests/test_core.py::TestDocument::test_save_and_open PASSED
cli_anything/freecad/tests/test_core.py::TestDocument::test_open_nonexistent PASSED
cli_anything/freecad/tests/test_core.py::TestDocument::test_get_info PASSED
cli_anything/freecad/tests/test_core.py::TestDocument::test_get_info_with_data PASSED
cli_anything/freecad/tests/test_core.py::TestDocument::test_list_profiles PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_box_defaults PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_all_primitives[box] PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_all_primitives[cylinder] PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_all_primitives[sphere] PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_all_primitives[cone] PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_all_primitives[torus] PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_all_primitives[wedge] PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_with_position_rotation PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_with_custom_params PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_add_invalid_type PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_remove_part PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_remove_invalid_index PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_list_parts PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_transform_part PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_boolean_cut PASSED
cli_anything/freecad/tests/test_core.py::TestParts::test_boolean_fuse_common PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_create_sketch PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_add_line PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_add_circle PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_add_rectangle PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_add_arc PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_add_constraint_distance PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_close_sketch PASSED
cli_anything/freecad/tests/test_core.py::TestSketch::test_list_and_get_sketch PASSED
cli_anything/freecad/tests/test_core.py::TestBody::test_create_body PASSED
cli_anything/freecad/tests/test_core.py::TestBody::test_pad PASSED
cli_anything/freecad/tests/test_core.py::TestBody::test_pocket PASSED
cli_anything/freecad/tests/test_core.py::TestBody::test_fillet PASSED
cli_anything/freecad/tests/test_core.py::TestBody::test_chamfer PASSED
cli_anything/freecad/tests/test_core.py::TestBody::test_revolution PASSED
cli_anything/freecad/tests/test_core.py::TestBody::test_list_and_get_body PASSED
cli_anything/freecad/tests/test_core.py::TestMaterials::test_create_default PASSED
cli_anything/freecad/tests/test_core.py::TestMaterials::test_create_from_preset PASSED
cli_anything/freecad/tests/test_core.py::TestMaterials::test_create_with_color PASSED
cli_anything/freecad/tests/test_core.py::TestMaterials::test_assign_to_part PASSED
cli_anything/freecad/tests/test_core.py::TestMaterials::test_set_property PASSED
cli_anything/freecad/tests/test_core.py::TestMaterials::test_set_invalid_property PASSED
cli_anything/freecad/tests/test_core.py::TestMaterials::test_list_presets PASSED
cli_anything/freecad/tests/test_core.py::TestSession::test_status_no_project PASSED
cli_anything/freecad/tests/test_core.py::TestSession::test_set_project PASSED
cli_anything/freecad/tests/test_core.py::TestSession::test_snapshot_and_undo PASSED
cli_anything/freecad/tests/test_core.py::TestSession::test_undo_redo_cycle PASSED
cli_anything/freecad/tests/test_core.py::TestSession::test_save_session PASSED
cli_anything/freecad/tests/test_core.py::TestSession::test_list_history PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestIntermediateFiles::test_full_project_json_structure PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestIntermediateFiles::test_multi_part_boolean_workflow PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestIntermediateFiles::test_macro_generation_syntax PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestIntermediateFiles::test_save_load_roundtrip PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestIntermediateFiles::test_complex_workflow PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestFreeCADBackend::test_find_freecad PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestFreeCADBackend::test_get_version PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestFreeCADBackend::test_export_box_step PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestFreeCADBackend::test_export_multi_part_stl PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestFreeCADBackend::test_export_fcstd PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestCLISubprocess::test_document_new_json PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestCLISubprocess::test_part_add_json PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestCLISubprocess::test_part_list_json PASSED
cli_anything/freecad/tests/test_full_e2e.py::TestCLISubprocess::test_full_workflow_subprocess PASSED

============================= 67 passed in 3.47s ==============================
```

### Summary

| Metric | Value |
|--------|-------|
| Total tests | 67 |
| Passed | 67 |
| Failed | 0 |
| Skipped | 0 |
| Pass rate | **100%** |
| Execution time | 3.47s |

### Coverage Notes

- **Unit tests**: Full coverage of original 6 core modules (document, parts, sketch, body, materials, session)
- **E2E intermediate**: Project JSON structure, macro generation, save/load roundtrip
- **E2E backend**: STEP, STL, and FCStd export with format validation (requires FreeCAD)
- **CLI subprocess**: Full workflow tested via installed command
- **Not covered**: REPL interactive mode (requires terminal), IGES/OBJ/BREP export (tested indirectly via presets)

### Post-Expansion Status (258 commands)

After expanding from 38 to 258 commands across 17 groups:
- All 67 existing tests continue to pass (backward compatible)
- **17 core modules** all parse without syntax errors
- All 17 CLI groups register correctly and respond to `--help`
- End-to-end workflow verified: document → part add → copy → mirror → measure → assembly
- New modules covered: measure, spreadsheet, mesh, draft, surface, import, assembly, techdraw, fem, cam
- New expanded functions: parts (+19), sketch (+17), body (+30), materials (+2+11 presets), export (+10 presets)
