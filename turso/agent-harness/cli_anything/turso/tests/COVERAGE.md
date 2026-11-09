# Turso command and REPL proof matrix

Generated from the Click command tree; every advertised command, argument, option
and automatic help route has an evidence row. Names below refer to executable
cases in `test_full_e2e.py` (or the parameter unit case in `test_core.py`).
The proof covers the documented local native subset; it is not exhaustive SQL
or OS qualification.

| Surface | Kind | Executed proof |
| --- | --- | --- |
| `cli-anything-turso` | command/default | `test_default_repl_selection_persistence_and_recovery`, `test_pseudo_tty_repl_smoke` |
| `cli-anything-turso --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso --database` | option | `test_session_override_collision_and_invalid_state`, `test_missing_database_and_parent_never_created` |
| `cli-anything-turso --session` | option | `test_default_repl_selection_persistence_and_recovery`, `test_session_override_collision_and_invalid_state`, `test_session_lock_refusal_is_bounded` |
| `cli-anything-turso --json` | option | `test_crud_binds_escaping_and_null`, `test_sql_failures_are_json`, `test_repl_help_quit_eof_parse_and_nested_paths` |
| `cli-anything-turso --version` | option | `test_all_command_help_and_version` |
| `cli-anything-turso doctor` | command/default | `test_help_and_native_dependency`, `test_missing_sdk_in_separate_environment` |
| `cli-anything-turso doctor --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso status` | command/default | `test_all_command_help_and_version`, `test_session_override_collision_and_invalid_state` |
| `cli-anything-turso status --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso db` | command/default | `test_all_command_help_and_version` |
| `cli-anything-turso db --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso db create` | command/default | `test_database_selection_schema_and_no_overwrite`, `test_missing_database_and_parent_never_created`, `test_session_override_collision_and_invalid_state` |
| `cli-anything-turso db create --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso db create PATH` | argument | `test_database_selection_schema_and_no_overwrite`, `test_missing_database_and_parent_never_created`, `test_session_override_collision_and_invalid_state` |
| `cli-anything-turso db open` | command/default | `test_database_selection_schema_and_no_overwrite`, `test_missing_database_and_parent_never_created` |
| `cli-anything-turso db open --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso db open PATH` | argument | `test_database_selection_schema_and_no_overwrite`, `test_missing_database_and_parent_never_created` |
| `cli-anything-turso db close` | command/default | `test_database_selection_schema_and_no_overwrite` |
| `cli-anything-turso db close --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso sql` | command/default | `test_crud_binds_escaping_and_null`, `test_sql_failures_are_json`, `test_sql_row_cap_and_returning_are_durable` |
| `cli-anything-turso sql --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso sql STATEMENT` | argument | `test_sql_failures_are_json`, `test_sql_row_cap_and_returning_are_durable` |
| `cli-anything-turso sql --params` | option | `test_native_bind_boundaries_and_nonfinite_output`, `test_named_prefixes_missing_binds_and_literal_escaping`, `test_sql_parameter_slots_ignore_literals_and_comments` |
| `cli-anything-turso sql --limit` | option | `test_sql_row_cap_and_returning_are_durable`, `test_invalid_output_limits`, `test_native_bind_boundaries_and_nonfinite_output` |
| `cli-anything-turso schema` | command/default | `test_database_selection_schema_and_no_overwrite` |
| `cli-anything-turso schema --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table` | command/default | `test_all_command_help_and_version` |
| `cli-anything-turso table --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table list` | command/default | `test_database_selection_schema_and_no_overwrite` |
| `cli-anything-turso table list --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table describe` | command/default | `test_database_selection_schema_and_no_overwrite`, `test_session_override_collision_and_invalid_state` |
| `cli-anything-turso table describe --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table describe NAME` | argument | `test_database_selection_schema_and_no_overwrite`, `test_session_override_collision_and_invalid_state` |
| `cli-anything-turso table rows` | command/default | `test_crud_binds_escaping_and_null`, `test_sql_row_cap_and_returning_are_durable`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table rows --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table rows NAME` | argument | `test_crud_binds_escaping_and_null`, `test_sql_row_cap_and_returning_are_durable`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table rows --where` | option | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table rows --limit` | option | `test_sql_row_cap_and_returning_are_durable`, `test_invalid_output_limits`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table insert` | command/default | `test_crud_binds_escaping_and_null`, `test_quoted_table_and_column_names`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table insert --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table insert NAME` | argument | `test_crud_binds_escaping_and_null`, `test_quoted_table_and_column_names`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table insert --values` | option | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table update` | command/default | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table update --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table update NAME` | argument | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table update --values` | option | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table update --where` | option | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table update --all` | option | `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table delete` | command/default | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table delete --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso table delete NAME` | argument | `test_crud_binds_escaping_and_null`, `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso table delete --where` | option | `test_crud_binds_escaping_and_null` |
| `cli-anything-turso table delete --all` | option | `test_actual_all_row_crud_and_filter_validation` |
| `cli-anything-turso transaction` | command/default | `test_all_command_help_and_version` |
| `cli-anything-turso transaction --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso transaction run` | command/default | `test_transaction_commit_and_constraint_rollback`, `test_transaction_commit_failure_and_validation` |
| `cli-anything-turso transaction run --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso transaction run MANIFEST` | argument | `test_transaction_commit_and_constraint_rollback`, `test_transaction_commit_failure_and_validation` |
| `cli-anything-turso export` | command/default | `test_json_and_csv_export_content`, `test_export_truncation_and_invalid_output` |
| `cli-anything-turso export --help` | help | `test_all_command_help_and_version` |
| `cli-anything-turso export NAME` | argument | `test_json_and_csv_export_content`, `test_export_truncation_and_invalid_output` |
| `cli-anything-turso export --output` | option | `test_json_and_csv_export_content`, `test_export_truncation_and_invalid_output` |
| `cli-anything-turso export --format` | option | `test_json_and_csv_export_content`, `test_export_truncation_and_invalid_output` |
| `cli-anything-turso export --limit` | option | `test_export_truncation_and_invalid_output`, `test_invalid_output_limits` |
| `cli-anything-turso repl` | command/default | `test_repl_help_quit_eof_parse_and_nested_paths`, `test_repl_releases_locks_after_success_and_failure` |
| `cli-anything-turso repl --help` | help | `test_all_command_help_and_version` |

