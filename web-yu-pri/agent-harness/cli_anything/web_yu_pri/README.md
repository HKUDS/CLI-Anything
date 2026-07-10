# cli-anything-web-yu-pri

CLI harness for Japan Post Web Yu-pri label workflows.

This CLI drives the real Web Yu-pri browser UI through Playwright. It uses a
persistent local browser profile so you can log in manually once, then run
structured commands for repetitive form entry. It does not store passwords and
does not click final shipment confirmation buttons.

## Install

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=web-yu-pri/agent-harness
```

If Playwright cannot find a browser, install Microsoft Edge or Chrome, or run:

```bash
python -m playwright install chromium
```

## Quick Start

```bash
cli-anything-web-yu-pri doctor
cli-anything-web-yu-pri open-login
cli-anything-web-yu-pri plan items.json --json
cli-anything-web-yu-pri contents fill items.json --dry-run --json
cli-anything-web-yu-pri contents fill items.json --json
```

## Items File

JSON:

```json
{
  "items": [
    {"description": "Award plaque", "value": 8000, "quantity": 1, "country": "KR"},
    {"description": "Certificate", "value": 9000, "quantity": 1, "country": "KR"}
  ]
}
```

CSV:

```csv
description,value,quantity,country,hs_code
Award plaque,8000,1,KR,
Certificate,9000,1,KR,
```

`value` is a line value by default. Add `--value-mode unit` when value should be
multiplied by quantity.

## Commands

| Command | Description |
| --- | --- |
| `doctor` | Check local runtime and profile paths |
| `selectors` | Print the known Web Yu-pri selector map |
| `plan <items-file>` | Validate JSON/CSV/TSV items and compute totals |
| `open-login` | Open the login/start URL in the persistent profile |
| `status` | Inspect title, URL, and selector presence |
| `snapshot -o page.png` | Capture screenshot and optional HTML |
| `contents fill <items-file>` | Fill contents rows and declared total |

## Safety

`contents fill` stops after filling contents and totals. It returns a `safety`
object in JSON output with `final_submit_clicked: false`.
