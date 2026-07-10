---
name: cli-anything-mailchimp
description: CLI harness for the Mailchimp Marketing API v3.0 — 303 commands across 30 resource groups (lists, campaigns, reports, automations, ecommerce, templates, and more). Supports JSON output and interactive REPL mode.
---

# cli-anything-mailchimp

## Identity

An agent-native CLI for the [Mailchimp Marketing API v3.0](https://mailchimp.com/developer/marketing/docs/fundamentals/), built on the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) framework.

## What This CLI Does

- Manage **audiences (lists)** — create, update, delete lists; add/update/archive members; manage merge fields, segments, tags, and webhooks.
- Run **campaigns** — create, schedule, send, pause, replicate, and analyse email campaigns.
- Read **reports** — open rates, click rates, bounce stats, unsubscribes, email activity, geographic data.
- Control **automations** — create and manage automated email workflows.
- Manage **e-commerce** — stores, orders, customers, products, carts, and promo codes.
- Use **templates, file manager, landing pages, SMS campaigns, surveys**, and all other Marketing API resources.

## Prerequisites

- Python 3.10+
- `MAILCHIMP_API_KEY` environment variable set to your API key (including datacenter suffix, e.g. `abc123-us8`)

## Installation

```bash
# From the CLI-Anything repo (once merged):
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=mailchimp/agent-harness

# During development:
cd mailchimp/agent-harness && pip install -e .
```

## Command Reference

### Root

| Command | Description |
|---|---|
| `cli-anything-mailchimp ping` | Health check — confirms API connectivity |
| `cli-anything-mailchimp root list` | Get account info |
| `cli-anything-mailchimp --json <cmd>` | Output any command as JSON |
| `cli-anything-mailchimp` | Launch interactive REPL |

### Lists (Audiences)

| Command | Description |
|---|---|
| `lists list` | List all audiences |
| `lists get <LIST_ID>` | Get audience info |
| `lists create --data '<json>'` | Create audience |
| `lists update <LIST_ID> --data '<json>'` | Update audience |
| `lists delete <LIST_ID>` | Delete audience |
| `lists list-lists-id-members <LIST_ID>` | List members |
| `lists get-lists-id-members-id <LIST_ID> <SUBSCRIBER_HASH>` | Get member by MD5 hash |
| `lists create-lists-id-members <LIST_ID> --data '<json>'` | Add member |
| `lists list-lists-id-merge-fields <LIST_ID>` | List merge fields |
| `lists create-lists-id-merge-fields <LIST_ID> --data '<json>'` | Add merge field |
| `lists list-lists-id-segments <LIST_ID>` | List segments |
| `lists list-list-member-tags <LIST_ID> <SUBSCRIBER_HASH>` | List member tags |
| `lists create-list-member-tags <LIST_ID> <SUBSCRIBER_HASH> --data '<json>'` | Add/remove member tags |
| `lists list-lists-id-webhooks <LIST_ID>` | List webhooks |
| `lists create-lists-id-webhooks <LIST_ID> --data '<json>'` | Add webhook |

### Campaigns

| Command | Description |
|---|---|
| `campaigns list` | List campaigns |
| `campaigns get <CAMPAIGN_ID>` | Get campaign info |
| `campaigns create --data '<json>'` | Create campaign |
| `campaigns update <CAMPAIGN_ID> --data '<json>'` | Update campaign settings |
| `campaigns delete <CAMPAIGN_ID>` | Delete campaign |
| `campaigns send <CAMPAIGN_ID>` | Send campaign immediately |
| `campaigns schedule <CAMPAIGN_ID> --data '<json>'` | Schedule campaign |
| `campaigns cancel-send <CAMPAIGN_ID>` | Cancel scheduled send |
| `campaigns pause <CAMPAIGN_ID>` | Pause RSS campaign |
| `campaigns resume <CAMPAIGN_ID>` | Resume RSS campaign |
| `campaigns replicate <CAMPAIGN_ID>` | Duplicate campaign |
| `campaigns list-content <CAMPAIGN_ID>` | Get campaign content |
| `campaigns list-send-checklist <CAMPAIGN_ID>` | Pre-send checklist |

### Reports

| Command | Description |
|---|---|
| `reports list` | List all campaign reports |
| `reports get <CAMPAIGN_ID>` | Get campaign summary report |
| `reports list-email-activity <CAMPAIGN_ID>` | Per-subscriber open/click activity |
| `reports list-click-details <CAMPAIGN_ID>` | Link click breakdown |
| `reports list-open-details <CAMPAIGN_ID>` | Per-subscriber opens |
| `reports list-unsubscribed <CAMPAIGN_ID>` | Unsubscribers |
| `reports list-locations <CAMPAIGN_ID>` | Geographic breakdown |
| `reports list-domain-performance <CAMPAIGN_ID>` | Per-domain stats |

### Automations

| Command | Description |
|---|---|
| `automations list` | List automations |
| `automations get <WORKFLOW_ID>` | Get automation info |
| `automations create --data '<json>'` | Create automation |
| `automations pause <WORKFLOW_ID>` | Pause automation |
| `automations start <WORKFLOW_ID>` | Start automation |
| `automations archive <WORKFLOW_ID>` | Archive automation |
| `automations list-emails <WORKFLOW_ID>` | List automation emails |

### E-commerce

| Command | Description |
|---|---|
| `ecommerce list-ecommerce-stores` | List stores |
| `ecommerce get <STORE_ID>` | Get store info |
| `ecommerce create --data '<json>'` | Add store |
| `ecommerce list-ecommerce-stores-id-orders <STORE_ID>` | List orders |
| `ecommerce list-ecommerce-stores-id-products <STORE_ID>` | List products |
| `ecommerce list-ecommerce-stores-id-customers <STORE_ID>` | List customers |
| `ecommerce list-ecommerce-stores-id-carts <STORE_ID>` | List carts |
| `ecommerce list-ecommerce-stores-id-promocodes <PROMO_RULE_ID> <STORE_ID>` | List promo codes |

### Other Resources

| Group | Description |
|---|---|
| `templates` | Email templates (list, get, create, update, delete) |
| `template-folders` | Template folders |
| `campaign-folders` | Campaign folders |
| `file-manager` | Files and folders in the file manager |
| `landing-pages` | Landing pages (list, create, publish, unpublish) |
| `sms-campaigns` | SMS campaigns (10 operations) |
| `surveys` | Surveys (list, get, publish) |
| `reporting` | Facebook ad and landing page reporting |
| `search-campaigns` | Search campaigns by query |
| `search-members` | Search members across all audiences |
| `batches` | Batch API operations |
| `batch-webhooks` | Batch operation webhooks |
| `verified-domains` | Email domain verification |
| `authorized-apps` | OAuth connected apps |
| `connected-sites` | Connected site integrations |
| `conversations` | Inbox conversations |
| `activity-feed` | Account activity feed |
| `account-exports` | Account data exports |

## JSON Output

All commands support `--json` at the root level:

```bash
# List all audiences as JSON
cli-anything-mailchimp --json lists list

# Get a campaign report as JSON
cli-anything-mailchimp --json reports get abc123def

# Pipe to jq — use the native Mailchimp field name for the resource
cli-anything-mailchimp --json lists list | jq '.lists[].name'
cli-anything-mailchimp --json campaigns list | jq '.campaigns[].id'
```

**Envelope shapes** (native Mailchimp API response — use the resource-specific key):

```json
// List endpoints — key matches the resource name (lists, campaigns, members, etc.)
{"lists": [...], "total_items": 42, "_links": [...]}
{"campaigns": [...], "total_items": 10, "_links": [...]}

// Single resource GET / POST / PATCH
{"id": "abc123", "name": "My List", ...}

// DELETE
{"ok": true, "message": "Deleted."}

// Error
{"ok": false, "message": "Resource Not Found: ...", "data": {...}}
```

## Common Agent Patterns

```bash
# Get account health
cli-anything-mailchimp --json ping | jq '.health_status'

# List all audience IDs and names
cli-anything-mailchimp --json lists list | jq '.lists[] | {id, name}'

# Find all subscribed members in an audience
cli-anything-mailchimp --json lists list-lists-id-members <list_id> --status subscribed | jq '.members[].email_address'

# Create a campaign and get its send checklist
cli-anything-mailchimp --json campaigns create --data '{"type":"regular","settings":{"subject_line":"Hello","from_name":"Me","reply_to":"me@example.com"}}' | jq '.id'
cli-anything-mailchimp --json campaigns list-send-checklist <campaign_id> | jq '.items[] | select(.result == false)'

# Get unsubscribes for a sent campaign
cli-anything-mailchimp --json reports list-unsubscribed <campaign_id> | jq '.unsubscribes[].email_address'

# Add a member to an audience (subscriber hash = MD5 of lowercased email)
cli-anything-mailchimp --json lists create-members <list_id> --data '{"email_address":"user@example.com","status":"subscribed"}'

# Search for a member across all audiences
cli-anything-mailchimp --json search-members list --query "user@example.com" | jq '.exact_matches.members[]'
```

## Interactive REPL

Run `cli-anything-mailchimp` with no arguments to enter the REPL:

```
◆  cli-anything · Mailchimp
   v0.1.0
   Type help for commands, quit to exit

◆ mailchimp ❯ ping
  ✓ {"health_status": "Everything's Chimpy!"}

◆ mailchimp ❯ --json lists list
{"lists": [...], "total_items": 3, "_links": [...]}

◆ mailchimp ❯ quit
```

## Notes

- **Subscriber hash**: Mailchimp identifies members by the MD5 hash of their lowercased email. Compute with `python -c "import hashlib; email='email@example.com'; print(hashlib.md5(email.strip().lower().encode()).hexdigest())"`.
- **Body payloads**: All POST/PATCH/PUT commands accept `--data '<json>'`. See [Mailchimp API docs](https://mailchimp.com/developer/marketing/api/) for the schema of each endpoint.
- **Datacenter**: Your API key ends in `-us8`, `-eu2`, etc. The CLI extracts this automatically — include it in `MAILCHIMP_API_KEY`.
- **Rate limits**: The Marketing API rate-limits at 10 concurrent connections and a rolling per-account limit. For bulk operations, use the `batches` group.
