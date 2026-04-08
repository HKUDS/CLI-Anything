# Test Plan — cli-anything-iterm2

## Test Inventory Plan

| File | Tests Planned |
|------|--------------|
| `test_core.py` | 28 unit tests |
| `test_full_e2e.py` | 18 E2E + subprocess tests |

---

## Unit Test Plan (test_core.py)

### Module: `core/session_state.py`

Functions to test: `SessionState`, `load_state`, `save_state`, `clear_state`

| Test | Description |
|------|-------------|
| `test_session_state_defaults` | Default state has all None fields |
| `test_session_state_summary_empty` | Empty state returns "no context set" |
| `test_session_state_summary_partial` | Partial state describes available fields |
| `test_session_state_summary_full` | Full state lists all three IDs |
| `test_session_state_to_dict` | Serializes to expected dict shape |
| `test_session_state_from_dict` | Deserializes correctly |
| `test_session_state_from_dict_missing_keys` | Missing keys use defaults |
| `test_session_state_clear` | Clear sets all fields to None |
| `test_save_and_load_state` | Round-trip save + load |
| `test_save_state_creates_dir` | Creates parent dir if missing |
| `test_load_state_missing_file` | Returns empty state for missing file |
| `test_load_state_invalid_json` | Returns empty state for corrupt JSON |
| `test_clear_state` | Persists empty state to disk |
| `test_save_state_overwrite` | Overwrites existing state |

### Module: `utils/iterm2_backend.py`

Functions to test: `find_iterm2_app`, `require_iterm2_running`, `connection_error_help`

| Test | Description |
|------|-------------|
| `test_find_iterm2_app_present` | Returns path when iTerm2 exists at known location |
| `test_find_iterm2_app_absent` | Raises RuntimeError with install instructions |
| `test_require_iterm2_running_import_error` | Raises RuntimeError if iterm2 not installed |
| `test_connection_error_help_content` | Returns helpful instructions string |

### Module: `core/session.py` (logic only — no live connection)

| Test | Description |
|------|-------------|
| `test_send_text_builds_payload_with_newline` | Default adds \\n to text |
| `test_send_text_no_newline_flag` | --no-newline flag prevents \\n |

### Module: CLI output formatting

| Test | Description |
|------|-------------|
| `test_cli_help` | `--help` exits 0 and mentions groups |
| `test_cli_app_help` | `app --help` shows subcommands |
| `test_cli_window_help` | `window --help` shows subcommands |
| `test_cli_tab_help` | `tab --help` shows subcommands |
| `test_cli_session_help` | `session --help` shows subcommands |
| `test_cli_profile_help` | `profile --help` shows subcommands |
| `test_cli_arrangement_help` | `arrangement --help` shows subcommands |
| `test_json_flag_propagates` | `--json` flag is recognized |

---

## E2E Test Plan (test_full_e2e.py)

**Prerequisite:** iTerm2 must be running with Python API enabled.

### App status workflow

| Test | Description | Verifies |
|------|-------------|---------|
| `test_app_status` | Get iTerm2 app status | Returns window count ≥ 0 |
| `test_app_current` | Get current focused context | Returns window/tab/session IDs |

### Window workflow

| Test | Description | Verifies |
|------|-------------|---------|
| `test_window_create_and_close` | Create window, verify it appears in list, close it | Window ID in list, removed after close |
| `test_window_create_with_profile` | Create window with Default profile | Returns valid window_id |
| `test_window_set_title` | Set window title | No error |
| `test_window_frame` | Get and set window frame | Returns numeric x/y/w/h |

### Tab workflow

| Test | Description | Verifies |
|------|-------------|---------|
| `test_tab_create_and_close` | Create tab in window, close it | tab_id present, removed |
| `test_tab_list` | List tabs | Returns list |

### Session workflow

| Test | Description | Verifies |
|------|-------------|---------|
| `test_session_list` | List all sessions | Returns non-empty list |
| `test_session_send_and_screen` | Send a command, read screen | Output contains sent command or its result |
| `test_session_split_and_close` | Split pane, close new pane | new_session_id returned |

### Profile workflow

| Test | Description | Verifies |
|------|-------------|---------|
| `test_profile_list` | List profiles | Returns ≥ 1 profile |
| `test_color_presets` | List color presets | Returns list of strings |

