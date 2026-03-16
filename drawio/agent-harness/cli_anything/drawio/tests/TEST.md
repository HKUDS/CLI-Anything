# Draw.io CLI - Test Plan & Results

## Test Plan

### Unit Tests (test_core.py)

**XML Utilities (TestDrawioXml)**
- Create blank diagram with correct structure
- System cells (id=0, id=1) always present
- No user cells in blank diagram
- Add vertex with all attributes
- Generate unique cell IDs across rapid inserts
- Add edge with source/target
- Remove cell
- Remove vertex also removes connected edges
- Find cell by ID (found and not found)
- Update cell label
- Move cell
- Resize cell
- Get cell info
- Get vertices vs edges
- Write and parse file roundtrip

**Style Parsing (TestStyleParsing)**
- Parse empty style
- Parse key=value pairs
- Parse base style (no value)
- Build style from dict
- Parse-build roundtrip
- Set style property on cell
- Remove style property from cell

**Shape Presets (TestShapePresets)**
- All 15 shape types create valid cells (parametrized)
- All 4 edge styles create valid edges (parametrized)

**Multi-Page Operations (TestPages)**
- Single page by default
- Add page
- Remove page
- Cannot remove last page
- Rename page
- Shapes on different pages are independent

**Session (TestSession)**
- New session is not open
- New project opens session
- Undo/redo single operation
- Multiple undo
- Save and open roundtrip
- Save with no project raises error
- Open nonexistent file raises error
- Status shows correct counts

**Project Module (TestProject)**
- New project with default preset
- New project with all presets
- Invalid preset raises error
- Custom page size
- Save and open roundtrip
- Project info
- Project info with no project raises error
- List presets

**Shapes Module (TestShapes)**
- Add shape
- Add shape with no project raises error
- List shapes
- Remove shape
- Remove nonexistent shape raises error
- Update label
- Move shape
- Resize shape
- Set style
- Get shape info
- List shape types
- All 15 shape types via module (parametrized)
- Undo add shape

**Connectors Module (TestConnectors)**
- Add connector
- Invalid source raises error
- Invalid target raises error
- List connectors
- Remove connector
- Update connector label
- Set connector style
- List edge styles
- All 4 edge styles via module (parametrized)

**Pages Module (TestPagesModule)**
- List pages
- Add page
- Remove page
- Rename page

**Export Module (TestExport)**
- List formats
- Export to XML (no draw.io CLI needed)
- Propagate backend install errors without fallback export
- Export with no project raises error
- Invalid format raises error
- File exists raises error

**Complex Workflows (TestWorkflows)**
- Build complete flowchart (4 shapes, 3 connectors, save/reopen)
- Build styled diagram (custom colors, font, shadow)
- Multi-page workflow
- Undo/redo across multiple operations
- Export XML workflow with content verification

### E2E Tests (test_full_e2e.py)

**File Roundtrip (TestFileRoundtrip)**
- Empty diagram save/reopen
- Complex diagram (6 shapes, 4 connectors, styles) roundtrip
- Multi-page diagram roundtrip

**XML Export Verification (TestXmlExport)**
- Export XML with valid structure
- Export XML preserves styles

**Real Draw.io Export (TestRealExport)** — requires draw.io installed
- Export to PNG with magic bytes verification
- Export to SVG with content verification
- Export to PDF with magic bytes verification

**CLI Subprocess (TestCLISubprocess)**
- --help output
- `python -m cli_anything.drawio --help` module entry point
- project new --json
- project info --json
- shape add --json
- shape list --json
- shape types --json
- connect styles --json
- export formats --json
- page list --json
- session status --json
- project presets --json
- export XML via subprocess

**Real-World Workflows (TestRealWorldWorkflows)**
- 3-tier web architecture diagram (5 shapes, 4 connectors, styles)
- Entity-relationship diagram (3 entities, 2 relations)
- Decision tree / flowchart (5 nodes, 5 edges)
- Multi-page technical documentation (3 pages, multiple shapes)

## Test Results

Command run:

