# TEST.md — Exa CLI Harness Test Plan & Results

## Test Strategy

| Layer | File | API calls | Purpose |
|-------|------|-----------|---------|
| Unit  | test_core.py | None (mocked) | Logic, flag parsing, output formatting |
| E2E   | test_full_e2e.py | Real Exa API | End-to-end correctness, field presence |

## Unit Test Plan (`test_core.py`)

### TestBuildContentsParam
- [x] `none` mode returns `None`
- [x] `highlights` mode sets `max_characters: 4000`
- [x] `text` mode sets `max_characters: 10000`
- [x] `summary` mode sets `summary: True`
- [x] `freshness=always` sets `max_age_hours: 0`
- [x] `freshness=never` sets `max_age_hours: -1`
- [x] `freshness=smart` omits `max_age_hours`

### TestCategorySlugMap
- [x] Hyphenated slugs map correctly to API space-separated values
- [x] Simple slugs pass through unchanged

### TestCLIHelp
- [x] Root `--help` exits 0 and mentions "Exa"
- [x] `search --help` shows all flags
- [x] `contents --help` exits exit code 0
- [x] `server status --help` exits exit code 0

### TestSearchCLI
- [x] Basic search calls `exa.search()` with correct query
- [x] `--json` flag produces parseable JSON with `results` key
- [x] `--type deep` is forwarded to SDK
- [x] `--num-results 5` is forwarded to SDK
- [x] `--include-domains` is forwarded to SDK
- [x] Invalid `--type` value is rejected (exit != 0)

### TestContentsCLI
- [x] Single URL invokes `exa.get_contents()`
- [x] Multiple URLs forwarded as list

### TestServerCLI
- [x] `[OK]` shown on success
- [x] `[ERROR]` shown on failure
- [x] `--json` produces `{"ok": true}`

### TestErrorHandling
- [x] `RuntimeError` from backend produces `{"error": "..."}` in JSON mode
- [x] Missing required argument exits non-zero

## E2E Test Plan (`test_full_e2e.py`)

Skipped automatically when `EXA_API_KEY` is not set.

### TestServerStatusE2E
- [ ] `server status` exits 0 and shows `[OK]`
- [ ] `--json server status` returns `{"ok": true}`

### TestSearchE2E
- [ ] Basic search returns at least 1 result
- [ ] Result objects contain `url` and `title`
- [ ] `--content highlights` produces `highlights` array
- [ ] `--content text` produces non-empty `text` string
- [ ] `--category news` returns results
- [ ] `--include-domains arxiv.org` — all result URLs contain `arxiv.org`
- [ ] `--num-results 5` returns ≤ 5 results
- [ ] Human-readable output contains `http`

### TestContentsE2E
- [ ] `contents <url>` returns results
- [ ] `--content text` result has non-empty `text`
- [ ] Multiple URLs: at least 1 result returned

### TestEntryPoint
- [ ] `cli-anything-exa --help` exits 0 via subprocess
- [ ] `cli-anything-exa --json search ...` returns valid JSON via subprocess

## Running Tests

```bash
# Unit tests only
pytest cli_anything/exa/tests/test_core.py -v

# E2E tests (requires EXA_API_KEY)
EXA_API_KEY=your-key pytest cli_anything/exa/tests/test_full_e2e.py -v

# All tests
pytest cli_anything/exa/tests/ -v
```
