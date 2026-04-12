# ChromaDB CLI Tests

## Test Plan

### Unit Tests (`test_core.py`) -- 38 tests, mocked HTTP

- [x] Backend URL construction (default, custom, trailing slash)
- [x] Tenant/database prefix generation
- [x] Session headers (Content-Type)
- [x] Heartbeat URL and response parsing
- [x] Version URL and response parsing
- [x] Collection list URL and response parsing
- [x] Collection create request body (with/without metadata)
- [x] Collection get URL construction
- [x] Collection delete returns True
- [x] Document add request body (with/without metadatas)
- [x] Document get URL and limit/offset params
- [x] Document delete request body
- [x] Document count URL and return value
- [x] Query request body and default n_results
- [x] Query URL construction
- [x] Error handling: ConnectionError on heartbeat/version
- [x] Error handling: HTTPError on list_collections
- [x] Error handling: 404 on get_collection
- [x] CLI --help flag
- [x] CLI server/collection/document/query --help subcommands
- [x] JSON output formatting for heartbeat, version, collection list
- [x] Human output mode for heartbeat
- [x] JSON error output on server failure
- [x] Custom --host flag acceptance

### E2E Tests (`test_full_e2e.py`) -- 14 tests, real ChromaDB at localhost:8000

- [x] `cli-anything-chromadb --help` returns exit code 0
- [x] `server --help` lists subcommands
- [x] Unknown command returns non-zero exit code
- [x] `--json server heartbeat` returns valid JSON with heartbeat data
- [x] `--json server version` returns valid JSON with version string
- [x] `server heartbeat` (human mode) exits 0
- [x] `--json collection list` returns valid JSON array
- [x] Collection list entries contain name field
- [x] `--json collection info hub_knowledge` returns info (skipped if not present)
- [x] `collection info` for nonexistent collection returns error
- [x] JSON output from heartbeat is parseable
- [x] JSON output from version is parseable
- [x] JSON output from collection list is parseable
- [x] Error output in JSON mode is parseable

## Test Results

```
Run date: 2026-03-23
Python: 3.14.3
pytest: 9.0.2
Platform: Darwin (macOS)

======================== 51 passed, 1 skipped in 1.69s =========================

Skipped:
  - test_collection_info_hub_knowledge: hub_knowledge collection not present on test server
```

## Running Tests

```bash
cd agent-harness
pip install -e .

# Run all tests
python -m pytest cli_anything/chromadb/tests/ -v --tb=short

# Run only unit tests (no external deps)
python -m pytest cli_anything/chromadb/tests/test_core.py -v

# Run only E2E tests (requires ChromaDB at localhost:8000)
python -m pytest cli_anything/chromadb/tests/test_full_e2e.py -v
```
