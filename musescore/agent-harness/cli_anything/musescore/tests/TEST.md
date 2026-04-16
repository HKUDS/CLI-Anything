# TEST.md — Test Plan and Results

## Test Plan

### Unit Tests (`test_core.py`)

| # | Test | Module | Description |
|---|------|--------|-------------|
| 1 | TestSession::test_create_session | session | Create empty session |
| 2 | TestSession::test_set_project | session | Set project data and path |
| 3 | TestSession::test_get_project_raises | session | Error when no project open |
| 4 | TestSession::test_undo_redo | session | Undo/redo state transitions |
| 5 | TestSession::test_undo_empty_raises | session | Error on empty undo |
| 6 | TestSession::test_redo_empty_raises | session | Error on empty redo |
| 7 | TestSession::test_snapshot_clears_redo | session | New edit clears redo |
| 8 | TestSession::test_history | session | History tracking |
| 9 | TestSession::test_status | session | Status dict format |
| 10 | TestSession::test_modified_flag | session | Modified flag tracking |
| 11 | TestSession::test_save_session | session | JSON persistence with locking |
| 12 | TestKeySignature::test_major_keys | mscx_xml | Key name → int (majors) |
| 13 | TestKeySignature::test_minor_keys | mscx_xml | Key name → int (minors) |
| 14 | TestKeySignature::test_case_insensitive | mscx_xml | Case-insensitive lookup |
| 15 | TestKeySignature::test_invalid_key | mscx_xml | Error on invalid key |
| 16 | TestKeySignature::test_int_to_name | mscx_xml | Int → key name |
| 17 | TestKeySignature::test_all_major_keys_roundtrip | mscx_xml | Full roundtrip |
| 18 | TestTranspose::test_semitones_* | transpose | Semitone → interval mapping |
| 19 | TestXMLParsing::test_get_key_signature | mscx_xml | XML key sig extraction |
| 20 | TestXMLParsing::test_get_time_signature | mscx_xml | XML time sig extraction |
| 21 | TestXMLParsing::test_get_instruments | mscx_xml | XML instrument extraction |
| 22 | TestXMLParsing::test_get_score_title | mscx_xml | XML title extraction |
| 23 | TestXMLParsing::test_count_measures | mscx_xml | Measure counting |
| 24 | TestXMLParsing::test_count_notes | mscx_xml | Note counting |
| 25 | TestXMLParsing::test_detect_format | mscx_xml | Format detection |
| 26 | TestXMLParsing::test_mscz_roundtrip | mscx_xml | MSCZ write + read |
| 27 | TestExportVerification::test_* | export | Magic byte verification |
| 28 | TestMediaStats::test_score_stats | media | Synthetic MXL stats |

### E2E Tests (`test_full_e2e.py`)

| # | Test | Requires | Description |
|---|------|----------|-------------|
| 1 | TestExportE2E::test_export_pdf | mscore + samples | Export PDF, verify magic |
| 2 | TestExportE2E::test_export_midi | mscore + samples | Export MIDI, verify magic |
| 3 | TestExportE2E::test_export_mp3 | mscore + samples | Export MP3, verify magic |
| 4 | TestExportE2E::test_export_musicxml | mscore + samples | Export MusicXML, verify XML |
| 5 | TestExportE2E::test_export_png | mscore + samples | Export PNG pages |
| 6 | TestTransposeE2E::test_transpose_db_to_c | mscore + samples | Db→C key verification |
| 7 | TestTransposeE2E::test_transpose_by_interval | mscore + samples | Interval transpose |
| 8 | TestPartsE2E::test_list_parts | mscore + samples | Part listing |
| 9 | TestPartsE2E::test_extract_part | mscore + samples | Part extraction |
| 10 | TestMediaE2E::test_probe_mxl | mscore + samples | MXL metadata probe |
| 11 | TestMediaE2E::test_probe_mscz | mscore + samples | MSCZ metadata probe |
| 12 | TestMediaE2E::test_stats_mxl | mscore + samples | Score statistics |
| 13 | TestCLISubprocess::test_help | none | --help flag |
| 14 | TestCLISubprocess::test_json_project_info | mscore + samples | Subprocess JSON output |
| 15 | TestCLISubprocess::test_json_export_pdf | mscore + samples | Subprocess PDF export |
| 16 | TestCLISubprocess::test_json_transpose_by_key | mscore + samples | Subprocess transpose |
| 17 | TestCLISubprocess::test_full_workflow | mscore + samples | Info→transpose→export→verify |

