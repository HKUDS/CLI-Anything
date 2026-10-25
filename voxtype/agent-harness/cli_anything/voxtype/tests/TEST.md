# TEST.md — cli-anything-voxtype

## Part 1 — Test Plan

### Test Inventory Plan

| File | Planned tests | Needs voxtype? |
|------|---------------|----------------|
| `test_core.py` | ~45 unit tests | No — synthetic data, mocked backend |
| `test_full_e2e.py` | ~30 E2E + subprocess tests | **Yes** — real `voxtype`, `ffmpeg`, a whisper model |

E2E prerequisites (hard dependencies — tests fail, never skip, if missing):
`voxtype` on PATH (or `$VOXTYPE_BIN`), `ffmpeg`, and at least one installed whisper
model (`voxtype setup --download --model base.en`). Speech fixtures ship in
`tests/fixtures/`.

Every E2E test runs against a **temporary config file and temporary meeting
storage**; the user's real `~/.config/voxtype/config.toml` and meetings are never
written. The only tests that touch the live system are read-only probes
(`daemon status`, `info ...`).

### Unit Test Plan (`test_core.py`)

| Module | Functions | Edge cases | Count |
|--------|-----------|------------|-------|
| `core/project.py` | `create_workspace`, `validate_workspace`, `load_workspace`, `set_override`, `remove_override`, `override_flags`, `workspace_info` | wrong format marker, invalid JSON, unknown override key, boolean parsing (`yes/off/0`), value-less flag override, missing value | 12 |
| `core/session.py` | `Session.new/open/save_session`, `record`, `pop_undo`, `pop_redo`, `config_path` precedence, `_locked_save_json` | undo on empty stack, redo cleared by new record, history cap, save without workspace, `--config` overriding workspace | 10 |
| `core/transcribe.py` | `parse_transcribe_output`, `collect_inputs`, `export_results` | resample line, VAD line, "No speech detected", multi-line transcript, missing input, glob/dir expansion & dedupe, every export format, overwrite guard, unknown format | 11 |
| `core/config.py` | `value_to_cli`, `set_key`/`unset_key` with mocked backend, `undo_entry`/`redo_entry` routing, dry-run scratch copy | bool/float/None rendering, dry-run leaves file untouched, undo of absent key → unset | 6 |
| `core/daemon.py` | `record_args` | each output mode, `--file=` path, auto-submit tri-state, options rejected on stop/cancel, bad action/mode | 6 |
| `core/meeting.py` | `build_transcript`, `_storage_dir_name`, `list_meetings` on a synthetic DB, `resolve_id` | speaker cycling, gaps, title sanitizing, untitled name, prefix / ambiguous / `latest` | 6 |
| `utils/audio.py` | `probe_wav`, `rms_dbfs`, `write_tone`, `needs_conversion` | non-WAV file, silence → −inf | 4 |
| `voxtype_backend.py` | `_error_message`, `find_voxtype` with bad `$VOXTYPE_BIN` | strips `error:` prefix, skips whisper log noise | 3 |

### E2E Test Plan (`test_full_e2e.py`)

Real software invoked: `voxtype config get/set/unset/schema`, `voxtype transcribe`,
`voxtype meeting export/show/label/delete`, `voxtype status`, `voxtype info`, `ffmpeg`.

Verified output properties:
- **Transcripts**: exact/near-exact expected text for the fixtures ("Hello world!",
  "…voice activity detection…"); word counts; duration matches the WAV header.
- **Config files**: TOML on disk contains / no longer contains the key after
  set / unset / undo / redo; voxtype re-reads it (`config get`) with the expected
  typed value; invalid values return voxtype's exit code 2 and leave the file unchanged.
- **Text pipeline**: a replacement or spoken-punctuation setting changes the
  transcript voxtype produces (proves the config is really applied).
- **Meeting exports**: SRT parses (index lines, `HH:MM:SS,mmm --> ...` timestamps
  matching segment timing), VTT starts with `WEBVTT`, JSON parses with the expected
  segments and speaker labels, Markdown contains the title and labeled speakers.
