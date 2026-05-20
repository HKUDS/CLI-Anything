# Tigris CLI — Test Plan

## Layout

- `test_core.py` — unit tests for the `TigrisBackend` wrapper and the Click CLI
  commands. **boto3 is fully mocked** — these tests run without a Tigris account
  or network access, and are safe to run in any CI environment.
- `test_full_e2e.py` — *(not included in MVP)* end-to-end tests against a real
  Tigris account. Requires `TIGRIS_STORAGE_ACCESS_KEY_ID` and
  `TIGRIS_STORAGE_SECRET_ACCESS_KEY` plus a writable test bucket. See "Adding
  e2e tests" below.

## Running unit tests

```bash
cd tigris/agent-harness
pip install -e .[dev]
pytest cli_anything/tigris/tests/test_core.py -v
```

All tests should pass without any Tigris credentials or network access.

## Coverage areas

The unit tests cover:

| Area | Tests |
|------|-------|
| `TigrisBackend.list_buckets` | response shape, ISO date formatting |
| `TigrisBackend.create_bucket` / `delete_bucket` | boto3 args, return shape |
| `TigrisBackend.head_bucket` | endpoint passthrough |
| `TigrisBackend.list_objects` | prefix + limit args, etag quote stripping |
| `TigrisBackend.put_object` | inline bytes + content-type |
| `TigrisBackend.get_object` | body read |
| `TigrisBackend.head_object` | metadata shape |
| `TigrisBackend.copy_object` | CopySource shape |
| `TigrisBackend.presign_get` / `presign_put` | URL passthrough, content-type |
| CLI: `bucket list --json` | exit code + JSON output |
| CLI: `object put` without `--file`/`--text` | error path |
| CLI: `presign get --json` | URL in output |
| URI parsing: `_parse_tigris_uri` | happy path + rejection cases |

## Adding e2e tests

To extend with real-Tigris e2e:

1. Create a test bucket in your Tigris account.
2. Set env vars: `TIGRIS_STORAGE_ACCESS_KEY_ID`, `TIGRIS_STORAGE_SECRET_ACCESS_KEY`,
   `CLI_ANYTHING_TIGRIS_TEST_BUCKET`.
3. Add `test_full_e2e.py` with `@pytest.mark.e2e` markers that put / get / delete
   real objects. Use unique per-run key prefixes (UUIDs) and clean up in
   teardown.
4. Skip e2e tests in CI by default (`@pytest.mark.skipif(not os.getenv("RUN_E2E"))`).

E2e tests are intentionally omitted from the MVP to keep the install / CI path
zero-friction.
