# Changelog

## [1.1.0] - 2026-03-31

### Changed
- **BREAKING**: Removed `credential list` and `credential update` commands (not supported by n8n Public API v1.1.1)
- **BREAKING**: Removed `execution stop` command (not in public API)
- **BREAKING**: Removed `table` command group (Data Tables not in public API v1.1.1)
- Aligned all endpoints with verified n8n OpenAPI spec v1.1.1
- Version bumped to 1.1.0

### Added
- `workflow set-tags` command to update workflow tags
- `workflow transfer` command to transfer workflows between projects
- `credential transfer` command to transfer credentials between projects
- URL validation in `config set base_url`
- Configurable timeout via `N8N_TIMEOUT` env var (default: 30s)
- Ellipsis indicator when table columns are truncated
- Better JSON error messages (`@file.json` not found, invalid JSON)

### Fixed
- `credential list` no longer crashes with 405 (command removed — API doesn't support it)
- `_load_json_arg` now shows clear error for missing files and invalid JSON
- API key is always masked in `config show`, even with `--json`

### Removed
- `setup.py` (replaced by `pyproject.toml`)
- `core/session.py` (unused REPL state dataclass)
- `core/tables.py` (Data Tables not in n8n Public API)
- `execution stop/stop-all` (not in public API)
- `execution tags/set-tags` (not in public API)

## [1.0.0] - 2026-03-31

### Added
- Initial release
- CLI harness following CLI-Anything pattern
- Workflow management (list, get, create, update, delete, activate, deactivate, tags)
- Execution management (list, get, delete, retry)
- Credential management (create, delete, schema)
- Variable management (CRUD)
- Tag management (CRUD)
- Interactive REPL mode with colored output
- JSON output mode (`--json`)
- Config persistence (`~/.cli-anything/n8n/config.json`)
- 29 unit tests, E2E test suite
