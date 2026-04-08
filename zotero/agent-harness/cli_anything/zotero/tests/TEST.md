# Zotero CLI Harness - Test Documentation

## Test Inventory

| File | Focus | Coverage |
|---|---|---|
| `test_core.py` | Path discovery, SQLite inspection, library-aware resolution, note/context/analyze helpers, experimental SQLite writes | Unit + mocked HTTP |
| `test_cli_entrypoint.py` | CLI help, REPL entry, subprocess behavior, fake connector/Local API/OpenAI flows, group-library routing | Installed/subprocess behavior |
| `test_agent_harness.py` | Packaging, harness structure, skill generation | Packaging integrity |
| `test_full_e2e.py` | Real Zotero runtime, safe read workflows, opt-in write flows | Live validation |

## Unit Test Plan

### Path Discovery

- resolve profile root from explicit path and environment
- parse `profiles.ini`
- parse `prefs.js` and `user.js`
- resolve custom `extensions.zotero.dataDir`
- fall back to `~/Zotero`
- resolve executable and version
- detect Local API pref state

### SQLite Inspection

- libraries
- collections and collection tree
- title search and collection search
- items, notes, attachments, and annotations
- item fields, creators, and tags
- saved searches and conditions
- tag-linked item lookup
- attachment real-path resolution
- duplicate key resolution across user and group libraries

### Context, Notes, and Analysis

- `item find` Local API preference and SQLite fallback
- group-library Local API scope selection
- `item notes` and `note get`
- `note add` payload construction for text and markdown
- `item context` aggregation of links, notes, and exports
- `item analyze` OpenAI request path and missing API key errors

### Experimental SQLite Writes

- `collection create`
- `item add-to-collection`
- `item move-to-collection`
- backup creation
- transaction commit/rollback behavior
- Zotero-running guard
- local user-library-only restriction

### Import Core

- `app enable-local-api` idempotency
- connector-required guard for write commands
- `import file` raw-text handoff
- `import json` parsing and validation
- inline `attachments` extraction and stripping for `import json`
- `--attachments-manifest` parsing and index/title validation for `import file`
- local-file and URL PDF validation, including magic-byte acceptance when `Content-Type` is wrong
- partial-success attachment reporting and non-zero exit semantics
- duplicate attachment skipping within the same import request
- session-target fallback chain
- repeatable tag propagation to `updateSession`

## CLI / Subprocess Plan

- root `--help`
- default REPL entry
- REPL help text
- `app status --json`
- `app enable-local-api --json`
- `collection list/find --json`
- `item get/find/notes/context --json`
- `note get/add --json`
- `item analyze --json` against a fake OpenAI-compatible endpoint
- group-library `item find/export/citation/bibliography/search items` routing
- `session use-library L<id>` normalization
- force-installed subprocess resolution via `CLI_ANYTHING_FORCE_INSTALLED=1`
- `import json` with inline local and URL PDF attachments
- `import file` with `--attachments-manifest`
- partial-success import attachment failures returning non-zero
- experimental collection write commands against an isolated SQLite copy

## Live E2E Plan

### Non-Mutating

- `app ping`
- `collection use-selected`
- `collection tree/get/items`
- `item list/get/find/attachments/file`
- `item notes`
- `note get`
- `tag list/items`
- `search list/get/items` when saved searches exist
- `session use-collection/use-item`
- `style list`
- `item context`
- `item citation`
- `item bibliography`
- `item export --format ris|bibtex|csljson`

### Mutating

- `import file`
- `import json`
- `import json` with inline local PDF attachment
- `note add`

These write tests are opt-in only and require:

- `CLI_ANYTHING_ZOTERO_ENABLE_WRITE_E2E=1`
- `CLI_ANYTHING_ZOTERO_IMPORT_TARGET=<collection-key-or-id>`

Experimental SQLite write commands are intentionally **not** executed against the
real Zotero library. They are tested only against isolated SQLite copies.

## Test Results

Validation completed on 2026-03-27.

### Machine / Runtime

- OS: Windows
- Python: 3.13.5
- Zotero executable: `C:\Program Files\Zotero\zotero.exe`
- Zotero version: `7.0.32`
- Active profile: `C:\Users\Lenovo\AppData\Roaming\Zotero\Zotero\Profiles\38ay0ldk.default`
- Active data dir: `D:\Study\科研\论文`
- HTTP port: `23119`
- Local API state during validation: enabled and available

### Product Validation Commands

```powershell
py -m pip install -e .
py -m pytest cli_anything/zotero/tests/test_core.py -v
py -m pytest cli_anything/zotero/tests/test_cli_entrypoint.py -v
py -m pytest cli_anything/zotero/tests/test_agent_harness.py -v
py -m pytest cli_anything/zotero/tests/test_full_e2e.py -v -s
py -m pytest cli_anything/zotero/tests/ -v --tb=no

$env:CLI_ANYTHING_FORCE_INSTALLED=1
py -m pytest cli_anything/zotero/tests/test_cli_entrypoint.py -v
py -m pytest cli_anything/zotero/tests/test_full_e2e.py -v -s

cli-anything-zotero --json app status
cli-anything-zotero --json collection find "具身"
cli-anything-zotero --json item find "embodied intelligence" --limit 5
cli-anything-zotero --json item context PB98EI9N --include-links
cli-anything-zotero --json note get <note-key>
```

