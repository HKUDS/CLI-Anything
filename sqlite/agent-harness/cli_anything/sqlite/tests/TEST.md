# SQLite harness test plan

## Inventory

- `test_core.py`: 67 test cases against temporary real SQLite databases.
- `test_full_e2e.py`: 22 installed-command cases and workflows.

## Core behavior

Verify exclusive database creation and backup, URI-safe paths, read-only queries,
positional and named parameters, binary/null values, duplicate result columns,
bounded results, statement deadlines, schema introspection (including quoted
identifiers, views, foreign keys and indexes), integrity checks, and atomic writes.
Batch failure must roll back all earlier statements, including DDL; user SQL must
not escape the transaction with COMMIT, SAVEPOINT, ATTACH, or PRAGMA changes.

CSV tests cover Unicode and embedded newlines, streaming insertion, column mapping,
duplicate/missing headers, malformed rows, foreign-key failures, rollback, and
exclusive exports. Export and backup failures must leave no partial destination.
Read-only commands must not create a missing database.

## End-to-end behavior

Install the actual entry point into an isolated environment and invoke it from
subprocesses. Check help, parseable JSON for successful commands and errors,
database creation, schema creation, parameterized writes, CSV import/export,
online backup, and independent SQLite readback. Run the default REPL with scripted
input and verify database selection, history, and exit behavior. Inspect built
wheel contents for the packaged skill and namespace-package layout.

## Realistic workflows

1. **Inventory ingest:** create database, batch-create schema, import Unicode CSV,
   query a filtered report, export it, and verify exact CSV rows.
2. **Failed migration:** run a batch that creates a table then violates a constraint;
   verify neither schema nor inserted rows survive.
3. **Consistent backup:** insert committed data with WAL enabled, back up using
   SQLite's online backup API, and read the copy independently.
4. **Agent inspection:** inspect a database, list/describe its schema, run a bounded
   read-only query, and confirm mutation attempts fail without changing data.

## Coverage boundaries

Tests exercise the actual SQLite engine through Python's standard-library binding.
The native `sqlite3` executable independently reads generated databases where
installed; it is required for the end-to-end suite. GUI interactions, encrypted
databases, extensions, and remote databases are outside this harness's scope.

## Results

Validated on macOS with Python 3.10.8, Python-linked SQLite 3.37.2,
native sqlite3 3.54.0, Click 8.3.3, prompt-toolkit 3.0.53, and pytest 8.4.2.

- Full suite with the editable installed entry point: **89 passed** (67 core, 22 E2E).
- Replaced the editable installation with the built wheel and ran the 22 E2E
  cases again from `/private/tmp`: **22 passed**. Confirmed the imported package
  lives in `site-packages`, not the source checkout.
- Wheel inspection: namespace package preserved; packaged skill and README
  present; test sources and caches excluded.
- Root skill mirror validator, registry entry/path validation, shared skin
  byte-for-byte comparison, and `git diff --check` passed.

No backend was mocked and no tests were skipped. Native sqlite3 independently
read the CSV workflow backup, rollback results, and committed WAL snapshot.
Terminal rendering/keybindings, Windows/Linux, encrypted files, large-file
performance, and recovery after process termination were not exercised.

Full output of `CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest
cli_anything/sqlite/tests -v --tb=no` (local paths abbreviated):

