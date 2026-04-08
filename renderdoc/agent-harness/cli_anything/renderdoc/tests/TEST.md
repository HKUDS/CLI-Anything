# TEST.md – RenderDoc CLI Test Plan & Results

## Test Strategy

### Unit Tests (`test_core.py`)
Mock-based tests for all core modules. No dependency on the `renderdoc` Python
module or actual `.rdc` capture files. Tests synthetic data paths.

### E2E Tests (`test_full_e2e.py`)
Full integration tests requiring:
1. RenderDoc installed with Python bindings accessible
2. A `.rdc` capture file (set via `RENDERDOC_TEST_CAPTURE` env var)

Skips gracefully if either prerequisite is missing.

## Running Tests

```bash
# Unit tests (always runnable)
cd renderdoc/agent-harness
pytest cli_anything/renderdoc/tests/test_core.py -v

# E2E tests (requires RenderDoc + capture file)
RENDERDOC_TEST_CAPTURE=/path/to/capture.rdc pytest cli_anything/renderdoc/tests/test_full_e2e.py -v

# All tests
pytest cli_anything/renderdoc/tests/ -v
```

## Test Coverage

| Module                  | Tests | Status |
|------------------------|-------|--------|
| utils/output.py         | 4     | ✅ Pass |
| utils/errors.py         | 2     | ✅ Pass |
| core/actions.py         | 9     | ✅ Pass |
| core/textures.py        | 4     | ✅ Pass |
| core/resources.py       | 5     | ✅ Pass |
| core/diff.py            | 12    | ✅ Pass |
| CLI help (all groups)   | 8     | ✅ Pass |
| CLI subprocess          | 1     | ✅ Pass |
| **Total Unit**          | **45**| **✅ All Pass** |
| E2E (capture info)      | 2     | ⏭️ Skip (no RD) |
| E2E (actions)           | 4     | ⏭️ Skip (no RD) |
| E2E (textures)          | 2     | ⏭️ Skip (no RD) |
| E2E (resources)         | 2     | ⏭️ Skip (no RD) |
| E2E (pipeline)          | 2     | ⏭️ Skip (no RD) |
| E2E (counters)          | 1     | ⏭️ Skip (no RD) |
| E2E (workflow)          | 1     | ⏭️ Skip (no RD) |
| **Total E2E**           | **14**| **⏭️ All Skip** |

## Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.10.2, pytest-9.0.2

cli_anything/renderdoc/tests/test_core.py::TestOutputUtils::test_output_json PASSED
cli_anything/renderdoc/tests/test_core.py::TestOutputUtils::test_output_table PASSED
cli_anything/renderdoc/tests/test_core.py::TestOutputUtils::test_output_table_empty PASSED
cli_anything/renderdoc/tests/test_core.py::TestOutputUtils::test_format_size PASSED
cli_anything/renderdoc/tests/test_core.py::TestErrorUtils::test_handle_error PASSED
cli_anything/renderdoc/tests/test_core.py::TestErrorUtils::test_handle_error_debug PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_decode_flags PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_decode_flags_multiple PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_action_to_dict PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_list_actions_flat PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_list_actions_root_only PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_find_actions_by_name PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_find_action_by_event PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_get_drawcalls_only PASSED
cli_anything/renderdoc/tests/test_core.py::TestActionsModule::test_action_summary PASSED
cli_anything/renderdoc/tests/test_core.py::TestTexturesModule::test_tex_to_dict PASSED
cli_anything/renderdoc/tests/test_core.py::TestTexturesModule::test_list_textures PASSED
cli_anything/renderdoc/tests/test_core.py::TestTexturesModule::test_get_texture_found PASSED
cli_anything/renderdoc/tests/test_core.py::TestTexturesModule::test_get_texture_not_found PASSED
cli_anything/renderdoc/tests/test_core.py::TestResourcesModule::test_list_resources PASSED
cli_anything/renderdoc/tests/test_core.py::TestResourcesModule::test_list_buffers PASSED
cli_anything/renderdoc/tests/test_core.py::TestResourcesModule::test_get_buffer_data_hex PASSED
cli_anything/renderdoc/tests/test_core.py::TestResourcesModule::test_get_buffer_data_float32 PASSED
cli_anything/renderdoc/tests/test_core.py::TestResourcesModule::test_get_buffer_data_not_found PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_main_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_capture_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_actions_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_textures_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_pipeline_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_resources_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_mesh_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLIHelp::test_counters_help PASSED
cli_anything/renderdoc/tests/test_core.py::TestCLISubprocess::test_cli_help_subprocess PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_identical_snapshots PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_different_viewport PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_float_tolerance PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_float_nan_equal PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_diff_lists_only_in_one_side PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_diff_dicts_missing_key PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_diff_dicts_identical PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_diff_dicts_none_inputs PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_stage_diff_shader_changed PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_cbuffer_variable_diff PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_cbuffer_variable_identical PASSED
cli_anything/renderdoc/tests/test_core.py::TestDiffModule::test_output_table_extra_columns PASSED

============================= 45 passed in 0.15s ==============================

cli_anything/renderdoc/tests/test_full_e2e.py - 14 skipped (no RenderDoc)

============================= 59 total, 45 passed, 14 skipped ================
```
