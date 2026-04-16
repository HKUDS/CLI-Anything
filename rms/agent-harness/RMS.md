# RMS — Teltonika Remote Management System CLI Harness

## Architecture

This harness wraps the Teltonika RMS REST API (v3-BETA) to provide a CLI
for device management, monitoring, alerting, and administration.

**Backend**: REST API at `https://api.rms.teltonika-networks.com`
**Auth**: Bearer token (Personal Access Token) via `Authorization: Bearer <token>` header
**Response format**: `{"success": bool, "data": ..., "errors": [...], "meta": {"total": N}}`

## Prerequisites

- Teltonika RMS account with 2FA enabled
- Personal Access Token (PAT) created in account settings
- Token set as `RMS_API_TOKEN` env var or via `cli-anything-rms config set api_token <token>`

## Resource Map

| Resource | API Path | CLI Group | Operations |
|----------|----------|-----------|------------|
| Devices | /devices | `devices` | list, get, update, delete |
| Companies | /companies | `companies` | list, get, create, update, delete |
| Users | /users | `users` | list, get, invite, update, delete |
| Tags | /tags | `tags` | list, get, create, update, delete |
| Device Alerts | /device_alerts | `alerts` | list, get, delete |
| Alert Configurations | /device_alert_configurations | `alerts configs` | list, get, create, update, delete |
| Device Configurations | /device_configurations | `configs` | list, get, update |
| Remote Access | /device_remote_access | `remote-access` | list, get, create, delete |
| Device Logs | /device_logs | `logs` | list, get, delete |
| Device Location | /device_location | `location` | get, history |
| Credits | /credits | `credits` | list, transfer |
| Credit Transfer Codes | /credit_transfer_codes | `credits codes` | list |
| Files | /files | `files` | list, get, upload, delete |
| Reports | /reports | `reports` | list, get, create, delete |
| Report Templates | /report_templates | `reports templates` | list, get, create, update, delete |
| Device Hotspots | /device_hotspots | `hotspots` | list, get, create, update, delete |
| Device Passwords | /device_passwords | `passwords` | get, update |
| SMTP Configurations | /smtp_configurations | `smtp` | list, get, create, update, delete |

## API Conventions

- **Pagination**: `offset` + `limit` query parameters; `meta.total` in response
- **Filtering**: Resource-specific params (e.g., `status`, `tag` for devices)
- **Sorting**: `sort` param with field name, prefix `-` for descending
- **Timestamps**: `Y-m-d H:i:s` format, UTC timezone
- **Rate limit**: 100,000 requests/month per Client ID; HTTP 429 when exceeded

## Session State

Stored at `~/.cli-anything-rms/session.json`:
- `last_device_id`: Last accessed device for convenience
- `history`: Command history (max 50 entries)
- `preferences`: Default limit, sort order

## Testing

- `test_core.py`: Unit tests with mocked API responses (no RMS account needed)
- `test_full_e2e.py`: E2E tests requiring valid `RMS_API_TOKEN`
