# cli-anything-vlc — Tests

## Part 1 — Test Plan (written before implementation)

### Test Inventory

| Layer | File | Requires VLC? | Purpose |
|---|---|---|---|
| Unit | `test_core.py` | No | Pure-Python core + Click wiring, synthetic data |
| E2E  | `test_full_e2e.py` | **Yes** | Invokes the real `vlc` binary (transcode / info / stream) |

### Unit Test Plan (`test_core.py`)

- `TestProjectModel` — `new_job` defaults, save/load round-trip, `validate_job` rules,
  schema (field-type) rejection at load time
- `TestSession` — undo/redo restores snapshots, history labels
- `TestTranscodeBuilder` — `--sout` chain construction (transcode + stream + snapshot),
  Windows path normalization, scene-prefix override
- `TestMediaParser` — best-effort stats parsing from synthetic VLC log
- `TestCliWiring` — `--version`/`--help`, `project new`, `add-input`, `set-option`
  persistence, `set-output`/`set-stream`, `transcode` requires `--project`, `doctor`
  without VLC, structured `--json` errors for missing / malformed / schema-invalid projects
- `TestBackendSafety` — stream timeout scaling with `--run-time`, persistent stream when
  run-time is omitted, `info` probe bounded independently of media length, snapshot
  isolation from stale files and across re-runs, temp-file cleanup on subprocess
  failure, `run_info` propagating a nonzero exit, `VLC_BINARY` validation, registry
  de-duplication
- `TestRepl` — `new` detaching an opened project, binding a not-yet-existing
  `--project`, shell-like tokenising of quoted Windows paths
- `TestOptionValidation` — unknown `set-option` keys rejected on both the Click and
  REPL paths without persisting anything
- `TestStructuredErrors` — every data-level failure in `--json` mode (missing media
  file, output path is a directory, missing `--project`) returns a JSON document and
  exit 1 rather than Click's human-only usage error

### E2E Test Plan (`test_full_e2e.py`)

- `test_transcode_wav_to_wav` — real VLC transcode; verify output exists, size > 1 KB, `RIFF` magic
- `test_info_wav` — real VLC probe; verify `path` + `returncode`
- `test_stream_udp` — real VLC UDP stream for 1 s; verify exit 0
- `test_cli_transcode_end_to_end` — full agent flow via `--json`

A `tests/assets/sample.wav` is synthesised with the stdlib `wave` module so the basic
E2E paths run without ffmpeg.

> **Non-negotiable (HARNESS.md):** E2E tests MUST invoke the real software and FAIL
> (not skip) when VLC is missing. They use `pytest.fail` for that.

## Part 2 — Test Results

### Unit — `pytest cli_anything/vlc/tests/test_core.py -v`