- **Format conversion**: MP3 and 48 kHz stereo inputs (made with ffmpeg) produce the
  same transcript as the 16 kHz original.
- **VAD**: silence + energy VAD → `no_speech: true` and empty text.
- Artifact paths are printed for manual inspection.

### Realistic Workflow Scenarios

1. **Dictation tuning**
   *Simulates:* a user teaching voxtype their jargon.
   *Operations:* `project new` → `config replace add "voice activity detection" VAD`
   → `config set text.spoken_punctuation true` → `transcribe file` → `session undo`
   → `transcribe file` → `session redo`.
   *Verified:* transcript contains "VAD" only while the replacement is active; TOML
   reflects each step; history/redo depths.

2. **Podcast / voice-memo batch transcription**
   *Simulates:* transcribing a folder of mixed-format recordings.
   *Operations:* ffmpeg makes MP3 + 48 kHz stereo copies → `transcribe batch DIR -o out.csv`
   and `-o out.md` → `transcribe history` → `transcribe export all.json`.
   *Verified:* every file transcribed, CSV rows/columns, Markdown sections, JSON count.

3. **Meeting minutes from recordings**
   *Simulates:* turning two recorded call segments into minutes with named speakers.
   *Operations:* `config set meeting.storage_path TMP` → `meeting import a.wav b.wav --speakers 0,1 --gap-ms 500`
   → `meeting list` → `meeting label latest 1 Alice` → `meeting export -f srt/vtt/json/markdown`
   → `meeting delete --yes`.
   *Verified:* index.db row, SRT timing math (gap applied), labels applied by voxtype,
   meeting gone after delete.

4. **Safe experimentation (dry-run)**
   *Simulates:* an agent probing whether a setting is valid before committing.
   *Operations:* `--dry-run config set hotkey.key F13`, `--dry-run config set audio.feedback.volume 9`.
   *Verified:* valid value reported, invalid value rejected by voxtype (exit 2), config
   file byte-identical and workspace history unchanged in both cases.

5. **Undo/redo stress**
   *Simulates:* iterative refinement of many settings.
   *Operations:* 8 mixed set/unset operations → undo all → redo all.
   *Verified:* config after full undo equals the original file's key set; after full
   redo equals the final state.

6. **Status introspection**
   *Simulates:* an agent checking the daemon before acting.
   *Operations:* `daemon status`, `info engines/models/devices`, `config schema --section Text`.
   *Verified:* JSON structure (state field, ≥1 compiled engine, installed model listed).

### Subprocess Tests (`TestCLISubprocess`)

Run through `_resolve_cli("cli-anything-voxtype")` (no hardcoded paths, no `cwd`):
`--help`, `--version`, `--json info engines`, `project new` JSON, config set/get/undo
round trip, `transcribe file` JSON, `meeting import` + `export -o x.srt`, error JSON
for an invalid value, `--dry-run` file preservation.

---

## Part 2 — Test Results

Run on 2026-10-25, Arch Linux (Omarchy), voxtype 1.1.1 (whisper, CPU AVX2,
model `base.en`), ffmpeg on PATH, Python 3.15.1, installed command
`~/.local/bin/cli-anything-voxtype` (`CLI_ANYTHING_FORCE_INSTALLED=1`; the run
printed `[_resolve_cli] Using installed command: ~/.local/bin/cli-anything-voxtype`).

Command:

```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/voxtype/tests/ -v --tb=no
```

