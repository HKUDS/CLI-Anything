# Darktable CLI - Test Documentation

## Unit Tests (test_core.py)

- TestSession: create, set_project, undo/redo, status, save, history
- TestProcess: list_styles, get_file_info error handling
- TestExport: list_presets, get_preset_info, preset validation

## E2E Tests (test_full_e2e.py)

- TestCLISubprocess: --help, export-presets list
