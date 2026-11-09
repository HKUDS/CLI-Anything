# Turso test plan

Written before test implementation.

## Inventory

- `test_core.py`: approximately 15 backend-independent tests for typed JSON,
  identifier quoting, CRUD compilation, session locking/validation, and CLI errors.
- `test_full_e2e.py`: approximately 15 integration tests using native pyturso 0.8.3
  and installed CLI subprocesses. Missing native dependencies fail, never skip.

## Unit plan

Test positional/named parameters, blobs, finite numbers and signed 64-bit limits;
reject invalid JSON shapes. Compile identifiers and equality/NULL predicates
without interpolating values. Verify session save/load/clear and malformed-state
errors. Verify missing SDK and unsupported version diagnostics without fallback.

## Native workflows

Create only new owned fixtures beneath pytest's explicit `--basetemp` in the
private task data directory (or an explicitly chosen private directory elsewhere).

1. Create/open a database with spaces in its path; verify explicit selection and
   prevent implicit creation/overwrite. Inspect schema and table columns.
2. Bind Unicode, quotes, pipes, newlines, NULL, integers and blobs; cap SQL output;
   verify durable CRUD and export JSON/CSV content. Independently read a closed
   fixture through the actual tursodb binary, including `turso_version()`.
3. Commit a multi-operation transaction and reopen; provoke a UNIQUE failure and
   prove complete rollback. Provoke a deferred FK failure at explicit COMMIT and
   prove nonzero error propagation and durable absence after reopen.
4. Exercise malformed SQL, extra statements, invalid parameters, missing database,
   missing dependency and export collisions. Verify stdout/stderr JSON contracts.
5. Replay CLI commands through the default piped REPL, including selection changes,
   session persistence and an error followed by recovery; validate JSON lines and
   nonzero aggregate exit status. Exercise installed entry point from arbitrary cwd.

No Cloud, MCP, live/user databases, sync, AgentFS, libSQL, concurrency, MVCC,
backup fidelity, query time/memory limits, or full SQLite compatibility is qualified.

## Results

Native installed-CLI run: **50 passed in 12.87s** (28 unit cases, 22 native
integration cases; no skips). Platform: Linux x86_64, Python 3.14.10, pyturso 0.8.3.
The complete verbose output follows, with private installation/root paths
normalized. Command used `-v --tb=short`; no traceback was emitted.

After the full run, a numbered-placeholder alias edge case was fixed and its two
unit/native cases passed in 0.80s. The missing-SDK isolated launcher was also made
compatible with the documented module fallback and its native dependency-negative
case passed again. These targeted checks cover the only subsequent code changes.
No unchanged full-suite rerun was needed.