```
============================= test session starts ==============================
platform linux -- Python 3.15.1, pytest-9.1.1, pluggy-1.7.0 -- ~/.local/share/cli-anything-voxtype-venv/bin/python
cachedir: .pytest_cache
rootdir: ~/src/CLI-Anything/voxtype/agent-harness
plugins: cov-7.1.0
collecting ... collected 115 items

cli_anything/voxtype/tests/test_core.py::TestProject::test_create_workspace_defaults PASSED [  0%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_create_workspace_absolutizes_config PASSED [  1%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_validate_rejects_wrong_format PASSED [  2%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_validate_fills_missing_fields PASSED [  3%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_load_invalid_json PASSED [  4%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_load_missing PASSED [  5%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_set_override_value PASSED [  6%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_set_override_unknown PASSED [  6%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_set_override_requires_value PASSED [  7%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_set_override_bool_parsing[yes-True] PASSED [  8%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_set_override_bool_parsing[off-False] PASSED [  9%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_set_override_bool_parsing[0-False] PASSED [ 10%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_set_override_bool_parsing[None-True] PASSED [ 11%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_override_flags_translation PASSED [ 12%]
cli_anything/voxtype/tests/test_core.py::TestProject::test_remove_override_and_info PASSED [ 13%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_new_and_save_roundtrip PASSED [ 13%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_save_without_workspace PASSED [ 14%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_undo_empty PASSED [ 15%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_undo_redo_stacks PASSED [ 16%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_new_record_clears_redo PASSED [ 17%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_history_cap PASSED [ 18%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_record_without_workspace_is_noop PASSED [ 19%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_config_path_precedence PASSED [ 20%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_locked_save_truncates PASSED [ 20%]
cli_anything/voxtype/tests/test_core.py::TestSession::test_status_and_transcription_log PASSED [ 21%]
cli_anything/voxtype/tests/test_core.py::TestTranscribeParsing::test_full_report PASSED [ 22%]
cli_anything/voxtype/tests/test_core.py::TestTranscribeParsing::test_no_speech PASSED [ 23%]
cli_anything/voxtype/tests/test_core.py::TestTranscribeParsing::test_minimal PASSED [ 24%]
cli_anything/voxtype/tests/test_core.py::TestTranscribeParsing::test_garbage PASSED [ 25%]
cli_anything/voxtype/tests/test_core.py::TestCollectInputs::test_dir_glob_and_dedupe PASSED [ 26%]
cli_anything/voxtype/tests/test_core.py::TestCollectInputs::test_missing PASSED [ 26%]
cli_anything/voxtype/tests/test_core.py::TestExportResults::test_each_format[txt] PASSED [ 27%]
cli_anything/voxtype/tests/test_core.py::TestExportResults::test_each_format[md] PASSED [ 28%]
cli_anything/voxtype/tests/test_core.py::TestExportResults::test_each_format[json] PASSED [ 29%]
cli_anything/voxtype/tests/test_core.py::TestExportResults::test_each_format[csv] PASSED [ 30%]
cli_anything/voxtype/tests/test_core.py::TestExportResults::test_each_format[jsonl] PASSED [ 31%]
cli_anything/voxtype/tests/test_core.py::TestExportResults::test_overwrite_guard PASSED [ 32%]
cli_anything/voxtype/tests/test_core.py::TestExportResults::test_bad_format_and_empty PASSED [ 33%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_value_to_cli[True-true] PASSED [ 33%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_value_to_cli[False-false] PASSED [ 34%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_value_to_cli[0.7-0.7] PASSED [ 35%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_value_to_cli[5-5] PASSED [ 36%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_value_to_cli[F13-F13] PASSED [ 37%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_value_to_cli_none PASSED [ 38%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_set_records_old_and_new PASSED [ 39%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_dry_run_uses_scratch PASSED [ 40%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_undo_absent_key_unsets_and_redo_resets PASSED [ 40%]
cli_anything/voxtype/tests/test_core.py::TestConfigLogic::test_resolved_path_default PASSED [ 41%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_plain PASSED [ 42%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_modes[type] PASSED [ 43%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_modes[clipboard] PASSED [ 44%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_modes[paste] PASSED [ 45%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_file PASSED [ 46%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_full_options PASSED [ 46%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_stop_rejects_options PASSED [ 47%]
cli_anything/voxtype/tests/test_core.py::TestRecordArgs::test_bad_action_and_mode PASSED [ 48%]
cli_anything/voxtype/tests/test_core.py::TestMeetingLogic::test_build_transcript_timeline PASSED [ 49%]
cli_anything/voxtype/tests/test_core.py::TestMeetingLogic::test_build_transcript_no_speakers PASSED [ 50%]
cli_anything/voxtype/tests/test_core.py::TestMeetingLogic::test_storage_dir_name PASSED [ 51%]
cli_anything/voxtype/tests/test_core.py::TestMeetingLogic::test_list_and_resolve PASSED [ 52%]
cli_anything/voxtype/tests/test_core.py::TestMeetingLogic::test_list_without_db PASSED [ 53%]
cli_anything/voxtype/tests/test_core.py::TestMeetingLogic::test_schema_matches_voxtype_columns PASSED [ 53%]
cli_anything/voxtype/tests/test_core.py::TestAudio::test_tone_probe_and_rms PASSED [ 54%]
cli_anything/voxtype/tests/test_core.py::TestAudio::test_silence_rms PASSED [ 55%]
cli_anything/voxtype/tests/test_core.py::TestAudio::test_non_wav PASSED  [ 56%]
cli_anything/voxtype/tests/test_core.py::TestAudio::test_missing PASSED  [ 57%]
cli_anything/voxtype/tests/test_core.py::TestBackendHelpers::test_error_message_strips_prefix PASSED [ 58%]
cli_anything/voxtype/tests/test_core.py::TestBackendHelpers::test_error_message_skips_log_noise PASSED [ 59%]
cli_anything/voxtype/tests/test_core.py::TestBackendHelpers::test_bad_voxtype_bin PASSED [ 60%]
cli_anything/voxtype/tests/test_core.py::TestCLINoBackend::test_help PASSED [ 60%]
cli_anything/voxtype/tests/test_core.py::TestCLINoBackend::test_project_new_and_override PASSED [ 61%]
cli_anything/voxtype/tests/test_core.py::TestCLINoBackend::test_dry_run_project_override_not_saved PASSED [ 62%]
cli_anything/voxtype/tests/test_core.py::TestCLINoBackend::test_missing_workspace_errors PASSED [ 63%]
cli_anything/voxtype/tests/test_core.py::TestCLINoBackend::test_undo_without_history PASSED [ 64%]
cli_anything/voxtype/tests/test_core.py::TestCLINoBackend::test_meeting_delete_requires_yes PASSED [ 65%]
cli_anything/voxtype/tests/test_full_e2e.py::TestPrerequisites::test_voxtype_installed PASSED [ 66%]
cli_anything/voxtype/tests/test_full_e2e.py::TestPrerequisites::test_ffmpeg_installed PASSED [ 66%]
cli_anything/voxtype/tests/test_full_e2e.py::TestPrerequisites::test_whisper_model_installed PASSED [ 67%]
cli_anything/voxtype/tests/test_full_e2e.py::TestPrerequisites::test_fixtures_are_voxtype_native PASSED [ 68%]
cli_anything/voxtype/tests/test_full_e2e.py::TestConfigE2E::test_set_get_unset_roundtrip PASSED [ 69%]
cli_anything/voxtype/tests/test_full_e2e.py::TestConfigE2E::test_typed_values PASSED [ 70%]
cli_anything/voxtype/tests/test_full_e2e.py::TestConfigE2E::test_invalid_value_rejected_file_unchanged PASSED [ 71%]
cli_anything/voxtype/tests/test_full_e2e.py::TestConfigE2E::test_dry_run_validates_without_writing PASSED [ 72%]
cli_anything/voxtype/tests/test_full_e2e.py::TestConfigE2E::test_undo_restores_previous_value PASSED [ 73%]
cli_anything/voxtype/tests/test_full_e2e.py::TestConfigE2E::test_replacements PASSED [ 73%]
cli_anything/voxtype/tests/test_full_e2e.py::TestConfigE2E::test_schema_filters PASSED [ 74%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_hello PASSED [ 75%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_long PASSED [ 76%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_replacement_applied_by_voxtype PASSED [ 77%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_mp3_converted_by_ffmpeg PASSED [ 78%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_48k_stereo_resampled_by_voxtype PASSED [ 79%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_silence_with_energy_vad PASSED [ 80%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_speech_passes_energy_vad PASSED [ 80%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_missing_file PASSED [ 81%]
cli_anything/voxtype/tests/test_full_e2e.py::TestTranscribeE2E::test_bad_engine_errors PASSED [ 82%]
cli_anything/voxtype/tests/test_full_e2e.py::TestMeetingE2E::test_import_creates_native_meeting PASSED [ 83%]
cli_anything/voxtype/tests/test_full_e2e.py::TestMeetingE2E::test_export_formats PASSED [ 84%]
cli_anything/voxtype/tests/test_full_e2e.py::TestMeetingE2E::test_get_meeting_json_and_list PASSED [ 85%]
cli_anything/voxtype/tests/test_full_e2e.py::TestMeetingE2E::test_export_overwrite_guard_and_bad_format PASSED [ 86%]
cli_anything/voxtype/tests/test_full_e2e.py::TestMeetingE2E::test_delete PASSED [ 86%]
cli_anything/voxtype/tests/test_full_e2e.py::TestSystemE2E::test_engines PASSED [ 87%]
cli_anything/voxtype/tests/test_full_e2e.py::TestSystemE2E::test_models_and_devices PASSED [ 88%]
cli_anything/voxtype/tests/test_full_e2e.py::TestSystemE2E::test_daemon_status_shape PASSED [ 89%]
cli_anything/voxtype/tests/test_full_e2e.py::TestSystemE2E::test_service_status PASSED [ 90%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED [ 91%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_version PASSED [ 92%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_info_engines_json PASSED [ 93%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_project_new_json PASSED [ 93%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_dictation_tuning_workflow PASSED [ 94%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_batch_workflow PASSED [ 95%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_meeting_workflow PASSED [ 96%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_dry_run_workflow PASSED [ 97%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_undo_redo_stress PASSED [ 98%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_status_introspection PASSED [ 99%]
cli_anything/voxtype/tests/test_full_e2e.py::TestCLISubprocess::test_error_json_for_missing_audio PASSED [100%]

============================= 115 passed in 44.00s =============================
```

