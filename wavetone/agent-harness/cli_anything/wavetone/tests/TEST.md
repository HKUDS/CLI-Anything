# WaveTone Harness Test Plan and Results

## Test Inventory Plan

- `test_core.py`: 24 unit tests for project manifests, audio probing, session logs,
  and backend discovery.
- `test_full_e2e.py`: 8 tests covering default real-backend opt-in gating,
  source-module subprocess resolution, CLI workflows, and real WaveTone launch
  smoke coverage.

## Unit Test Plan

- Create a manifest from a supported WAV file.
- Reject missing files and unsupported extensions.
- Save and load schema-compatible JSON.
- Reject non-object project JSON.
- Add labels in sorted time order.
- Set tempo and analysis options.
- Preserve omitted CLI boolean analysis flags as tri-state values.
- Require attached WFD analysis files to exist and use the `.wfd` suffix.
- Reject non-finite numeric project values before JSON serialization.
- Probe a generated WAV file with the Python stdlib.
- Fall back to stat metadata for malformed WAV files.
- Probe non-WAV audio with a single stable `ffprobe -show_entries` argument.
- Safely parse non-numeric ffprobe metadata.
- Append and reload session events.
- Reject invalid session JSON schemas with clear `ValueError`s.
- Reject non-finite session payload values before writing JSON.
- Resolve `WAVETONE_EXE` from the environment.
- Reject WaveTone backend data artifacts that are directories instead of files.
- Preserve inherited project and JSON context for REPL-style nested CLI
  invocations.
- Return a failing exit status for launch smoke checks when the backend exits
  early with a nonzero code.
- Convert launch runtime errors to clean CLI errors.
- Reject GUI launch attempts on non-Windows hosts with a clear error.
- Strip Windows REPL path quotes while preserving backslashes.
- Preserve WaveTone branding and expose the local skill path in the REPL banner.
- Report Click REPL exit control flow without falling through to the unexpected
  exception handler.

## E2E Test Plan

### CLI Project Workflow

Simulates an agent preparing an audio file before opening it in WaveTone.

Operations:

1. Generate a real WAV fixture.
2. Resolve the in-tree `python -m cli_anything.wavetone.wavetone_cli` module by
   default, even if an installed `cli-anything-wavetone` exists in `PATH` or
   `CLI_ANYTHING_FORCE_INSTALLED` is set externally.
3. Run `cli-anything-wavetone --json project new`.
4. Run `project set-tempo`.
5. Run `project add-label`.
6. Run `audio probe`.

Verified:

- CLI JSON is parseable.
- Project file exists.
- Labels and tempo persist.
- Audio metadata is correct.

### CLI Backend Workflow

Simulates an agent validating the installed WaveTone backend. These tests are
skipped by default and require `CLI_ANYTHING_WAVETONE_REAL_BACKEND=1` plus
`WAVETONE_EXE` or `WAVETONE_HOME`.

Operations:

1. Run `wavetone doctor`.
2. Run `wavetone formats`.
3. Launch the real `wavetone.exe` with a generated WAV and terminate it after a
   short wait.

Verified:

- Doctor reports all bundled files.
- Formats include documented WaveTone audio extensions.
- Real WaveTone process starts and is terminated by the smoke test.

## Test Results

Default command:

```bash
$env:PATH = "$env:APPDATA\Python\Python313\Scripts;$env:PATH"
$env:CLI_ANYTHING_FORCE_INSTALLED = "1"
Remove-Item Env:CLI_ANYTHING_WAVETONE_REAL_BACKEND -ErrorAction SilentlyContinue
Remove-Item Env:WAVETONE_EXE -ErrorAction SilentlyContinue
Remove-Item Env:WAVETONE_HOME -ErrorAction SilentlyContinue
python -m pytest cli_anything\wavetone\tests\ -v -s
```

Default result:

