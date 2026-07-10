# TEST.md - Nsight Graphics CLI Test Plan & Results

## Test Inventory Plan

- `test_core.py`: 46 unit and CLI tests planned
- `test_full_e2e.py`: 5 conditional E2E tests planned

## Unit Test Plan

### `utils/nsight_graphics_backend.py`

- executable discovery from env override and install directories
- compatibility mode detection for `unified`, `split`, `unified+split`, and missing tools
- CLI override precedence via `--nsight-path`
- `ngfx --help-all` parsing for current Graphics Capture and GPU Trace activities
- installation listing and version reporting
- Windows registry discovery for registered-only installs
- fixed-drive discovery for non-`C:` installs
- unified, split capture, and replay command construction
- explicit output directory creation before invoking Nsight
- artifact diffing behavior
- exported GPU Trace summary parsing
- exported GPU Trace table inventory, metric inventory, frame-budget/workload
  analysis, throughput ranking, bottleneck hints, and empty table warnings
- newest-complete GPU Trace export selection when multiple exports share an output root

### `core/*.py`

- Graphics Capture default activity selection and explicit OpenGL Frame Debugger routing
- split-mode fallback restrictions
- GPU Trace validation for trigger/limit options
- GPU Trace one-step summary behavior, including refusal to summarize stale exports
- `ngfx-replay` metadata/log/screenshot/perf-report analysis command orchestration
- structured replay metadata summaries for capture metadata, function streams,
  object inventories, and no-error log markers
- `.ngfx-gputrace` replay compatibility diagnostics when `ngfx-replay` rejects
  the file header
- launch attach/detached wrapping

### `nsight_graphics_cli.py`

- root help
- help for `doctor`, `launch`, `frame`, `gpu-trace`, `replay`, and `cpp`
- JSON output for `replay analyze`
- subprocess smoke test via `python -m`

## E2E Test Plan

Environment prerequisites:

- Nsight Graphics installed and discoverable
- `NSIGHT_GRAPHICS_TEST_EXE`
- optional `NSIGHT_GRAPHICS_TEST_ARGS`
- optional `NSIGHT_GRAPHICS_TEST_WORKDIR`
- optional `NSIGHT_GRAPHICS_TEST_CAPTURE_FILE` pointing at `.ngfx-capture`

Scenarios:

1. `doctor info` returns installation metadata
2. `frame capture` produces one or more non-empty artifacts, then feeds a
   discovered `.ngfx-capture` into `replay analyze`
3. `gpu-trace capture --auto-export --summarize` produces one or more
   non-empty artifacts and structured table/metric/analysis summary fields
4. `cpp capture` produces one or more non-empty artifacts
5. `replay analyze` on an existing capture produces non-empty analysis artifacts
   and structured metadata/log summary fields

## Running Tests

```bash
cd nsight-graphics/agent-harness
python -m pip install -e .
python -m pytest cli_anything/nsight_graphics/tests -v --tb=no
```

For the full local E2E run on this workstation:

```powershell
$env:NSIGHT_GRAPHICS_TEST_EXE = "D:\Program Files\NVIDIA Corporation\Nsight Graphics 2026.1.0\samples\applications\vk_graphics_pipeline_library\vk_graphics_pipeline_library.exe"
$env:NSIGHT_GRAPHICS_TEST_WORKDIR = "D:\Program Files\NVIDIA Corporation\Nsight Graphics 2026.1.0\samples\applications\vk_graphics_pipeline_library"
$env:NSIGHT_GRAPHICS_TEST_CAPTURE_FILE = "C:\Users\aimidi\Documents\NVIDIA Nsight Graphics\GraphicsCaptures\vk_graphics_pipeline_library_2026_04_23_17_48_22.ngfx-capture"
python -m pytest cli_anything/nsight_graphics/tests -v --tb=no
```

## Test Results

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\aimidi\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\aimidi\.codex\worktrees\da29\CLI-Anything\nsight-graphics\agent-harness
collecting ... collected 51 items

