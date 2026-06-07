# CC Switch CLI - Test Plan

## Test Inventory

| Test File | Tests | Type |
|-----------|-------|------|
| `test_core.py` | 46 | Unit tests with synthetic data |
| `test_full_e2e.py` | 20 | E2E tests against a real or configured CC Switch database |

## Unit Test Coverage

### Database and Config Helpers

- `CCSWITCH_HOME` path resolution
- DB, config, and settings path helpers
- SQLite in-memory connection setup
- Config load/save, including empty-file behavior
- Valid app type list

### CLI Core Helpers

- App resolution for valid, invalid, and `None` app values
- Table formatting for normal, empty, and single-row data
- Sensitive-value masking for tokens, API keys, passwords, short secrets, nested dicts, nested lists, authorization headers, and hotkey false positives

### CLI Commands

- Top-level help and command group help
- Explicit `status --json`
- `providers get --json` masking for nested `settings_config`
- Plain `providers get` masking for nested list/header values
- `settings get --json` object output
- `settings get/list/set` masking for sensitive settings
- `sessions list --json` empty-result output
- `mcp list` and `skills list` include OpenClaw state
- `usage stats` normalizes nullable token/cost aggregates
- `providers set-current` DB update plus live Codex config write

### Live Config Write Helpers

- Claude settings JSON env merge
- Codex provider TOML merge preserves unrelated `config.toml` sections plus `auth.json` writes
- Gemini `.env` merge with env key validation and newline escaping
- OpenCode provider merge into `~/.config/opencode/opencode.json`
- Temporary file cleanup after secure writes

## E2E Coverage

### Providers

- List providers
- JSON output
- App filtering
- Nonexistent provider error
- API key leak prevention

### Other Command Groups

- Skills list and repos
- Usage stats and logs
- MCP list
- Settings list
- Proxy status
- Default status overview and JSON overview

## Latest Verification

```powershell
python -m pytest cli_anything\ccswitch\tests -q
..................................................................       [100%]
66 passed in 2.61s
```

Additional checks:

```powershell
git diff --check
python -m compileall -q cli_anything
```

Both checks passed.

## Coverage Notes

- Write operations covered by synthetic tests: `providers set-current`, `settings set`, and live config writes for Claude, Codex, Gemini, and OpenCode.
- Destructive live-database operations and process-control flows should be validated only in a disposable CC Switch environment.
