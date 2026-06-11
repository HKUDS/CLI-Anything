# Test Plan: cli-anything-web-yu-pri

## Test Inventory Plan

- `test_core.py`: 15 unit/CLI smoke tests planned.
- `test_full_e2e.py`: 2 E2E tests planned.

## Unit Test Plan

### `core.items`

- JSON item loading from array and object payloads.
- CSV loading with aliases.
- Value parsing with commas and yen markers.
- Quantity validation.
- Country validation.
- Total computation in `line` and `unit` value modes.
- Declared total mismatch warning.

### `core.browser`

- Selector report returns the known Web Yu-pri form fields.
- Dry-run output includes safety metadata and does not launch a browser.

### CLI

- `--help` exits successfully.
- `plan --json` emits machine-readable totals.
- `contents fill --dry-run --json` emits browser-free dry-run output.

## E2E Test Plan

### Dry-run CLI workflow

Simulates an agent validating a contents file before touching the real site.
Operations:

1. Write a JSON item file.
2. Run `python -m cli_anything.web_yu_pri.web_yu_pri_cli --json contents fill ... --dry-run`.
3. Verify JSON structure, total, selector map, and safety metadata.

### Optional live Web Yu-pri workflow

Live execution requires a Japan Post account and a logged-in profile, so it is
gated by `WEB_YU_PRI_LIVE_E2E=1`. It runs `status` against the contents URL and
verifies the CLI can inspect the real page. Form mutation is intentionally not
part of default CI.

## Test Results

Command:

```bash
python -m pytest cli_anything/web_yu_pri/tests -v
```

Result:

```text
collected 17 items

cli_anything/web_yu_pri/tests/test_core.py::test_parse_item_mapping_aliases PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_parse_item_rejects_bad_country PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_load_json_object_payload PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_load_csv_aliases PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_plan_line_value_mode PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_plan_unit_value_mode PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_plan_warns_declared_total_mismatch PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_selector_report_contains_contents_controls PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_build_dry_run_has_safety_metadata PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_cli_help PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_cli_plan_json PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_cli_plan_missing_file_json PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_cli_contents_fill_dry_run_json PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_cli_contents_fill_missing_file_json PASSED
cli_anything/web_yu_pri/tests/test_core.py::test_cli_open_login_json_defaults_to_no_wait PASSED
cli_anything/web_yu_pri/tests/test_full_e2e.py::test_dry_run_cli_workflow PASSED
cli_anything/web_yu_pri/tests/test_full_e2e.py::test_live_status_against_contents_page SKIPPED

16 passed, 1 skipped
```

Additional checks:

```text
python .github/scripts/validate_root_skills.py
Root skills validation passed.

python -m json.tool registry.json
passed

python -m build
passed

python -m twine check dist/*
PASSED
```

Coverage note: default tests do not log into Japan Post or mutate a real
shipment. The live status test is gated by `WEB_YU_PRI_LIVE_E2E=1` because it
requires a real account and persistent browser profile.