### Arrangement workflow

| Test | Description | Verifies |
|------|-------------|---------|
| `test_arrangement_save_restore_list` | Save, list, restore arrangement | Name appears in list |

### CLI subprocess tests

Uses `_resolve_cli("cli-anything-iterm2")` — runs installed command as a real user would.

| Test | Description | Verifies |
|------|-------------|---------|
| `test_cli_help` | `cli-anything-iterm2 --help` | exit code 0 |
| `test_cli_json_app_status` | `--json app status` | Valid JSON with window_count |
| `test_cli_json_window_list` | `--json window list` | Valid JSON list |
| `test_cli_json_session_list` | `--json session list` | Valid JSON list |

---

## Realistic Workflow Scenarios

### Workflow 1: Agent workspace setup
**Simulates:** AI agent preparing a multi-pane development workspace

**Operations:**
1. `app current` — discover focused window
2. `window create` — open fresh window
3. `session split --vertical` — create side-by-side panes
4. `session send "cd ~/Developer" --session-id <left>` — navigate in left pane
5. `session send "python3 -m http.server 8000" --session-id <right>` — start server in right
6. `session screen --session-id <right>` — verify server started

**Verified:** Two sessions exist, screen contains server output

### Workflow 2: Automation audit
**Simulates:** Agent reading terminal state without modifying it

**Operations:**
1. `app status` — inventory all windows/tabs/sessions
2. `session screen` — read each session's visible output
3. `session get-var hostname` — check which host each session is on

**Verified:** JSON output for all commands, parseable by agent

### Workflow 3: Layout save/restore
**Simulates:** Saving a working environment and restoring it later

**Operations:**
1. Create 2 windows, each with 2 tabs
2. `arrangement save "dev-env"` — snapshot layout
3. `arrangement list` — verify it appears
4. Close all new windows
5. `arrangement restore "dev-env"` — restore windows

**Verified:** Arrangement name in list, windows restored

---

## Test Results

### Run: Phase 6 (2026-03-22)

**Command:**
```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3.12 -m pytest cli_anything/iterm2_ctl/tests/ -v --tb=no
```

**[_resolve_cli] Using installed command: /opt/homebrew/bin/cli-anything-iterm2**

```
============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/alexanderbass/Developer/iTerm2-master/agent-harness

cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_clear PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_defaults PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_from_dict PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_from_dict_missing_keys PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_summary_empty PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_summary_full PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_summary_partial_tab_only PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_summary_partial_window_only PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStateDefaults::test_to_dict PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStatePersistence::test_clear_state PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStatePersistence::test_load_invalid_json_returns_empty PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStatePersistence::test_load_missing_file_returns_empty PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStatePersistence::test_overwrite_existing_state PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStatePersistence::test_save_and_load_roundtrip PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStatePersistence::test_save_creates_parent_dir PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestSessionStatePersistence::test_saved_file_is_valid_json PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestIterm2Backend::test_connection_error_help_content PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestIterm2Backend::test_find_iterm2_app_absent PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestIterm2Backend::test_find_iterm2_app_present PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestIterm2Backend::test_require_iterm2_running_import_error PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_app_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_arrangement_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_json_flag_in_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_main_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_profile_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_session_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_session_send_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_session_split_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_tab_help PASSED
cli_anything/iterm2_ctl/tests/test_core.py::TestCLIHelp::test_window_help PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestAppStatus::test_app_status PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestAppStatus::test_get_current_context PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestWindowOperations::test_list_windows PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestWindowOperations::test_create_and_close_window PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestWindowOperations::test_window_frame PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestTabOperations::test_list_tabs PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestTabOperations::test_create_and_close_tab PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestSessionOperations::test_list_sessions PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestSessionOperations::test_send_text_and_read_screen PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestSessionOperations::test_split_pane PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestProfileOperations::test_list_profiles PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestProfileOperations::test_list_color_presets PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestArrangementOperations::test_arrangement_save_list_restore PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestCLISubprocess::test_json_app_status PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestCLISubprocess::test_json_window_list PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestCLISubprocess::test_json_session_list PASSED
cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestCLISubprocess::test_json_profile_list PASSED

======================= 48 passed, 17 warnings in 3.22s ========================
```

### Summary