```text

============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0 -- <private-env>/bin/python
cachedir: .pytest_cache
rootdir: <checkout>/turso/agent-harness
collecting ... collected 50 items

turso/agent-harness/cli_anything/turso/tests/test_core.py::test_parameter_types_and_blob_round_trip PASSED [  2%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_bound_values[9223372036854775808] PASSED [  4%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_bound_values[-9223372036854775809] PASSED [  6%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_bound_values[inf] PASSED [  8%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_bound_values[nan] PASSED [ 10%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_bound_values[value4] PASSED [ 12%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_bound_values[value5] PASSED [ 14%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_bound_values[value6] PASSED [ 16%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_json[NaN] PASSED [ 18%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_json[Infinity] PASSED [ 20%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_json[[1,]] PASSED [ 22%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_json[{] PASSED [ 24%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_bad_parameter_shape PASSED [ 26%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_identifiers_and_predicates PASSED [ 28%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_crud_compilation_binds_values PASSED [ 30%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_crud_operations[op0] PASSED [ 32%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_crud_operations[op1] PASSED [ 34%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_crud_operations[op2] PASSED [ 36%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_crud_operations[op3] PASSED [ 38%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_crud_operations[op4] PASSED [ 40%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_invalid_crud_operations[op5] PASSED [ 42%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_session_round_trip_and_malformed_file_preservation PASSED [ 44%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_no_implicit_creation PASSED [ 46%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_missing_dependency PASSED [ 48%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_unsupported_dependency PASSED [ 50%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_usage_error_is_structured PASSED [ 52%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_missing_selection_is_structured PASSED [ 54%]
turso/agent-harness/cli_anything/turso/tests/test_core.py::test_sql_parameter_slots_ignore_literals_and_comments PASSED [ 56%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_help_and_native_dependency PASSED [ 58%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_database_selection_schema_and_no_overwrite PASSED [ 60%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_crud_binds_escaping_and_null PASSED [ 62%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_quoted_table_and_column_names PASSED [ 64%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_sql_row_cap_and_returning_are_durable PASSED [ 66%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_transaction_commit_and_constraint_rollback PASSED [ 68%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_deferred_commit_failure_propagates_and_rolls_back PASSED [ 70%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_sql_failures_are_json[SELEC bad-[]] PASSED [ 72%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_sql_failures_are_json[SELECT 1; SELECT 2-[]] PASSED [ 74%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_sql_failures_are_json[SELECT ?-[]] PASSED [ 76%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_sql_failures_are_json[SELECT ?-[9223372036854775808]] PASSED [ 78%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_sql_failures_are_json[SELECT ?-[NaN]] PASSED [ 80%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_missing_database_and_parent_never_created PASSED [ 82%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_json_and_csv_export_content PASSED [ 84%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_default_repl_selection_persistence_and_recovery PASSED [ 86%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_repl_success_and_usage_error PASSED [ 88%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_native_binary_independent_readback PASSED [ 90%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_held_native_lock_fails_promptly_and_recovers PASSED [ 92%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_repl_releases_locks_after_success_and_failure PASSED [ 94%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_missing_sdk_in_separate_environment PASSED [ 96%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_session_lock_refusal_is_bounded PASSED [ 98%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_named_prefixes_missing_binds_and_literal_escaping PASSED [100%]

============================= 50 passed in 12.87s ==============================
```

## Final targeted parameter regression

```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0 -- <private-env>/bin/python
cachedir: .pytest_cache
rootdir: <checkout>/turso/agent-harness
collecting ... collected 2 items

turso/agent-harness/cli_anything/turso/tests/test_core.py::test_sql_parameter_slots_ignore_literals_and_comments PASSED [ 50%]
turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_named_prefixes_missing_binds_and_literal_escaping PASSED [100%]

============================== 2 passed in 0.80s ===============================
```

## Final dependency-negative launcher check

```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0 -- <private-env>/bin/python
cachedir: .pytest_cache
rootdir: <checkout>/turso/agent-harness
collecting ... collected 1 item

turso/agent-harness/cli_anything/turso/tests/test_full_e2e.py::test_missing_sdk_in_separate_environment PASSED [100%]

============================== 1 passed in 0.16s ===============================
```

## Evidence and limits

The suite exercised real native SDK reads/writes and independent tursodb readback,
JSON/CSV exports with escaping, explicit deferred-COMMIT failure and rollback,
atomic manifest rollback, CLI/REPL selection, missing SDK/path errors, row caps,
and prompt native/session lock refusal. A held-REPL test independently opened the
fixture after success and failure, proving connection release in those cases.

Initial development runs exposed incomplete binds, prefix reuse and SDK object
lock lifetime. Parameter normalization and reference release address those tested
cases. tursodb binary `--version` and its SQL version function are separate evidence.

Interactive TTY appearance, non-Linux hosts, unbounded SQL workloads, native
crash recovery, full SQL grammar, schema-specific extension/FTS/vector features,
concurrency/MVCC, deployment and database backup fidelity are not qualified.
Use an external process timeout for SQL. Result limits cap retained/output rows,
not per-cell bytes, execution time or engine memory. All fixtures were synthetic.