```text
============================= test session starts ==============================
platform darwin -- Python 3.10.8, pytest-8.4.2, pluggy-1.7.0 -- <venv>/bin/python
cachedir: .pytest_cache
rootdir: <harness>
collecting ... collected 89 items

cli_anything/sqlite/tests/test_core.py::test_create_real_database_and_refuse_overwrite PASSED [  1%]
cli_anything/sqlite/tests/test_core.py::test_missing_database_is_not_created[info] PASSED [  2%]
cli_anything/sqlite/tests/test_core.py::test_missing_database_is_not_created[check] PASSED [  3%]
cli_anything/sqlite/tests/test_core.py::test_missing_database_is_not_created[schema] PASSED [  4%]
cli_anything/sqlite/tests/test_core.py::test_missing_database_is_not_created[<lambda>0] PASSED [  5%]
cli_anything/sqlite/tests/test_core.py::test_missing_database_is_not_created[<lambda>1] PASSED [  6%]
cli_anything/sqlite/tests/test_core.py::test_uri_special_characters PASSED [  7%]
cli_anything/sqlite/tests/test_core.py::test_named_and_positional_parameters_prevent_sql_interpolation PASSED [  8%]
cli_anything/sqlite/tests/test_core.py::test_blobs_nulls_and_duplicate_column_names PASSED [ 10%]
cli_anything/sqlite/tests/test_core.py::test_nonfinite_database_value_is_json_safe PASSED [ 11%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[None] PASSED [ 12%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[x] PASSED [ 13%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[1] PASSED [ 14%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value3] PASSED [ 15%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value4] PASSED [ 16%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value5] PASSED [ 17%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value6] PASSED [ 19%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value7] PASSED [ 20%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value8] PASSED [ 21%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value9] PASSED [ 22%]
cli_anything/sqlite/tests/test_core.py::test_invalid_parameters_rejected[value10] PASSED [ 23%]
cli_anything/sqlite/tests/test_core.py::test_query_is_always_read_only[DELETE FROM items] PASSED [ 24%]
cli_anything/sqlite/tests/test_core.py::test_query_is_always_read_only[INSERT INTO items(name) VALUES ('bad')] PASSED [ 25%]
cli_anything/sqlite/tests/test_core.py::test_query_is_always_read_only[CREATE TABLE bad(x)] PASSED [ 26%]
cli_anything/sqlite/tests/test_core.py::test_query_is_always_read_only[WITH c(x) AS (VALUES ('bad')) INSERT INTO items(name) SELECT x FROM c] PASSED [ 28%]
cli_anything/sqlite/tests/test_core.py::test_sql_cannot_escape_transaction[COMMIT] PASSED [ 29%]
cli_anything/sqlite/tests/test_core.py::test_sql_cannot_escape_transaction[ROLLBACK] PASSED [ 30%]
cli_anything/sqlite/tests/test_core.py::test_sql_cannot_escape_transaction[BEGIN] PASSED [ 31%]
cli_anything/sqlite/tests/test_core.py::test_sql_cannot_escape_transaction[SAVEPOINT escape] PASSED [ 32%]
cli_anything/sqlite/tests/test_core.py::test_sql_cannot_escape_transaction[PRAGMA user_version=7] PASSED [ 33%]
cli_anything/sqlite/tests/test_core.py::test_sql_cannot_escape_transaction[ATTACH DATABASE ':memory:' AS other] PASSED [ 34%]
cli_anything/sqlite/tests/test_core.py::test_sql_cannot_escape_transaction[SELECT load_extension('anything')] PASSED [ 35%]
cli_anything/sqlite/tests/test_core.py::test_batch_rolls_back_ddl_and_data PASSED [ 37%]
cli_anything/sqlite/tests/test_core.py::test_batch_commits_and_reports_changes_including_trigger_effects PASSED [ 38%]
cli_anything/sqlite/tests/test_core.py::test_invalid_batch_contract[statements0] PASSED [ 39%]
cli_anything/sqlite/tests/test_core.py::test_invalid_batch_contract[statements1] PASSED [ 40%]
cli_anything/sqlite/tests/test_core.py::test_invalid_batch_contract[statements2] PASSED [ 41%]
cli_anything/sqlite/tests/test_core.py::test_invalid_batch_contract[statements3] PASSED [ 42%]
cli_anything/sqlite/tests/test_core.py::test_invalid_batch_contract[statements4] PASSED [ 43%]
cli_anything/sqlite/tests/test_core.py::test_invalid_batch_contract[statements5] PASSED [ 44%]
cli_anything/sqlite/tests/test_core.py::test_multiple_statements_cannot_bypass_batch PASSED [ 46%]
cli_anything/sqlite/tests/test_core.py::test_results_are_bounded_but_returning_writes_complete PASSED [ 47%]
cli_anything/sqlite/tests/test_core.py::test_query_timeout_interrupts_actual_sqlite_work PASSED [ 48%]
cli_anything/sqlite/tests/test_core.py::test_busy_database_reports_failure_without_partial_write PASSED [ 49%]
cli_anything/sqlite/tests/test_core.py::test_batch_timeout_rolls_back_prior_schema_and_data PASSED [ 50%]
cli_anything/sqlite/tests/test_core.py::test_deferred_foreign_key_failure_at_commit_rolls_back PASSED [ 51%]
cli_anything/sqlite/tests/test_core.py::test_schema_preserves_user_names_similar_to_sqlite_prefix PASSED [ 52%]
cli_anything/sqlite/tests/test_core.py::test_schema_reports_generated_columns_indexes_foreign_keys_and_views PASSED [ 53%]
cli_anything/sqlite/tests/test_core.py::test_quoted_identifiers_are_not_sql PASSED [ 55%]
cli_anything/sqlite/tests/test_core.py::test_csv_round_trip_unicode_newlines_and_reordered_columns PASSED [ 56%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[] PASSED [ 57%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[name,name\nx,y\n] PASSED [ 58%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[name,NAME\nx,y\n] PASSED [ 59%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[,name\nx,y\n] PASSED [ 60%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[name\nx\ny,z\n] PASSED [ 61%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[name\nx\n"unterminated] PASSED [ 62%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[name\nx\nx\n] PASSED [ 64%]
cli_anything/sqlite/tests/test_core.py::test_invalid_csv_rolls_back_every_row[absent\nvalue\n] PASSED [ 65%]
cli_anything/sqlite/tests/test_core.py::test_header_only_csv_validates_target PASSED [ 66%]
cli_anything/sqlite/tests/test_core.py::test_csv_foreign_key_failure_rolls_back PASSED [ 67%]
cli_anything/sqlite/tests/test_core.py::test_csv_reports_ignored_rows_separately PASSED [ 68%]
cli_anything/sqlite/tests/test_core.py::test_export_refuses_existing_files_and_cleans_partial_output PASSED [ 69%]
cli_anything/sqlite/tests/test_core.py::test_export_rejects_writes PASSED [ 70%]
cli_anything/sqlite/tests/test_core.py::test_backup_includes_committed_wal_data_and_is_independently_readable PASSED [ 71%]
cli_anything/sqlite/tests/test_core.py::test_backup_refuses_source_existing_file_and_symlink PASSED [ 73%]
cli_anything/sqlite/tests/test_core.py::test_integrity_check_reports_foreign_key_violations PASSED [ 74%]
cli_anything/sqlite/tests/test_core.py::test_corrupt_source_does_not_leave_backup PASSED [ 75%]
cli_anything/sqlite/tests/test_full_e2e.py::test_help_and_version PASSED [ 76%]
cli_anything/sqlite/tests/test_full_e2e.py::test_inventory_csv_report_and_backup PASSED [ 77%]
cli_anything/sqlite/tests/test_full_e2e.py::test_parameters_blobs_and_bounded_results PASSED [ 78%]
cli_anything/sqlite/tests/test_full_e2e.py::test_failed_migration_leaves_no_schema_or_rows PASSED [ 79%]
cli_anything/sqlite/tests/test_full_e2e.py::test_query_rejects_mutation_and_transaction_control[DELETE FROM items] PASSED [ 80%]
cli_anything/sqlite/tests/test_full_e2e.py::test_query_rejects_mutation_and_transaction_control[COMMIT] PASSED [ 82%]
cli_anything/sqlite/tests/test_full_e2e.py::test_query_rejects_mutation_and_transaction_control[PRAGMA user_version=7] PASSED [ 83%]
cli_anything/sqlite/tests/test_full_e2e.py::test_query_rejects_mutation_and_transaction_control[ATTACH DATABASE ':memory:' AS external] PASSED [ 84%]
cli_anything/sqlite/tests/test_full_e2e.py::test_errors_are_single_json_documents[args0-1] PASSED [ 85%]
cli_anything/sqlite/tests/test_full_e2e.py::test_errors_are_single_json_documents[args1-1] PASSED [ 86%]
cli_anything/sqlite/tests/test_full_e2e.py::test_errors_are_single_json_documents[args2-2] PASSED [ 87%]
cli_anything/sqlite/tests/test_full_e2e.py::test_errors_are_single_json_documents[args3-2] PASSED [ 88%]
cli_anything/sqlite/tests/test_full_e2e.py::test_errors_are_single_json_documents[args4-2] PASSED [ 89%]
cli_anything/sqlite/tests/test_full_e2e.py::test_errors_are_single_json_documents[args5-1] PASSED [ 91%]
cli_anything/sqlite/tests/test_full_e2e.py::test_errors_are_single_json_documents[args6-2] PASSED [ 92%]
cli_anything/sqlite/tests/test_full_e2e.py::test_missing_database_does_not_create_file PASSED [ 93%]
cli_anything/sqlite/tests/test_full_e2e.py::test_corrupt_database_and_existing_output PASSED [ 94%]
cli_anything/sqlite/tests/test_full_e2e.py::test_integrity_failure_has_report_and_nonzero_status PASSED [ 95%]
cli_anything/sqlite/tests/test_full_e2e.py::test_online_backup_reads_committed_wal PASSED [ 96%]
cli_anything/sqlite/tests/test_full_e2e.py::test_scripted_repl_retains_session_and_continues_after_errors PASSED [ 97%]
cli_anything/sqlite/tests/test_full_e2e.py::test_plain_scripted_repl_reports_parse_error_without_crashing PASSED [ 98%]
cli_anything/sqlite/tests/test_full_e2e.py::test_packaged_skill_is_available PASSED [100%]

============================== 89 passed in 2.70s ==============================
```