| Metric | Value |
|--------|-------|
| Total tests | 48 |
| Pass rate | 100% (48/48) |
| Execution time | 3.22s |
| Unit tests | 30 (no iTerm2 needed) |
| E2E tests | 18 (live iTerm2 connection) |
| Subprocess tests | 4 (using installed `cli-anything-iterm2`) |

### Run: Phase 6 — After tmux additions (2026-03-22)

**Command:**
```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3.12 -m pytest cli_anything/iterm2_ctl/tests/ -v --tb=short
```

```
==================== 68 passed, 5 skipped, 17 warnings in 3.84s ====================
```

The 5 skipped tests are `TestTmuxOperations` tests that require an active `tmux -CC`
integration session. They are correctly skipped when none is running and will execute
fully when a session is active.

### Summary (after tmux)

| Metric | Value |
|--------|-------|
| Total tests | 73 |
| Passing | 68 |
| Skipped (tmux -CC not running) | 5 |
| Pass rate | 100% of executed tests |
| Execution time | 3.84s |
| Unit tests | 44 (no iTerm2 needed) |
| E2E tests | 29 (live iTerm2 connection) |
| Subprocess tests | 6 (using installed `cli-anything-iterm2`) |

### Coverage Notes

- **All core modules** covered by unit tests: `session_state`, `iterm2_backend`, `tmux` (7 logic tests with mocks), CLI help/structure
- **All command groups** covered by E2E tests: app, window, tab, session, profile, arrangement, tmux
- **Tmux logic tests** cover: empty connection list, unknown ID error, first-connection selection, `list_connections` formatting, `send_command` output, `set_window_visible` argument passing
- **Tmux E2E tests** (skipped without `tmux -CC`): `list-sessions`, `list-windows`, `display-message`, create-window, set-visible roundtrip
- **Subprocess tests** confirm `--json tmux list`, `--json tmux tabs`, `tmux --help`, and `tmux send` error path all work via the installed command
- **Not covered**: `async_inject`, `async_get_selection_text`, broadcast domains — less commonly used operations
- **Warnings**: `iterm2` package uses deprecated `enum.Enum` nested-class pattern (Python 3.12 issue in the pypi package) — no functional impact

### Running tmux tests with an active connection

To run the full tmux test suite, start a `tmux -CC` session in iTerm2:
```bash
tmux -CC          # in an iTerm2 terminal (not a subprocess)
# then in another tab:
CLI_ANYTHING_FORCE_INSTALLED=1 python3.12 -m pytest cli_anything/iterm2_ctl/tests/test_full_e2e.py::TestTmuxOperations -v -s
```

---

### Run: Phase 7 — Full capability expansion (2026-03-22)

**New capabilities added:**
- `broadcast` group: list, set, add, clear, all-panes
- `menu` group: select, state, list-common
- `pref` group: get, set, tmux-get, tmux-set, theme
- `tmux bootstrap` command (start tmux -CC and wait for connection)
- `session get-prompt`, `wait-prompt`, `wait-command-end` (Shell Integration)
- `app get-var`, `app set-var`
- `core/broadcast.py`, `core/menu.py`, `core/pref.py`, `core/prompt.py`

**Command:**
```bash
CLI_ANYTHING_FORCE_INSTALLED=1 python3.12 -m pytest cli_anything/iterm2_ctl/tests/ -v --tb=short
```

```
==================== 104 passed, 5 skipped, 17 warnings in 4.40s ====================
```

**Summary (Phase 7):**

| Metric | Value |
|--------|-------|
| Total tests | 109 |
| Passing | 104 |
| Skipped (tmux -CC not running) | 5 |
| Pass rate | 100% of executed tests |
| Execution time | ~4.4s |
| Unit tests | 80 (no iTerm2 needed) |
| E2E tests | 29 (live iTerm2 connection) |

**New unit test classes:**
- `TestCLIHelp` extended: 20 new help-structure tests for broadcast, menu, pref, tmux bootstrap, session prompt, app vars
- `TestBroadcastCore`: empty domains, clear calls API
- `TestMenuCore`: list_common structure, select_menu_item calls API
- `TestPrefCore`: _parse_value (bool/int/float/str), unknown setting raises
- `TestPromptCore`: None prompt, mock prompt dict, get_last_prompt None, list_prompts empty
- `TestTmuxBootstrap`: timeout raises, no windows raises