cli_anything/nsight_graphics/tests/test_core.py::TestOutputAndErrors::test_output_json PASSED [  2%]
cli_anything/nsight_graphics/tests/test_core.py::TestOutputAndErrors::test_handle_error_debug PASSED [  4%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_default_windows_install_dirs_prefers_higher_version PASSED [  6%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_discover_binaries_from_env_dir PASSED [  8%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_discover_binaries_prefers_cli_override PASSED [ 10%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_detect_tool_mode PASSED [ 12%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_prepare_output_dir_creates_missing_directory PASSED [ 13%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_reports_versions PASSED [ 14%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_includes_registry_only_entries PASSED [ 16%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_merges_registry_metadata_into_filesystem_entry PASSED [ 18%]
cli_anything/nsight_graphics/tests/test_core.py::TestBackendDiscovery::test_list_installations_promotes_newer_drive_install PASSED [ 20%]
cli_anything/nsight_graphics/tests/test_core.py::TestHelpParsing::test_parse_unified_help_extracts_activities_and_options PASSED [ 22%]
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_build_unified_command_formats_args_and_env PASSED [ 24%]
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_build_split_capture_command_maps_wait_seconds PASSED [ 26%]
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_build_replay_command_uses_capture_file_as_positional PASSED [ 28%]
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_diff_snapshots_reports_new_nonempty_files PASSED [ 30%]
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_gpu_trace_summary_from_export_dir PASSED [ 32%]
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_gpu_trace_summary_reports_empty_event_and_regime_tables PASSED [ 35%]
cli_anything/nsight_graphics/tests/test_core.py::TestCommandBuilders::test_gpu_trace_summary_prefers_newest_complete_export_dir PASSED [ 34%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_frame_capture_uses_unified_ngfx PASSED [ 36%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_frame_capture_allows_explicit_opengl_frame_debugger PASSED [ 38%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_frame_capture_split_mode_rejects_perf_exports PASSED [ 40%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_gpu_trace_requires_arch_for_metric_set PASSED [ 42%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_launch_attach_returns_unified_result PASSED [ 44%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_cpp_capture_sets_activity PASSED [ 46%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_gpu_trace_capture_with_summary PASSED [ 48%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_gpu_trace_capture_summary_refuses_failed_capture PASSED [ 51%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_gpu_trace_capture_summary_requires_new_complete_export PASSED [ 53%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_replay_analyze_exports_requested_metadata_logs_screenshot_and_perf PASSED [ 55%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_replay_analyze_defaults_to_metadata_logs_and_perf PASSED [ 57%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_replay_analyze_filters_no_error_log_marker PASSED [ 59%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_replay_analyze_reports_gputrace_replay_incompatibility PASSED [ 61%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_replay_analyze_requires_ngfx_replay PASSED [ 63%]
cli_anything/nsight_graphics/tests/test_core.py::TestCoreModules::test_replay_analyze_rejects_unknown_capture_extension PASSED [ 65%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_root_help PASSED [ 67%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_nsight_path_is_forwarded_to_doctor PASSED [ 69%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args0-info] PASSED [ 71%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args1-versions] PASSED [ 73%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args2-detached] PASSED [ 75%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args3-capture] PASSED [ 77%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args4-capture] PASSED [ 79%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args5-summarize] PASSED [ 81%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args6-analyze] PASSED [ 83%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_group_help[args7-capture] PASSED [ 85%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLIHelp::test_replay_analyze_json_cli PASSED [ 87%]
cli_anything/nsight_graphics/tests/test_core.py::TestCLISubprocess::test_cli_help_subprocess PASSED [ 89%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestDoctorE2E::test_doctor_info PASSED [ 91%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_frame_capture PASSED [ 93%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_gpu_trace_capture PASSED [ 95%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_cpp_capture PASSED [ 97%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestReplayE2E::test_replay_analyze_existing_capture PASSED [100%]

============================= 51 passed in 36.51s =============================
```

## Summary Statistics

- Total tests collected: 51
- Passed: 51
- Skipped: 0
- Pass rate: 100%

## Coverage Notes

- `doctor info` E2E passed against the local Nsight Graphics installation.
- Target-dependent capture E2E passed with the Nsight Graphics 2026.1.0 `vk_graphics_pipeline_library.exe` sample, including `gpu-trace capture --auto-export --summarize`.
- Replay E2E passed with an existing local `.ngfx-capture` generated from the same sample and now asserts structured metadata/log summary fields.
- Frame capture E2E now immediately replays the captured `.ngfx-capture` when one is discovered.
- A real local `.ngfx-gputrace` was checked manually against `ngfx-replay` and returned `ERROR: Invalid file header`; the CLI now reports this as a compatibility warning instead of implying metadata support.
- GPU Trace summary coverage now refuses stale exports for one-step capture summaries and reports table inventory, metric inventory, frame-budget/workload analysis, throughput ranking, bottleneck hints, and empty event/regime table warnings.
- Explicit `--output-dir` paths are now created before capture commands invoke Nsight.
- Without target/capture E2E environment variables, the suite reports `47 passed, 4 skipped`; the skips are the expected target-dependent capture and replay E2E gates.