## REPL paths

| Path | Executed proof |
| --- | --- |
| No-subcommand pipe, changing database selection, saved session, success/error recovery | `test_default_repl_selection_persistence_and_recovery` |
| Explicit repl, JSON help, quit, EOF, malformed shell quoting, nested repl with/without global flag | `test_repl_help_quit_eof_parse_and_nested_paths` |
| Piped usage error, continued status and sticky nonzero exit | `test_repl_success_and_usage_error` |
| Live REPL releases native locks after success and SQL failure; independent process reopens fixture | `test_repl_releases_locks_after_success_and_failure` |
| Actual pseudo-TTY default REPL, banner/prompt, human status/SQL, malformed SQL, help, recovery, exit/Ctrl-C/Ctrl-D | `test_pseudo_tty_repl_smoke` |

## Artifact and identity proof

Wheel metadata/dependency/entry-point/namespace checks, installed-module identity,
canonical-to-packaged skill equality and installed ReplSkin skill fallback are
recorded with the final wheel and environment receipts. `test_help_and_native_dependency`
checks the native extension identity and can enforce the required installation
root with `CLI_ANYTHING_REQUIRE_INSTALLED_ROOT`. The real tursodb readback test
checks binary `--version` separately from SQL diagnostic version strings.

## Limits

No non-Linux, full SQL grammar, concurrency/MVCC, extension/FTS/vector, crash recovery,
Cloud, libSQL, AgentFS, MCP/sync, managed-writer ownership, deployment, migrations or
backup/restore qualification is claimed. Row caps do not bound cell size or SQL runtime.
Use external query timeouts. Terminal controls are qualified in the tested Linux
pseudo-TTY with prompt synchronization; arbitrary terminal emulators remain unmeasured.
