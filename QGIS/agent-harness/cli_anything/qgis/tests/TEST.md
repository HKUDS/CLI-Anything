# cli-anything-qgis test plan

## Scope

This test plan covers the production-style QGIS harness under `cli_anything/qgis/`.

The suite is split into:

- `test_core.py` for direct module tests against PyQGIS helpers and backend wrappers
- `test_full_e2e.py` for real workflow coverage and installed-command subprocess coverage

## Planned unit and module coverage

### Backend helpers
- `find_qgis_process()` returns a usable executable path or raises a clear error
- `project_path_argument()` normalizes project paths
- `run_process_json()` normalizes JSON and failure cases

### Project helpers
- create a new project
- open an existing project
- save a project to a path
- change project CRS
- derive the default datastore path
- summarize project metadata

### Layer helpers
- parse field specs
- create GeoPackage-backed vector layers with fields
- list and inspect layers
- remove layers

### Feature helpers
- add features using WKT and typed attributes
- list features with limits
- validate bad attr specifications and bad booleans

### Layout helpers
- create layouts with page size/orientation
- list and inspect layouts
- add map items
- add label items
- remove layouts

### Session helpers
- record command history
- save/load session history
- report session status

## Planned real end-to-end workflows

### Workflow 1 — scratch project to PDF
1. create a new project
2. create a writable vector layer
3. add features
4. create a layout
5. add a map item and label
6. export PDF
7. verify file exists, has non-zero size, and starts with `%PDF-`

### Workflow 2 — scratch project to PNG
1. create a new project
2. create content and layout
3. export image
4. verify file exists, PNG signature is valid, and dimensions are positive

### Workflow 3 — processing passthrough
1. create a vector layer and add features
2. run `native:buffer` through the harness
3. verify output dataset exists and opens as a valid vector layer
4. verify buffered feature count is positive

## Planned subprocess coverage

Subprocess tests must target the installed executable via `_resolve_cli("cli-anything-qgis")`.

Planned checks:

- `cli-anything-qgis --help`
- `cli-anything-qgis --json process help native:printlayouttopdf`
- `cli-anything-qgis --json project new -o ...`
- full installed-command PDF workflow
- full installed-command PNG workflow

## Planned execution commands

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/qgis/tests/test_core.py -v
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/qgis/tests/test_full_e2e.py -v -s
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/qgis/tests -v -s --tb=no
```

## Results

### Coverage note

- Direct core tests covered project, layer, feature, layout, session, and backend error-normalization helpers, including a point-only layout auto-extent regression.
- Real E2E coverage exercised PDF export, PNG export, and `native:buffer` processing against the installed QGIS runtime.
- Subprocess coverage verified the installed `cli-anything-qgis` entrypoint, JSON help output, project creation, full PDF/PNG workflows, and the point-only `layout add-map` regression path.
- One known warning remains: `QgsLayoutItemLabel.setFont()` is deprecated in this QGIS build, but exports and tests pass.

### `pytest -v -s --tb=no` output

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- /home/wangh68/project/cli_anything_g/QGIS/agent-harness/.venv/bin/python
cachedir: .pytest_cache
rootdir: /home/wangh68/project/cli_anything_g/QGIS/agent-harness
configfile: pytest.ini
plugins: cov-7.1.0, anyio-4.12.1
collecting ... collected 22 items

QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_project_create_save_open_and_info PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_default_datastore_path PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_parse_field_and_param_specs PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_layer_create_list_info_and_remove PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_feature_add_and_list PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_feature_add_rejects_invalid_boolean PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_layout_create_add_items_and_remove PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_layout_add_map_accepts_point_only_project PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_export_presets_describe_supported_formats PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_session_save_load_and_status PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_project_path_argument_normalizes PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_find_qgis_process_missing_raises_clear_error PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_core.py::test_run_process_json_normalizes_backend_failure PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestRealCLIWorkflows::test_scratch_project_to_pdf PDF artifact: /tmp/pytest-of-wangh68/pytest-10/test_scratch_project_to_pdf0/workflow.pdf
PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestRealCLIWorkflows::test_scratch_project_to_png PNG artifact: /tmp/pytest-of-wangh68/pytest-10/test_scratch_project_to_png0/workflow.png
PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestRealCLIWorkflows::test_processing_passthrough_buffer PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestCLISubprocess::test_help [_resolve_cli] Using sibling command: /home/wangh68/project/cli_anything_g/QGIS/agent-harness/.venv/bin/cli-anything-qgis
PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestCLISubprocess::test_process_help_json [_resolve_cli] Using sibling command: /home/wangh68/project/cli_anything_g/QGIS/agent-harness/.venv/bin/cli-anything-qgis
PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestCLISubprocess::test_project_new_json [_resolve_cli] Using sibling command: /home/wangh68/project/cli_anything_g/QGIS/agent-harness/.venv/bin/cli-anything-qgis
PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestCLISubprocess::test_full_pdf_workflow [_resolve_cli] Using sibling command: /home/wangh68/project/cli_anything_g/QGIS/agent-harness/.venv/bin/cli-anything-qgis
Subprocess PDF artifact: /tmp/pytest-of-wangh68/pytest-10/test_full_pdf_workflow0/subprocess.pdf
PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestCLISubprocess::test_full_png_workflow [_resolve_cli] Using sibling command: /home/wangh68/project/cli_anything_g/QGIS/agent-harness/.venv/bin/cli-anything-qgis
Subprocess PNG artifact: /tmp/pytest-of-wangh68/pytest-10/test_full_png_workflow0/subprocess.png
PASSED
QGIS/agent-harness/cli_anything/qgis/tests/test_full_e2e.py::TestCLISubprocess::test_point_only_project_add_map_without_extent [_resolve_cli] Using sibling command: /home/wangh68/project/cli_anything_g/QGIS/agent-harness/.venv/bin/cli-anything-qgis
Subprocess point-only PDF artifact: /tmp/pytest-of-wangh68/pytest-10/test_point_only_project_add_ma0/subprocess_point.pdf
PASSED

=============================== warnings summary ===============================
cli_anything/qgis/tests/test_core.py::test_layout_create_add_items_and_remove
cli_anything/qgis/tests/test_full_e2e.py::TestRealCLIWorkflows::test_scratch_project_to_pdf
cli_anything/qgis/tests/test_full_e2e.py::TestRealCLIWorkflows::test_scratch_project_to_png
cli_anything/qgis/tests/test_full_e2e.py::TestRealCLIWorkflows::test_processing_passthrough_buffer
  /home/wangh68/project/cli_anything_g/QGIS/agent-harness/cli_anything/qgis/core/layouts.py:187: DeprecationWarning: QgsLayoutItemLabel.setFont() is deprecated
    label.setFont(font)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 22 passed, 4 warnings in 18.95s ========================
```