## Test Results

```
$ python3 -m pytest cli_anything/musescore/tests/ -v --tb=short
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-7.4.4
rootdir: /Users/vickytam/Study/cli-anything/musescore/agent-harness

cli_anything/musescore/tests/test_core.py::TestSession::test_create_session PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_set_project PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_get_project_raises_without_open PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_undo_redo PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_undo_empty_raises PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_redo_empty_raises PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_snapshot_clears_redo PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_history PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_status PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_modified_flag PASSED
cli_anything/musescore/tests/test_core.py::TestSession::test_save_session PASSED
cli_anything/musescore/tests/test_core.py::TestKeySignature::test_major_keys PASSED
cli_anything/musescore/tests/test_core.py::TestKeySignature::test_minor_keys PASSED
cli_anything/musescore/tests/test_core.py::TestKeySignature::test_case_insensitive PASSED
cli_anything/musescore/tests/test_core.py::TestKeySignature::test_invalid_key PASSED
cli_anything/musescore/tests/test_core.py::TestKeySignature::test_int_to_name PASSED
cli_anything/musescore/tests/test_core.py::TestKeySignature::test_all_major_keys_roundtrip PASSED
cli_anything/musescore/tests/test_core.py::TestTranspose::test_semitones_to_interval_unison PASSED
cli_anything/musescore/tests/test_core.py::TestTranspose::test_semitones_to_interval_minor_second PASSED
cli_anything/musescore/tests/test_core.py::TestTranspose::test_semitones_to_interval_octave PASSED
cli_anything/musescore/tests/test_core.py::TestTranspose::test_semitones_to_interval_fifth PASSED
cli_anything/musescore/tests/test_core.py::TestTranspose::test_interval_enum_count PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_get_key_signature PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_get_time_signature PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_get_instruments PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_get_score_title PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_count_measures PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_count_notes PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_detect_format PASSED
cli_anything/musescore/tests/test_core.py::TestXMLParsing::test_mscz_roundtrip PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_ext_to_format PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_verify_nonexistent PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_verify_pdf PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_verify_midi PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_verify_mp3_sync PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_verify_mp3_id3 PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_verify_png PASSED
cli_anything/musescore/tests/test_core.py::TestExportVerification::test_verify_empty_file PASSED
cli_anything/musescore/tests/test_core.py::TestMediaStats::test_score_stats_from_mxl PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestExportE2E::test_export_pdf PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestExportE2E::test_export_midi PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestExportE2E::test_export_mp3 PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestExportE2E::test_export_musicxml PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestExportE2E::test_export_png PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestTransposeE2E::test_transpose_db_to_c PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestTransposeE2E::test_transpose_by_interval PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestPartsE2E::test_list_parts PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestPartsE2E::test_extract_part PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestMediaE2E::test_probe_mxl PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestMediaE2E::test_probe_mscz PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestMediaE2E::test_stats_mxl PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestCLISubprocess::test_json_project_info PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestCLISubprocess::test_json_export_pdf PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestCLISubprocess::test_json_transpose_by_key PASSED
cli_anything/musescore/tests/test_full_e2e.py::TestCLISubprocess::test_full_workflow PASSED

============================= 56 passed in 15.10s ==============================
```

**Environment**: macOS Darwin 24.1.0, Python 3.12.2, MuseScore 4.6.5
**Date**: 2026-03-19
**Status**: 56/56 PASSED (39 unit + 17 E2E)