```
platform win32 -- Python 3.14.3, pytest-9.1.1
collected 89 items

test_new_job_defaults PASSED
test_save_and_load_roundtrip PASSED
test_validate_job PASSED
test_session_undo_redo PASSED
test_session_history_labels PASSED
test_build_transcode_sout_basic PASSED
test_build_transcode_sout_windows_path_normalized PASSED
test_build_stream_sout_rtp PASSED
test_build_snapshot_args PASSED
test_build_snapshot_args_scene_prefix PASSED
test_parse_vlc_stats_synthetic PASSED
test_cli_version_and_help PASSED
test_cli_project_new_and_mutate PASSED
test_cli_set_output_and_stream PASSED
test_cli_transcode_requires_project PASSED
test_cli_doctor_without_vlc PASSED
test_cli_transcode_missing_project_is_structured_json PASSED
test_transcode_copy_and_none_codecs_omitted PASSED
test_run_stream_timeout_scales_with_run_time PASSED
test_run_snapshot_ignores_stale_files PASSED
test_run_info_propagates_nonzero_exit PASSED
test_registry_names_not_in_both_files PASSED
test_transcode_rejects_output_equal_to_input PASSED
test_run_stream_persistent_omits_run_time PASSED
test_find_vlc_rejects_directory_binary PASSED
test_find_vlc_rejects_non_executable_file PASSED
test_cli_mutation_malformed_project_structured PASSED
test_repl_shlex_handles_spaces_and_backslashes PASSED
test_load_job_rejects_schema_invalid_types PASSED
test_load_job_rejects_non_string_inputs PASSED
test_cli_mutation_schema_invalid_project_is_structured PASSED
test_repl_new_detaches_opened_project PASSED
test_run_transcode_removes_temp_when_subprocess_raises PASSED
test_run_snapshot_rerun_same_directory_succeeds PASSED
test_load_job_normalizes_null_inputs PASSED
test_run_info_bounds_playback PASSED
test_repl_binds_missing_project_path PASSED
test_set_option_rejects_unknown_key PASSED
test_repl_set_option_rejects_unknown_key PASSED
test_cli_info_missing_file_is_structured PASSED
test_cli_add_input_missing_file_is_structured PASSED
test_cli_set_output_directory_is_structured PASSED
test_cli_project_show_without_project_is_structured PASSED
test_cli_project_new_unwritable_target_is_structured PASSED
test_cli_add_input_directory_is_structured PASSED
test_cli_info_directory_is_structured PASSED
test_set_option_rejects_non_finite_numbers[nan] PASSED
test_set_option_rejects_non_finite_numbers[inf] PASSED
test_set_option_rejects_non_finite_numbers[1e309] PASSED
test_set_option_rejects_non_numeric_value PASSED
test_load_job_rejects_non_finite_transcode PASSED
test_load_job_rejects_boolean_transcode_value PASSED
test_load_job_rejects_scalar_extra PASSED
test_load_job_rejects_non_string_extra_items PASSED
test_build_sout_treats_scalar_extra_as_single_option PASSED
test_find_vlc_rejects_runnable_binary_that_is_not_vlc PASSED
test_find_vlc_accepts_binary_that_identifies_as_vlc PASSED
test_find_vlc_probe_failure_is_rejected PASSED
test_build_sout_null_output_format_uses_mp4_default PASSED
test_build_stream_sout_null_mux_uses_ts_default PASSED
test_build_snapshot_args_defaults_missing_time PASSED
test_build_snapshot_args_tolerates_null_time_and_ratio PASSED
test_set_snapshot_rejects_non_finite_time[nan] PASSED
test_set_snapshot_rejects_non_finite_time[inf] PASSED
test_set_snapshot_rejects_non_finite_time[1e309] PASSED
test_run_snapshot_cleans_up_when_vlc_fails PASSED
test_readme_command_table_matches_the_cli PASSED
test_build_stream_sout_null_dst_and_port_use_defaults PASSED
test_build_stream_sout_rejects_or_defaults_bad_port[abc] PASSED
test_build_stream_sout_rejects_or_defaults_bad_port[inf] PASSED
test_build_stream_sout_rejects_or_defaults_bad_port[0] PASSED
test_build_stream_sout_rejects_or_defaults_bad_port[70000] PASSED
test_build_stream_sout_rejects_or_defaults_bad_port[-1] PASSED
test_build_stream_sout_rejects_or_defaults_bad_port[] PASSED
test_load_job_rejects_invalid_stream_fields PASSED
test_load_job_accepts_valid_stream PASSED
test_load_job_rejects_invalid_snapshot_fields PASSED
test_documented_doctor_shape_matches_reality PASSED
test_find_vlc_rejects_probe_that_exits_nonzero PASSED
test_set_snapshot_rejects_zero_ratio PASSED
test_build_snapshot_args_rejects_zero_ratio PASSED
test_build_snapshot_args_rejects_non_integer_ratio PASSED
test_skill_copies_stay_in_sync PASSED
test_repl_add_input_rejects_missing_file PASSED
test_repl_add_input_accepts_existing_file PASSED
test_repl_set_output_rejects_directory PASSED
test_save_job_is_atomic_on_success PASSED
test_save_job_leaves_no_temp_and_keeps_old_file_on_failure PASSED
test_repl_skin_construction_does_not_write_home PASSED

============================= 88 passed, 1 skipped in 0.98s =============================
```

**Summary:** 88 passed, 1 skipped (`test_find_vlc_rejects_non_executable_file` — the
exec-bit check is POSIX-only). No external dependency (VLC / ffmpeg) required.

#### Regression-proofing of the review fixes

Every review finding ships with a test that was verified to **fail against the pre-fix
code** (the fixed sources were reverted and the new tests re-run), so none of them is a
test that would pass either way:

| Round | Findings | Regression tests |
|---|---|---|
| 1st (`8d1a22a`) | 9 | codec `None` omission, stream timeout scaling, snapshot stale-file isolation, `run_info` exit propagation, structured project errors, registry de-duplication, SKILL.md option order |
| 2nd (`cb6fe9e`) | 7 | output aliases input, stale destination rejected, persistent stream, guarded malformed projects, REPL `shlex`, `VLC_BINARY` validation, `.gitignore` scoping |
| 3rd (`7d5c4e1`) | 4 | `new` detaches an opened project, schema-invalid projects rejected at load *and* inside the guard, temp-file cleanup on subprocess failure, per-run snapshot prefix |
| 4th (`77f42fc`) | 4 | `info` playback bounded independently of media length, explicit-null containers normalised at load, REPL binds a not-yet-existing `--project`, unknown `set-option` keys rejected |
| 5th (`f58b8f8`) | 4 | `project new` write failures guarded, directory inputs routed through the callback, non-finite numeric options rejected, `transcode.extra` validated as `list[str]` |
| 6th (`9013821`) | 6 | `VLC_BINARY` probed before `doctor` reports ready, null output format/mux defaulted, missing snapshot `time` defaulted, non-finite snapshot times rejected, partial snapshots cleaned up on failure, README command table corrected |
| class sweep | — | Same bug classes as earlier rounds, audited across **every** path rather than the reported one: `stream.dst`/`stream.port` null handling and port coercion, `stream`/`snapshot` sub-field schema validation, and the `doctor` response shape documented in `examples/agent-workflows.md` |
| 7th (`eea996a`) | 4 | VLC probe fixtures made executable on POSIX, `--version` probe required to exit zero, zero snapshot ratios rejected instead of silently substituted, root `skills/` copy kept in sync with the packaged one |
| class sweep (2) | — | Same audit applied to the paths the first sweep did not reach: the **REPL** (which validated nothing) and **on-disk atomicity**. `add-input` / `set-output` now validate in the REPL exactly as the Click commands do; `save_job` writes to a temp sibling and renames; `ReplSkin` no longer creates `~/.cli-anything-*` merely by being constructed |
| proactive | — | every *data-level* `--json` failure emits structured JSON: missing media file (`info` / `add-input`), output path that is a directory (`set-output`), missing `--project` (`project show`) |

