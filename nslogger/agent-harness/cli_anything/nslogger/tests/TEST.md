# TEST.md — cli-anything-nslogger

## Test Plan

### Unit Tests (`test_core.py`)

All tests use synthetic in-memory data — no external files or network required.

| Class | Coverage |
|-------|----------|
| `TestLogMessage` | `to_dict()`, `to_text_line()`, level/type name derivation for all types |
| `TestFilterMessages` | level, min-level, tag (case-insensitive), thread, text search, regex, limit, combined |
| `TestComputeStats` | totals, by_level, by_tag, by_thread, by_type, duration, timestamps, empty input |
| `TestExporter` | text, JSON (shape + validity), CSV (header + rows), `export_messages()` dispatcher |
| `TestWireProtocol` | encode→decode round-trip for text, timestamp, client-info; length prefix format |
| `TestGenerateSampleFile` | file creation, parseability, level variety |
| `TestParseRawFile` | single message, multiple messages, empty file |

### E2E Tests (`test_full_e2e.py`)

All tests use real files created by `generate_sample_file()` and real subprocess invocations.

| Class | Coverage |
|-------|----------|
| `TestGenerateCommand` | file creation, count in output, parseable result |
| `TestReadCommand` | output lines, `--json` shape, `--level` filter, `--limit`, `--search` |
| `TestFilterCommand` | `--level`, no-results, `--regex` |
| `TestExportCommand` | text/JSON/CSV stdout, `--output` file, `--level` pre-filter |
| `TestStatsCommand` | text summary, JSON shape, `by_level`, `by_tag` |
| `TestWorkflow` | generate→filter→export pipeline, stats on generated file, help output |
| `TestCLISubprocess` | installed entrypoint via `_resolve_cli()`: help, generate+read, stats JSON, export CSV |

### Scenarios NOT covered by automated tests

- `listen` command (requires live TCP client; integration test would need a network fixture)
- `repl` command (interactive terminal; tested manually)
- `.nsloggerdata` binary-plist format (requires a real NSLogger.app saved file)
- SSL/TLS listener mode

---

## Test Results

Run: `python3 -m pytest cli_anything/nslogger/tests/ -v --tb=no`

Platform: darwin / Python 3.13.2 / pytest 9.0.3

```
============================= test session starts ==============================
platform darwin -- Python 3.13.2, pytest-9.0.3, pluggy-1.6.0
collected 80 items

cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_level_name_known PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_level_name_unknown PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_type_name_text PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_type_name_image PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_type_name_data PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_type_name_client_info PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_dict_keys PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_dict_timestamp_isoformat PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_text_line_contains_text PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_text_line_contains_level PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_text_line_contains_tag PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_text_line_no_timestamp PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_text_line_image PASSED
cli_anything/nslogger/tests/test_core.py::TestLogMessage::test_to_text_line_binary PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_no_filter_passes_all PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_max_level PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_min_level PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_tag_filter PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_tag_case_insensitive PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_thread_filter PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_text_search PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_text_search_case_insensitive PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_regex_filter PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_limit PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_combined_filters PASSED
cli_anything/nslogger/tests/test_core.py::TestFilterMessages::test_empty_input PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_total PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_by_level PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_by_tag PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_by_thread PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_duration PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_timestamps PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_empty PASSED
cli_anything/nslogger/tests/test_core.py::TestComputeStats::test_by_type PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_text PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_json_valid PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_json_has_all_fields PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_csv_has_header PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_csv_has_data PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_messages_text PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_messages_json PASSED
cli_anything/nslogger/tests/test_core.py::TestExporter::test_export_messages_csv PASSED
cli_anything/nslogger/tests/test_core.py::TestWireProtocol::test_round_trip_text PASSED
cli_anything/nslogger/tests/test_core.py::TestWireProtocol::test_round_trip_timestamp PASSED
cli_anything/nslogger/tests/test_core.py::TestWireProtocol::test_round_trip_client_info PASSED
cli_anything/nslogger/tests/test_core.py::TestWireProtocol::test_encode_message_has_length_prefix PASSED
cli_anything/nslogger/tests/test_core.py::TestGenerateSampleFile::test_creates_file PASSED
cli_anything/nslogger/tests/test_core.py::TestGenerateSampleFile::test_parseable PASSED
cli_anything/nslogger/tests/test_core.py::TestGenerateSampleFile::test_varied_levels PASSED
cli_anything/nslogger/tests/test_core.py::TestParseRawFile::test_single_message PASSED
cli_anything/nslogger/tests/test_core.py::TestParseRawFile::test_multiple_messages PASSED
cli_anything/nslogger/tests/test_core.py::TestParseRawFile::test_empty_file PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestGenerateCommand::test_generate_creates_file PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestGenerateCommand::test_generate_output_mentions_count PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestGenerateCommand::test_generate_parseable PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestReadCommand::test_read_outputs_messages PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestReadCommand::test_read_json_valid PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestReadCommand::test_read_json_message_shape PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestReadCommand::test_read_level_filter PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestReadCommand::test_read_limit PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestReadCommand::test_read_search PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestFilterCommand::test_filter_by_level PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestFilterCommand::test_filter_no_results PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestFilterCommand::test_filter_regex PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestExportCommand::test_export_text_stdout PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestExportCommand::test_export_json_stdout PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestExportCommand::test_export_csv_stdout PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestExportCommand::test_export_to_file PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestExportCommand::test_export_with_level_filter PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestStatsCommand::test_stats_text_output PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestStatsCommand::test_stats_json_output PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestStatsCommand::test_stats_json_has_by_level PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestStatsCommand::test_stats_json_has_by_tag PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestWorkflow::test_generate_filter_export_pipeline PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestWorkflow::test_stats_on_generated_file PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestWorkflow::test_cli_help_shows_commands PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestCLISubprocess::test_installed_cli_help PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestCLISubprocess::test_installed_generate_and_read PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestCLISubprocess::test_installed_stats_json PASSED
cli_anything/nslogger/tests/test_full_e2e.py::TestCLISubprocess::test_installed_export_csv PASSED

============================== 80 passed in 3.55s ==============================
```

**Result: 80 passed, 0 failed (100% pass rate)**