### Summary Statistics

| Suite | Tests | Passed | Failed |
|-------|-------|--------|--------|
| `test_core.py` (unit) | 75 | 75 | 0 |
| `test_full_e2e.py` (E2E + subprocess) | 40 | 40 | 0 |
| **Total** | **115** | **115** | **0** (100%) |

Result line: `============================= 115 passed in 44.00s =============================`. Nearly all of the run time goes to real whisper inference
(about 1.5 s per file on CPU).

### Coverage Notes

- **Covered against the real backend:** config set/get/unset/schema/replacements
  (including voxtype's own range and key validation and exit code 2), dry-run on a
  scratch copy, undo/redo across 8 mixed operations, transcription of WAV/MP3/FLAC
  and 48 kHz stereo input, energy VAD no-speech detection, the replacement
  pipeline changing real transcripts, meeting import → label → export in
  srt/vtt/json/markdown/text → delete, and read-only daemon/info probes.
- **Not exercised automatically (on purpose):** `daemon record start/toggle` and
  `meeting start`, because they would capture the live microphone and type into
  the focused window. Their argument building is unit-tested (`TestRecordArgs`)
  and `daemon status` is probed for real. `daemon service start/stop/restart` is
  left out so the user's running daemon isn't disturbed.
- **Not exercised:** `setup download` (large network downloads), `meeting
  summarize` (needs Ollama or a remote LLM), and non-whisper engines (not compiled
  into this voxtype build; `info engines` reports them as not compiled).
- **Observed engine behavior:** whisper turns pure silence into "you" unless VAD
  is on. With the whisper engine, `--vad` alone does nothing until the Silero
  model is downloaded (`setup vad`); `--vad-backend energy` works with no download.