> The 6th round went *up* (4 → 6) because two findings were second instances of classes
> fixed in earlier rounds: the non-finite-number hole had only been closed on the
> `set-option` path, not `set-snapshot`, and snapshot temp-file cleanup had only been
> added to `run_transcode`, not `run_snapshot`. Closing a class means auditing *every*
> path through it, not the one that was reported.

> The `nan` / `inf` finding is the important one: `float()` accepts them, and the
> resulting `NaN` / `Infinity` tokens are **not valid JSON**, so strict agent parsers
> could consume neither the `--json` response nor the saved project. Numeric options are
> now required to be finite, both when set and when a project is loaded.

> The proactive row was not a review finding: the remaining `--json` failures are pure
> CLI syntax errors (missing argument, unknown option/command), which still exit 2 with
> Click's human-only text. Those are deliberately left alone — they are command-line
> misuse rather than the agent-facing data contract, and changing them means overriding
> Click's own usage-error handling.

### E2E — `pytest cli_anything/vlc/tests/test_full_e2e.py -v` (real VLC 3.0.21)

```
platform win32 -- Python 3.14.3, pytest-9.1.1, VLC 3.0.21 Vetinari (win64 portable)
collected 5 items

test_transcode_wav_to_wav PASSED              # real vlc transcode -> output exists, >1KB, 'RIFF' magic
test_transcode_replaces_stale_output PASSED   # pre-existing destination replaced, never passed off as fresh
test_info_wav PASSED                          # real vlc --stats probe, playback bounded by --run-time
test_stream_udp PASSED                        # real vlc UDP stream 1s, exit 0
test_cli_transcode_end_to_end PASSED          # full agent flow via --json

============================= 5 passed =============================
```

Whole suite against a real VLC: **93 passed, 1 skipped in 8.30s** (88 unit + 5 E2E).
Without VLC installed, the unit layer alone: **88 passed, 1 skipped in 1.24s**.

The E2E run is also what validates the decisions that cannot be unit-tested:

- `run_info` bounded by `--run-time` returns `--stats` output within the bound (round 4's P1).
- `find_vlc()`'s `--version` probe accepts a real VLC and `doctor` reports
  `{"checks": [{"ok": true, "path": ...}], "ready": true}` with exit 0 (rounds 6–7).
- A real `--sout` chain transcode produces a valid file, and the temp-and-replace path
  replaces a stale destination rather than reporting it as fresh output.


Run locally (VLC on PATH, or `VLC_BINARY` set):

```bash
pip install -e '.[dev]'
VLC_BINARY=/path/to/vlc pytest cli_anything/vlc/tests/ -v
```

**Verified empirically against the real engine:**

- `WAV → WAV`: `--sout '#transcode{acodec=s16l}:std{access=file,mux=wav,dst=out.wav}'` produces a valid `RIFF` file.
- `WAV → MP3`: `acodec=mp3,mux=mp3` → valid MP3 frame (`ff e3…`).
- `WAV → AAC/FLAC/OPUS`: `acodec=mp4a/flac/opus` all produce valid containers.
- `acodec=wav` (friendly) is resolved to the canonical VLC `s16l`; raw `vlc` codec ids are also accepted.

> **Non-negotiable (HARNESS.md):** E2E tests MUST invoke the real software and FAIL
> (not skip) when VLC is missing. They use `pytest.fail` for that.

**Coverage notes:**

- Unit layer covers the full data model, undo/redo session, `--sout` chain construction,
  codec-alias resolution, and stats parsing — the parts most likely to regress.
- E2E layer proves the harness drives the authentic VLC engine end-to-end for transcode,
  info, and stream. Snapshot extraction is video-only (VLC's scene filter needs a video
  stream) and is validated manually with a real video sample.
