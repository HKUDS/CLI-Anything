# Tigris CLI Harness — Test Plan

## Layout

- `test_core.py` — unit tests for the `TigrisBackend` subprocess wrapper and
  the Click CLI. `subprocess.run` is fully mocked, and `shutil.which` is
  patched at module load so the backend believes `tigris` is on PATH. These
  tests run with **no `tigris` CLI installed and no network access** — safe
  for any CI environment.
- `test_full_e2e.py` — real-world tests that shell out to the actual `tigris`
  CLI against a real bucket. **Skipped by default**; gated on the
  `CLI_ANYTHING_TIGRIS_RUN_E2E` env var plus `tigris` being on PATH plus a
  configured test bucket.

## Running unit tests

```bash
cd tigris/agent-harness
pip install -e .[dev]
pytest cli_anything/tigris/tests/test_core.py -v
```

All tests should pass with no Tigris CLI and no credentials.

## Coverage areas (unit tests)

| Area | Tests |
|------|-------|
| URI/path helpers (`_path_to_t3`, `_parse_tigris_uri`) | scheme normalization, happy + reject paths |
| Backend init | binary resolution via `shutil.which`, missing-binary error, env-var export for credentials |
| Bucket ops | `list/create/delete/head` invoke `tigris buckets …` with correct args + `--format json`; `delete` only passes `--yes` when explicitly requested |
| Object ops | `list` (with prefix + client-side limit), `cp` (with `--recursive`), `put_from_file`, `put_inline` (tempfile path), `delete` (uses `rm --yes`), `head` (uses `stat`) |
| Presign | flags forwarded, URL extracted from JSON dict, fallback parse from raw string |
| Snapshots | `list/take` invoke `tigris snapshots …` |
| Access keys | `list/create/get/delete/assign/rotate` flag wiring; `delete` and `rotate` only pass `--yes` when explicitly requested |
| IAM | `policies list/create`, `users list/invite` flag wiring |
| Error path | non-zero exit code raises `TigrisCliError` with stderr |
| CLI integration | `--json` output works for bucket/object/presign/snapshot/access-key/auth; `object put` without `--file`/`--text` errors; `object cp` with no `t3://` errors |

## Running e2e tests

```bash
# Install + auth
npm install -g @tigrisdata/cli     # or: brew install tigrisdata/tap/tigris
tigris login

# Configure
export CLI_ANYTHING_TIGRIS_TEST_BUCKET=<your-test-bucket>
export CLI_ANYTHING_TIGRIS_RUN_E2E=1

# Run
pytest cli_anything/tigris/tests/test_full_e2e.py -v
```

E2e tests cover:

- `whoami` returns a non-empty session
- `list_buckets` includes the configured test bucket
- put / get / head / list / delete round trip for a single object
- presigned URL is well-formed and includes the key's last segment
- `snapshots list` succeeds against the test bucket

Each test uses a per-run UUID prefix for keys to avoid collisions when
multiple devs / CI runners hit the same bucket. Cleanup happens in
`finally` blocks so partial failures don't leave litter.
