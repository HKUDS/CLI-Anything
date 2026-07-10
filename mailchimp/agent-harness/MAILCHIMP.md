# MAILCHIMP.md — cli-anything Harness for Mailchimp Marketing API v3.0

## Overview

`cli-anything-mailchimp` makes the [Mailchimp Marketing API v3.0](https://mailchimp.com/developer/marketing/docs/fundamentals/) fully agent-native. Every endpoint from the official Swagger spec is exposed as a typed Click command, with JSON output and REPL mode.

**303 commands across 30 resource groups**, covering the full Marketing API surface.

---

## Backend

| Property | Value |
|---|---|
| API base | `https://<dc>.api.mailchimp.com/3.0` |
| Auth | HTTP Basic — username `anystring`, password = API key |
| Key format | `<random>-<datacenter>` e.g. `abc123-us8` |
| Spec source | `mailchimp/mailchimp-client-lib-codegen` → `spec/marketing.json` (Swagger 2.0) |

**Required env var:**
```bash
export MAILCHIMP_API_KEY=<your-key>-<datacenter>
```
No config files. The data-centre prefix (`us8`, `eu2`, etc.) is derived automatically from the API key suffix.

---

## Command Hierarchy

```
cli-anything-mailchimp [--json] [--version]
│
├── ping            # GET /ping — health check
├── root            # GET /  — account info
│
├── lists           # 66 operations (audiences, members, merge fields, segments, tags, webhooks)
│   ├── list / get / create / update / delete
│   ├── list-lists-id-members / get-lists-id-members-id / create-members / ...
│   ├── list-merge-fields / create-merge-fields / ...
│   ├── list-segments / get-segment-id / create-segments / ...
│   └── list-webhooks / get-webhook-id / create-webhooks / ...
│
├── campaigns       # 22 operations
│   ├── list / get / create / update / delete
│   ├── send / schedule / cancel-send / pause / resume / replicate
│   ├── list-content / list-feedback / get-feedback-id / create-feedback
│   └── list-send-checklist / create-resend
│
├── reports         # 22 operations — sent campaign analytics
│   ├── list / get
│   ├── list-abuse-reports / list-click-details / list-domain-performance
│   ├── list-email-activity / list-locations / list-open-details
│   └── list-sub-reports / list-unsubscribed
│
├── automations     # 18 operations
│   ├── list / get / create / update
│   ├── pause / start / archive
│   └── list-emails / get-email / pause-email / start-email / delete-email
│
├── ecommerce       # 60 operations — stores, orders, products, carts, promo codes
├── templates       # 6 operations
├── template-folders # 5 operations
├── campaign-folders # 5 operations
├── file-manager    # 11 operations — files and folders
├── reporting       # 12 operations — Facebook/landing-page reporting
├── landing-pages   # 8 operations
├── sms-campaigns   # 10 operations
├── surveys         # 3 operations
├── audiences       # 4 operations — connected audience management
├── batch-webhooks  # 5 operations
├── batches         # 4 operations — bulk API batch operations
├── connected-sites # 5 operations
├── contacts        # 4 operations
├── conversations   # 4 operations
├── customer-journeys # 1 operation
├── facebook-ads    # 2 operations
├── verified-domains # 5 operations
├── authorized-apps # 2 operations
├── activity-feed   # 1 operation
├── account-export  # 1 operation
├── account-exports # 2 operations
├── search-campaigns # 1 operation
└── search-members  # 1 operation
```

---

## Output Strategy

All commands share a root `--json` flag:

```bash
cli-anything-mailchimp --json lists list
cli-anything-mailchimp --json campaigns get <campaign_id>
```

**JSON envelopes** (commands emit the native Mailchimp API response):

| Endpoint type | Shape |
|---|---|
| List / collection | Native shape: `{"lists":[...], "total_items":N}` / `{"campaigns":[...]}` etc. — resource key matches the API path noun |
| Single resource GET | Raw Mailchimp response object |
| Mutation (POST/PATCH/PUT) | Raw Mailchimp response object |
| DELETE | `{"ok": true, "message": "Deleted."}` |
| Error | `{"ok": false, "message": "...", "data": <mailchimp-problem-detail>}` |

Use the Mailchimp-native field name when piping to `jq` (e.g. `.lists[]`, `.campaigns[]`, `.members[]`).

Human mode prints compact key-value pairs for single objects and annotated lists for collections.

Collection commands expose Mailchimp's native `count` and `offset` query parameters where the API supports them. The CLI does not auto-fetch every page by default.

---

## Design Decisions

1. **Code generation from spec** — 303 commands are auto-generated from Mailchimp's public Swagger 2.0 spec via `_codegen/generate.py`. Generated files are committed so end-users get fast `--help` without downloading the spec.

2. **Env-var-only auth** — per CLI-Anything convention, no config files. `MAILCHIMP_API_KEY` is the single source of truth.

3. **Verbatim `repl_skin.py`** — the REPL skin is copied unmodified from `cli-anything-plugin/repl_skin.py` as required by CLI-Anything's contribution rules.

4. **Path params as positional args** — Mailchimp path parameters (`{list_id}`, `{campaign_id}`, etc.) become required positional Click arguments, keeping commands concise.

5. **Body as `--data` JSON** — request bodies are passed as `--data '{"key": "value"}'` JSON strings. This avoids generating dozens of per-field flags per command and works naturally for agent use (agents can construct JSON payloads directly).

6. **Subscriber hash utility** — `cli_anything.mailchimp.core.client.subscriber_hash(email)` computes the MD5 hash Mailchimp uses as a member identifier, matching the Node.js reference implementation.

---

## File Layout

```
mailchimp/agent-harness/
├── setup.py
├── MAILCHIMP.md                          ← this file
└── cli_anything/mailchimp/
    ├── __init__.py
    ├── __main__.py
    ├── mailchimp_cli.py                  ← Click root + REPL
    ├── README.md
    ├── core/
    │   ├── client.py                     ← HTTP client, auth, error handling
    │   └── pagination.py                 ← count/offset paginator
    ├── commands/                         ← auto-generated (30 modules)
    │   ├── __init__.py                   ← imports ALL_GROUPS
    │   ├── lists.py                      ← 66 commands
    │   ├── campaigns.py                  ← 22 commands
    │   └── ...                           ← one module per tag
    ├── utils/
    │   ├── output.py                     ← _out() JSON/human switch
    │   └── repl_skin.py                  ← verbatim copy from cli-anything-plugin/repl_skin.py
    ├── _codegen/
    │   └── generate.py                   ← spec → commands/*.py generator
    ├── skills/SKILL.md                   ← packaged skill copy
    └── tests/
        ├── TEST.md
        ├── test_core.py                  ← unit tests (no API key)
        └── test_full_e2e.py              ← 9 live tests (gated on API key)
```