### Real Zotero Results

- `app status --json` reported:
  - `connector_available: true`
  - `local_api_available: true`
  - `local_api_enabled_configured: true`
- `collection use-selected --json` returned the live GUI selection from the running Zotero window
- `item find` succeeded on a live library item through the Local API search path
- `item context` produced structured item metadata and prompt-ready text on a real library item
- `item notes` and `note get` succeeded when a real item with child notes was available
- `item citation`, `item bibliography`, and `item export` all succeeded on a real regular item
- export validation succeeded:
  - RIS contained `TY  -`
  - BibTeX contained `@`
  - CSL JSON parsed successfully

### Write-Test Policy Result

- mocked connector write-path tests for `import file`, `import json`, import-time PDF attachments, and `note add` passed
- subprocess tests for the same write paths, including inline and manifest attachment flows, passed against fake local services
- mocked group-library Local API routing passed for `item find`, `item export`, `item citation`, `item bibliography`, and `search items`
- installed-command subprocess checks passed with `CLI_ANYTHING_FORCE_INSTALLED=1`
- real write-import, live import-with-attachment, and live note-add E2E remain opt-in by default
- experimental SQLite write commands were validated only on isolated local SQLite copies

### Pytest Results

```text
py -m pytest cli_anything/zotero/tests/ -v --tb=no

============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-8.4.2, pluggy-1.6.0 -- C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Lenovo\Desktop\CLI-Anything\zotero\agent-harness
configfile: pyproject.toml
plugins: anyio-4.9.0
collecting ... collected 82 items

cli_anything/zotero/tests/test_agent_harness.py::AgentHarnessPackagingTests::test_required_files_exist PASSED [  1%]
cli_anything/zotero/tests/test_agent_harness.py::AgentHarnessPackagingTests::test_setup_reports_expected_name PASSED [  2%]
cli_anything/zotero/tests/test_agent_harness.py::AgentHarnessPackagingTests::test_setup_reports_expected_version PASSED [  3%]
cli_anything/zotero/tests/test_agent_harness.py::AgentHarnessPackagingTests::test_skill_generator_regenerates_skill PASSED [  4%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_app_enable_local_api_json PASSED [  6%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_app_status_json PASSED [  7%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_collection_find_json PASSED [  8%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_collection_list_json PASSED [  9%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_default_entrypoint_starts_repl PASSED [ 10%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_dispatch_uses_requested_prog_name PASSED [ 12%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_experimental_collection_write_commands PASSED [ 13%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_force_installed_mode_requires_real_command PASSED [ 14%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_group_library_routes_use_group_scope PASSED [ 15%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_help_renders_groups PASSED [ 17%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_import_file_subprocess PASSED [ 18%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_import_file_subprocess_with_attachment_manifest PASSED [ 19%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_import_json_subprocess PASSED [ 20%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_import_json_subprocess_duplicate_attachment_is_idempotent PASSED [ 21%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_import_json_subprocess_partial_success_returns_nonzero PASSED [ 23%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_import_json_subprocess_with_inline_file_attachment PASSED [ 24%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_import_json_subprocess_with_url_attachment PASSED [ 25%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_item_context_and_analyze PASSED [ 26%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_item_find_and_notes_json PASSED [ 28%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_item_get_json PASSED [ 29%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_note_get_and_add PASSED [ 30%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_repl_help_text_mentions_builtins PASSED [ 31%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_session_status_json PASSED [ 32%]
cli_anything/zotero/tests/test_cli_entrypoint.py::CliEntrypointTests::test_session_use_library_normalizes_tree_view_library_ref PASSED [ 34%]
cli_anything/zotero/tests/test_core.py::PathDiscoveryTests::test_build_environment_accepts_env_profile_dir_pointing_to_profile PASSED [ 35%]
cli_anything/zotero/tests/test_core.py::PathDiscoveryTests::test_build_environment_falls_back_to_home_zotero PASSED [ 36%]
cli_anything/zotero/tests/test_core.py::PathDiscoveryTests::test_build_environment_uses_active_profile_and_data_dir_pref PASSED [ 37%]
cli_anything/zotero/tests/test_core.py::PathDiscoveryTests::test_ensure_local_api_enabled_writes_user_js PASSED [ 39%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_cross_library_unique_key_still_resolves_without_session_context PASSED [ 40%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_duplicate_key_resolution_requires_library_context PASSED [ 41%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_experimental_sqlite_write_helpers PASSED [ 42%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_fetch_collections_and_tree PASSED [ 43%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_fetch_item_children_and_attachments PASSED [ 45%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_fetch_libraries PASSED [ 46%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_fetch_saved_searches_and_tags PASSED [ 47%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_find_collections_and_items_and_notes PASSED [ 48%]
cli_anything/zotero/tests/test_core.py::SQLiteInspectionTests::test_resolve_item_includes_fields_creators_tags PASSED [ 50%]
cli_anything/zotero/tests/test_core.py::SessionTests::test_expand_repl_aliases PASSED [ 51%]
cli_anything/zotero/tests/test_core.py::SessionTests::test_normalize_library_ref_accepts_plain_and_tree_view_ids PASSED [ 52%]
cli_anything/zotero/tests/test_core.py::SessionTests::test_save_and_load_session_state PASSED [ 53%]
cli_anything/zotero/tests/test_core.py::HttpUtilityTests::test_build_runtime_context_reports_unavailable_services PASSED [ 54%]
cli_anything/zotero/tests/test_core.py::HttpUtilityTests::test_catalog_style_list_parses_csl PASSED [ 56%]
cli_anything/zotero/tests/test_core.py::HttpUtilityTests::test_wait_for_endpoint_requires_explicit_ready_status PASSED [ 57%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_enable_local_api_reports_idempotent_state PASSED [ 58%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_file_manifest_index_out_of_range_and_missing_connector_id_fail_cleanly PASSED [ 59%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_file_manifest_partial_success_records_attachment_failures PASSED [ 60%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_file_manifest_title_mismatch_marks_attachment_failure PASSED [ 62%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_file_posts_raw_text_and_explicit_tree_view_target PASSED [ 63%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_json_duplicate_inline_attachments_are_skipped PASSED [ 64%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_json_rejects_invalid_inline_attachment_schema PASSED [ 65%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_json_rejects_invalid_json PASSED [ 67%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_json_strips_inline_attachments_and_uploads_local_pdf PASSED [ 68%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_json_url_attachment_uses_delay_and_default_timeout PASSED [ 69%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_json_uses_session_collection_and_tags PASSED [ 70%]
cli_anything/zotero/tests/test_core.py::ImportCoreTests::test_import_requires_connector PASSED [ 71%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_collection_find_and_item_find_sqlite_fallback PASSED [ 73%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_collection_scoped_item_find_prefers_local_api PASSED [ 74%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_experimental_commands_require_closed_zotero_and_update_db_copy PASSED [ 75%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_group_library_local_api_scope_and_search_routes PASSED [ 76%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_item_analyze_requires_api_key_and_uses_openai PASSED [ 78%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_item_context_aggregates_exports_and_links PASSED [ 79%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_item_notes_and_note_get PASSED [ 80%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_note_add_builds_child_note_payload PASSED [ 81%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_rendering_uses_group_library_local_api_scope PASSED [ 82%]
cli_anything/zotero/tests/test_core.py::OpenAIUtilityTests::test_extract_text_from_response_payload PASSED [ 84%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_attachment_inventory_commands PASSED [ 85%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_collection_detail_commands PASSED [ 86%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_collection_use_selected PASSED [ 87%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_connector_ping PASSED [ 89%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_item_citation_bibliography_and_exports PASSED [ 90%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_item_find_and_context_commands PASSED [ 91%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_note_inventory_commands PASSED [ 92%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_opt_in_import_json_with_inline_attachment SKIPPED [ 93%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_opt_in_note_add_command SKIPPED [ 95%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_opt_in_write_import_commands SKIPPED [ 96%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_search_detail_commands SKIPPED [ 97%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_sqlite_inventory_commands PASSED [ 98%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_tag_and_session_commands PASSED [100%]

================== 78 passed, 4 skipped in 108.48s (0:01:48) ==================
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_item_notes_and_note_get PASSED [ 78%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_note_add_builds_child_note_payload PASSED [ 79%]
cli_anything/zotero/tests/test_core.py::WorkflowCoreTests::test_rendering_uses_group_library_local_api_scope PASSED [ 81%]
cli_anything/zotero/tests/test_core.py::OpenAIUtilityTests::test_extract_text_from_response_payload PASSED [ 82%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_attachment_inventory_commands PASSED [ 84%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_collection_detail_commands PASSED [ 85%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_collection_use_selected PASSED [ 86%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_connector_ping PASSED [ 88%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_item_citation_bibliography_and_exports PASSED [ 89%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_item_find_and_context_commands PASSED [ 91%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_note_inventory_commands PASSED [ 92%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_opt_in_note_add_command SKIPPED [ 94%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_opt_in_write_import_commands SKIPPED [ 95%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_search_detail_commands SKIPPED [ 97%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_sqlite_inventory_commands PASSED [ 98%]
cli_anything/zotero/tests/test_full_e2e.py::ZoteroFullE2E::test_tag_and_session_commands PASSED [100%]

================== 66 passed, 3 skipped in 87.81s (0:01:27) ===================
```

### Notes

- SQLite inspection uses a read-only immutable connection so local reads continue to work while Zotero is open.
- bare key lookup is library-aware: unique keys resolve automatically, while duplicate keys require `session use-library <id>`.
- stable Local API read/export routes are validated for both `/api/users/0/...` and `/api/groups/<libraryID>/...`.
- experimental collection write commands require Zotero to be closed, require `--experimental`, and create a timestamped backup before each write.
- `item context` is the recommended model-independent AI interface.
- `item analyze` is covered by mocked OpenAI-compatible subprocess tests, not by live external API calls.
