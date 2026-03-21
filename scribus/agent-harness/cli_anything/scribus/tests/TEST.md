# Scribus CLI - Test Documentation

## Unit Tests (test_core.py)

- TestSession: create, set_project, undo/redo, status, save, history
- TestDocument: create_document, get_file_info, list_pages, list_layers, list_fonts, error handling

## E2E Tests (test_full_e2e.py)

- TestCLISubprocess: --help, create document, info, page list, font-list