```text
collected 32 items

cli_anything/wavetone/tests/test_core.py::test_create_project_manifest PASSED
cli_anything/wavetone/tests/test_core.py::test_rejects_unsupported_audio PASSED
cli_anything/wavetone/tests/test_core.py::test_save_load_project_roundtrip PASSED
cli_anything/wavetone/tests/test_core.py::test_labels_are_sorted PASSED
cli_anything/wavetone/tests/test_core.py::test_update_analysis_settings PASSED
cli_anything/wavetone/tests/test_core.py::test_cli_analysis_preserves_omitted_boolean_flags PASSED
cli_anything/wavetone/tests/test_core.py::test_cli_attach_wfd_requires_existing_wfd_file PASSED
cli_anything/wavetone/tests/test_core.py::test_rejects_non_finite_project_numbers PASSED
cli_anything/wavetone/tests/test_core.py::test_load_project_rejects_non_object_json PASSED
cli_anything/wavetone/tests/test_core.py::test_probe_wav_metadata PASSED
cli_anything/wavetone/tests/test_core.py::test_probe_malformed_wav_falls_back_to_stat PASSED
cli_anything/wavetone/tests/test_core.py::test_ffprobe_uses_single_show_entries_argument PASSED
cli_anything/wavetone/tests/test_core.py::test_ffprobe_handles_non_numeric_metadata PASSED
cli_anything/wavetone/tests/test_core.py::test_session_event_log PASSED
cli_anything/wavetone/tests/test_core.py::test_session_rejects_invalid_schema PASSED
cli_anything/wavetone/tests/test_core.py::test_find_wavetone_from_env PASSED
cli_anything/wavetone/tests/test_core.py::test_doctor_rejects_required_data_directories PASSED
cli_anything/wavetone/tests/test_core.py::test_cli_preserves_inherited_project_and_json_context PASSED
cli_anything/wavetone/tests/test_core.py::test_wavetone_launch_fails_on_early_nonzero_exit PASSED
cli_anything/wavetone/tests/test_core.py::test_wavetone_launch_reports_runtime_errors PASSED
cli_anything/wavetone/tests/test_core.py::test_launch_requires_windows PASSED
cli_anything/wavetone/tests/test_core.py::test_repl_split_strips_windows_quotes PASSED
cli_anything/wavetone/tests/test_core.py::test_repl_skin_uses_wavetone_branding_and_local_skill_path PASSED
cli_anything/wavetone/tests/test_core.py::test_repl_reports_click_exit_without_unexpected_error PASSED
cli_anything/wavetone/tests/test_full_e2e.py::test_real_backend_requires_explicit_opt_in PASSED
cli_anything/wavetone/tests/test_full_e2e.py::test_resolve_cli_defaults_to_source_module PASSED
cli_anything/wavetone/tests/test_full_e2e.py::test_resolve_cli_uses_installed_only_when_requested PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestCLISubprocess::test_project_audio_workflow_json PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestCLISubprocess::test_formats_json PASSED
cli_anything/wavetone/tests/test_full_e2e.py::TestRealWaveToneBackend::test_doctor_real_backend SKIPPED
cli_anything/wavetone/tests/test_full_e2e.py::TestRealWaveToneBackend::test_launch_real_backend_with_wav SKIPPED

30 passed, 2 skipped in 1.44s
```

Real backend opt-in command:

```bash
$env:PATH = "$env:APPDATA\Python\Python313\Scripts;$env:PATH"
$env:CLI_ANYTHING_FORCE_INSTALLED = "1"
$env:CLI_ANYTHING_WAVETONE_REAL_BACKEND = "1"
$env:WAVETONE_HOME = "C:\Users\Hp\Desktop\wavetone2.6.1"
Remove-Item Env:WAVETONE_EXE -ErrorAction SilentlyContinue
python -m pytest cli_anything\wavetone\tests\ -v -s
```

Real backend result:

```text
32 passed in 3.03s
```

## Coverage Notes

- Unit tests cover manifest creation, validation, persistence, labels, tempo,
  analysis settings, CLI analysis flag tri-state behavior, finite numeric
  validation, WFD attachment validation, project JSON schema validation, audio
  probing, malformed WAV fallback, session logs, session schema and payload
  validation, backend discovery, backend data artifact validation, ffprobe
  argument construction, ffprobe metadata parsing, inherited CLI project and
  JSON context, failed launch smoke reporting, launch runtime error reporting,
  Windows launch gating, REPL Windows path splitting, REPL branding and local
  skill path display, and REPL Click exit handling.
- CLI subprocess tests resolve and use the in-tree
  `python -m cli_anything.wavetone.wavetone_cli` module by default, regardless
  of ambient `CLI_ANYTHING_FORCE_INSTALLED`.
- Real backend coverage launches `C:\Users\Hp\Desktop\wavetone2.6.1\wavetone.exe`
  with a generated WAV and terminates it after a short wait.
- Real backend tests are skipped by default unless
  `CLI_ANYTHING_WAVETONE_REAL_BACKEND=1` and `WAVETONE_EXE` or `WAVETONE_HOME`
  are set.
- WaveTone 2.61 has no documented headless analysis/export API. Export
  verification remains a known gap until a stable non-GUI automation surface is
  discovered.
