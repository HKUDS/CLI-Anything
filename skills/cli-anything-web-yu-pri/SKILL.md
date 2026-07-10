---
name: "cli-anything-web-yu-pri"
description: Use Japan Post Web Yu-pri from a CLI by driving the real browser UI for login, inspection, screenshots, dry-run planning, and contents-form filling.
---

# Web Yu-pri CLI

Use this skill when a task involves Japan Post Web Yu-pri label entry at
`https://mgr.post.japanpost.jp/C30P01Action.do`, especially repetitive contents
line entry.

## Install

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=web-yu-pri/agent-harness
```

If no browser is found:

```bash
python -m playwright install chromium
```

## Safety Rules

- Do not put Japan Post credentials in commands, files, logs, or prompts.
- Use `open-login` so the user can log in manually in the persistent profile.
- Run `contents fill ... --dry-run --json` before live form filling.
- This CLI does not click final shipment confirmation or purchase buttons.
- Keep item lines separate when the source data has separate award/category
  lines, while preserving the requested declared total.

## Common Commands

```bash
cli-anything-web-yu-pri --json doctor
cli-anything-web-yu-pri open-login
cli-anything-web-yu-pri --json status --url https://mgr.post.japanpost.jp/M060800.do
cli-anything-web-yu-pri --json plan items.json
cli-anything-web-yu-pri --json contents fill items.json --dry-run
cli-anything-web-yu-pri --json contents fill items.json --total-value 17000
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

CSV headers can use these aliases:

- description: `description`, `desc`, `content`, `contents`, `item`, `name`, `pkg`
- value: `value`, `declared_value`, `cost`, `price`, `amount`, `yen`, `jpy`
- quantity: `quantity`, `qty`, `num`, `count`
- country: `country`, `country_code`, `country_of_origin`, `origin`, `couCd`, `cou_cd`
- HS code: `hs_code`, `hs`, `hscode`, `hsCode`

By default, `value` is treated as the line declared value. Use `--value-mode unit`
when value should be multiplied by quantity.

## Selector Diagnostics

```bash
cli-anything-web-yu-pri --json selectors
cli-anything-web-yu-pri snapshot --url https://mgr.post.japanpost.jp/M060800.do -o page.png --html-output page.html
```

Known contents-page controls:

- `#M060800_itemBean_pkg`
- `#M060800_itemBean_cost_value`
- `#M060800_itemBean_num_value`
- `#M060800_itemBean_couCd`
- `#M060800_itemBean_hsCode`
- `#M060800_shippingBean_pkgType`
- `#M060800_shippingBean_pkgTotalPrice_value`
- `#M060800_ShippingBean_danger`
- `submitCommand('itemAdd2')`
