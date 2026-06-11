# Web Yu-pri Harness SOP

## Purpose

This harness turns Japan Post's Web Yu-pri browser workflow into an
agent-friendly CLI. Web Yu-pri is a logged-in web application, so the CLI drives
the real browser UI through Playwright instead of reimplementing Japan Post
business logic.

## Backend Surface

- Official start URL: `https://mgr.post.japanpost.jp/C30P01Action.do`
- Known contents form URL: `https://mgr.post.japanpost.jp/M060800.do`
- Browser engine: Playwright Chromium with a persistent user profile
- Credentials: never accepted or stored by the CLI; users log in manually in the
  browser profile

## Safety Model

The first version automates repetitive data entry only. It fills item contents,
declared value totals, optional package type, and dangerous-goods flags, but it
does not click the final shipment confirmation/submit button. Agents should use
`--dry-run` before touching the real page, then inspect `verification` in JSON
output after a live fill.

## Commands

- `doctor` checks Playwright availability and profile paths.
- `selectors` prints the known selector map for page diagnostics.
- `plan <items-file>` validates JSON/CSV/TSV item files and computes totals.
- `open-login` opens the Web Yu-pri start URL in the persistent profile.
- `status` opens a URL and reports current title, URL, and selector presence.
- `snapshot` captures a screenshot and optional HTML dump.
- `contents fill <items-file>` fills item rows on the contents form.

## Input Model

The CLI accepts JSON, CSV, or TSV files. Each row supports the following aliases:

- description: `description`, `desc`, `content`, `contents`, `item`, `name`, `pkg`
- value: `value`, `declared_value`, `cost`, `price`, `amount`, `yen`, `jpy`
- quantity: `quantity`, `qty`, `num`, `count`
- country: `country`, `country_code`, `country_of_origin`, `origin`, `couCd`, `cou_cd`
- HS code: `hs_code`, `hs`, `hscode`, `hsCode`

By default, `value` is treated as the line declared value. Use
`--value-mode unit` when `value` is a unit value that should be multiplied by
quantity.

## Known Web Yu-pri Selectors

- Item description: `#M060800_itemBean_pkg`
- Item value: `#M060800_itemBean_cost_value`
- Item quantity: `#M060800_itemBean_num_value`
- Country of origin: `#M060800_itemBean_couCd`
- HS code: `#M060800_itemBean_hsCode`
- Package type: `#M060800_shippingBean_pkgType`
- Total declared value: `#M060800_shippingBean_pkgTotalPrice_value`
- Dangerous-goods flag: `#M060800_ShippingBean_danger`
- Add item command: `submitCommand('itemAdd2')`

## Test Strategy

Unit tests cover item parsing, total computation, selector publication, and dry
run output without launching a browser. The E2E test file includes a real CLI
dry-run workflow and an optional live test gated by `WEB_YU_PRI_LIVE_E2E=1`,
because live execution requires a Japan Post account and a real logged-in
session.