```bash
python -m pytest cli_anything/drawio/tests/ -v --tb=no
```
```

Latest result:

```
drawio: 141 passed, 3 skipped
3 skipped: real draw.io export (PNG/SVG/PDF) - requires draw.io desktop app
```

**100% pass rate on all available tests.**

Latest `pytest -v --tb=no` output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\gram\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\gram\Downloads\코덱스 프로젝트\오픈소스 CLI변환\CLI-Anything\drawio\agent-harness
plugins: cov-7.0.0
collecting ... collected 144 items

cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_create_blank_diagram PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_system_cells_present PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_no_user_cells_in_blank PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_add_vertex PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_generated_ids_are_unique PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_add_edge PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_remove_cell PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_remove_vertex_also_removes_edges PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_find_cell_by_id PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_find_cell_not_exists PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_update_cell_label PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_move_cell PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_resize_cell PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_get_cell_info PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_get_vertices PASSED
cli_anything/drawio/tests/test_core.py::TestDrawioXml::test_write_and_parse_roundtrip PASSED
cli_anything/drawio/tests/test_core.py::TestStyleParsing::test_parse_empty PASSED
cli_anything/drawio/tests/test_core.py::TestStyleParsing::test_parse_basic PASSED
cli_anything/drawio/tests/test_core.py::TestStyleParsing::test_parse_base_style PASSED
cli_anything/drawio/tests/test_core.py::TestStyleParsing::test_build_style PASSED
cli_anything/drawio/tests/test_core.py::TestStyleParsing::test_roundtrip PASSED
cli_anything/drawio/tests/test_core.py::TestStyleParsing::test_set_style_property PASSED
cli_anything/drawio/tests/test_core.py::TestStyleParsing::test_remove_style_property PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[rectangle] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[rounded] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[ellipse] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[diamond] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[triangle] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[hexagon] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[cylinder] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[cloud] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[parallelogram] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[process] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[document] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[callout] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[note] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[actor] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_shape_types[text] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_edge_styles[straight] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_edge_styles[orthogonal] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_edge_styles[curved] PASSED
cli_anything/drawio/tests/test_core.py::TestShapePresets::test_all_edge_styles[entity-relation] PASSED
cli_anything/drawio/tests/test_core.py::TestPages::test_single_page_default PASSED
cli_anything/drawio/tests/test_core.py::TestPages::test_add_page PASSED
cli_anything/drawio/tests/test_core.py::TestPages::test_remove_page PASSED
cli_anything/drawio/tests/test_core.py::TestPages::test_cannot_remove_last_page PASSED
cli_anything/drawio/tests/test_core.py::TestPages::test_rename_page PASSED
cli_anything/drawio/tests/test_core.py::TestPages::test_shapes_on_different_pages PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_new_session PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_new_project PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_undo_redo PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_multiple_undo PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_save_and_open PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_save_no_project PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_open_nonexistent PASSED
cli_anything/drawio/tests/test_core.py::TestSession::test_status PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_new_project PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_new_project_all_presets PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_new_project_invalid_preset PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_new_project_custom_size PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_save_and_open PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_project_info PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_project_info_no_project PASSED
cli_anything/drawio/tests/test_core.py::TestProject::test_list_presets PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_add_shape PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_add_shape_no_project PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_list_shapes PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_remove_shape PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_remove_shape_not_found PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_update_label PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_move_shape PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_resize_shape PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_set_style PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_get_shape_info PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_list_shape_types PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[rectangle] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[rounded] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[ellipse] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[diamond] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[triangle] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[hexagon] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[cylinder] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[cloud] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[parallelogram] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[process] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[document] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[callout] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[note] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[actor] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_all_shape_types_via_module[text] PASSED
cli_anything/drawio/tests/test_core.py::TestShapes::test_undo_add_shape PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_add_connector PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_add_connector_invalid_source PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_add_connector_invalid_target PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_list_connectors PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_remove_connector PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_update_connector_label PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_set_connector_style PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_list_edge_styles PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_all_edge_styles_via_module[straight] PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_all_edge_styles_via_module[orthogonal] PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_all_edge_styles_via_module[curved] PASSED
cli_anything/drawio/tests/test_core.py::TestConnectors::test_all_edge_styles_via_module[entity-relation] PASSED
cli_anything/drawio/tests/test_core.py::TestPagesModule::test_list_pages PASSED
cli_anything/drawio/tests/test_core.py::TestPagesModule::test_add_page PASSED
cli_anything/drawio/tests/test_core.py::TestPagesModule::test_remove_page PASSED
cli_anything/drawio/tests/test_core.py::TestPagesModule::test_rename_page PASSED
cli_anything/drawio/tests/test_core.py::TestExport::test_list_formats PASSED
cli_anything/drawio/tests/test_core.py::TestExport::test_export_xml_direct PASSED
cli_anything/drawio/tests/test_core.py::TestExport::test_render_or_save_propagates_backend_errors PASSED
cli_anything/drawio/tests/test_core.py::TestExport::test_export_no_project PASSED
cli_anything/drawio/tests/test_core.py::TestExport::test_export_invalid_format PASSED
cli_anything/drawio/tests/test_core.py::TestExport::test_export_file_exists PASSED
cli_anything/drawio/tests/test_core.py::TestWorkflows::test_flowchart PASSED
cli_anything/drawio/tests/test_core.py::TestWorkflows::test_styled_diagram PASSED
cli_anything/drawio/tests/test_core.py::TestWorkflows::test_multi_page_workflow PASSED
cli_anything/drawio/tests/test_core.py::TestWorkflows::test_undo_redo_workflow PASSED
cli_anything/drawio/tests/test_core.py::TestWorkflows::test_export_xml_workflow PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestFileRoundtrip::test_empty_diagram_roundtrip PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestFileRoundtrip::test_complex_diagram_roundtrip PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestFileRoundtrip::test_multi_page_roundtrip PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestXmlExport::test_export_xml_valid_structure PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestXmlExport::test_export_xml_preserves_styles PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestRealExport::test_export_png SKIPPED
cli_anything/drawio/tests/test_full_e2e.py::TestRealExport::test_export_svg SKIPPED
cli_anything/drawio/tests/test_full_e2e.py::TestRealExport::test_export_pdf SKIPPED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_module_help PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_project_new_json PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_project_info_json PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_shape_add_json PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_shape_list_json PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_connect_add_json PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_shape_types PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_connect_styles PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_export_formats PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_page_list PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_session_status PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_project_presets PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestCLISubprocess::test_export_xml_subprocess PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestRealWorldWorkflows::test_architecture_diagram PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestRealWorldWorkflows::test_er_diagram PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestRealWorldWorkflows::test_decision_tree PASSED
cli_anything/drawio/tests/test_full_e2e.py::TestRealWorldWorkflows::test_multi_page_documentation PASSED

======================= 141 passed, 3 skipped in 12.55s =======================
```
