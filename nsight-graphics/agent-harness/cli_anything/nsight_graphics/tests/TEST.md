# TEST.md – Nsight Graphics CLI Test Plan & Results

## Test Inventory Plan

- `test_core.py`: 36 unit tests planned
- `test_full_e2e.py`: 4 E2E tests planned

## Unit Test Plan

### `utils/nsight_graphics_backend.py`

- executable discovery from env override and install directories
- compatibility mode detection
- CLI override precedence via `--nsight-path`
- `ngfx --help-all` parsing for activities and options
- installation listing and version reporting
- Windows registry discovery for registered-only installs
- fixed-drive discovery for non-`C:` installs
- unified and split command construction
- artifact diffing behavior
- exported GPU Trace summary parsing
- newest-complete GPU Trace export selection when multiple exports share an output root

### `core/*.py`

- frame capture command routing
- split-mode fallback restrictions
- GPU Trace validation for trigger/limit options
- GPU Trace one-step summary behavior
- launch attach/detached wrapping

### `nsight_graphics_cli.py`

- root help
- help for `doctor`, `launch`, `frame`, `gpu-trace`, and `cpp`
- subprocess smoke test via `python -m`

## E2E Test Plan

Environment prerequisites:

- Nsight Graphics installed and discoverable
- one shared target via `NSIGHT_GRAPHICS_TEST_EXE` (plus optional args/workdir), or
- activity-specific targets via:
  - `NSIGHT_GRAPHICS_FRAME_TEST_EXE`
  - `NSIGHT_GRAPHICS_GPU_TRACE_TEST_EXE`
  - `NSIGHT_GRAPHICS_CPP_TEST_EXE`
- optional args/workdirs for each activity via the matching `*_ARGS` / `*_WORKDIR` variables

Scenarios:

1. `doctor info` returns installation metadata
2. `frame capture` produces one or more non-empty artifacts
3. `gpu-trace capture --auto-export` produces one or more non-empty artifacts
4. `cpp capture` produces one or more non-empty artifacts

## Running Tests

```bash
cd nsight-graphics/agent-harness
python -m pip install -e .
python -m pytest cli_anything/nsight_graphics/tests -v --tb=no
```

## Test Results

```text
python -m pytest cli_anything/nsight_graphics/tests/test_core.py -q
....................................                                     [100%]
36 passed in 0.27s

python -m pytest cli_anything/nsight_graphics/tests/test_full_e2e.py -v -rs
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.0.3, pluggy-1.6.0 -- C:\Users\aimidi\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\aimidi\.codex\worktrees\da29\CLI-Anything\nsight-graphics\agent-harness
collecting ... collected 4 items

cli_anything/nsight_graphics/tests/test_full_e2e.py::TestDoctorE2E::test_doctor_info PASSED [ 25%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_frame_capture PASSED [ 50%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_gpu_trace_capture PASSED [ 75%]
cli_anything/nsight_graphics/tests/test_full_e2e.py::TestTargetedE2E::test_cpp_capture PASSED [100%]

============================= 4 passed in 23.10s ==============================
```

## Summary Statistics

- Total tests collected: 40
- Passed: 40
- Skipped: 0 in the validated real-environment run
- Pass rate: 100%

## Coverage Notes

- `doctor info` E2E passed against the local Nsight Graphics installation.
- Target-dependent E2E scenarios are env-gated by executable/workdir configuration.
- Verified all targeted E2E scenarios locally with the bundled Vulkan sample:
  `D:\Program Files\NVIDIA Corporation\Nsight Graphics 2026.1.0\samples\applications\vk_graphics_pipeline_library\vk_graphics_pipeline_library.exe`
- GPU Trace summary coverage now includes the case where an output root contains
  multiple export directories; the newest complete export is selected.
- Current builds map legacy `Frame Debugger` flows onto `Graphics Capture` where required by newer Nsight Graphics releases.
