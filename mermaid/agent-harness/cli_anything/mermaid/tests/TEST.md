# Mermaid CLI - Test Plan & Results

## Test Plan

### Test Inventory Plan

- `test_core.py`: 5 unit tests planned
- `test_full_e2e.py`: 5 E2E tests planned

### Unit Test Plan

**Session and project state**
- default state generation
- project save/open roundtrip
- undo/redo state transitions
- expected count: 3

**Backend serialization and URLs**
- serialized `pako:` state generation
- Mermaid renderer URL generation
- Mermaid live edit/view URL generation
- expected count: 2

**Share command behavior**
- edit/view share payload generation
- expected count: 1

### E2E Test Plan

**Installed CLI**
- `--help` output from the installed command
- JSON project creation through subprocess

**Real artifact generation**
- render SVG through the Mermaid renderer service
- render PNG through the Mermaid renderer service
- verify SVG content and PNG magic bytes

**Workflow validation**
- create a project
- replace diagram text
- auto-save through `--project`
- generate a live-editor URL

### Realistic Workflow Scenarios

**Workflow name**: Mermaid smoke path  
**Simulates**: an agent creating and sharing a small flowchart  
**Operations chained**: create project, set code, render SVG, render PNG, generate view URL  
**Verified**: saved project file, renderer response, SVG markup, PNG magic bytes, live URL format

## Test Results

Command run:

```bash
python -m pytest cli_anything/mermaid/tests/ -v --tb=no
```

Latest result:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\gram\AppData\Local\Programs\Python\Python312\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\gram\Downloads\코덱스 프로젝트\오픈소스 CLI변환\CLI-Anything\mermaid\agent-harness
plugins: cov-7.0.0
collecting ... collected 10 items

cli_anything/mermaid/tests/test_core.py::test_default_state PASSED
cli_anything/mermaid/tests/test_core.py::test_save_open_roundtrip PASSED
cli_anything/mermaid/tests/test_core.py::test_undo_redo PASSED
cli_anything/mermaid/tests/test_core.py::test_backend_serialization_and_urls PASSED
cli_anything/mermaid/tests/test_core.py::test_share_payload PASSED
cli_anything/mermaid/tests/test_full_e2e.py::TestMermaidCLI::test_help PASSED
cli_anything/mermaid/tests/test_full_e2e.py::TestMermaidCLI::test_project_new_json PASSED
cli_anything/mermaid/tests/test_full_e2e.py::TestMermaidCLI::test_render_svg PASSED
cli_anything/mermaid/tests/test_full_e2e.py::TestMermaidCLI::test_render_png PASSED
cli_anything/mermaid/tests/test_full_e2e.py::TestMermaidCLI::test_share_view_url PASSED

============================= 10 passed in 10.60s =============================
```

Summary:

- Total tests: 10
- Pass rate: 100%
- Execution time: 10.60s

Coverage notes:

- The harness verifies real SVG and PNG artifacts from the Mermaid renderer service.
- The harness does not currently cover gist import, browser-only editor options, or external Mermaid Chart save flows.
