---
name: >-
  cli-anything-rms
description: >-
  Teltonika RMS device management and monitoring CLI
---

# cli-anything-rms

CLI harness for Teltonika RMS (Remote Management System). Manage routers, gateways, and IoT devices via the RMS REST API.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=rms/agent-harness
```

## Authentication

Set `RMS_API_TOKEN` environment variable or run `cli-anything-rms config set api_token <token>`.

## Command Groups

### devices
- `devices list [--status online|offline] [--tag TAG] [--limit N] [--offset N] [--sort FIELD]` — List devices
- `devices get <device_id>` — Get device details
- `devices update <device_id> [--name NAME] [--tag TAG]` — Update device
- `devices delete <device_id>` — Delete device

### companies
- `companies list [--limit N] [--offset N]` — List companies
- `companies get <company_id>` — Get company details
- `companies create --name NAME` — Create company
- `companies update <company_id> [--name NAME]` — Update company
- `companies delete <company_id>` — Delete company

### users
- `users list [--limit N] [--offset N]` — List users
- `users get <user_id>` — Get user details
- `users invite --email EMAIL [--role ROLE]` — Invite user
- `users update <user_id> [--role ROLE]` — Update user
- `users delete <user_id>` — Delete user

### tags
- `tags list [--limit N] [--offset N]` — List tags
- `tags get <tag_id>` — Get tag details
- `tags create --name NAME` — Create tag
- `tags update <tag_id> [--name NAME]` — Update tag
- `tags delete <tag_id>` — Delete tag

### alerts
- `alerts list [--device DEVICE_ID] [--limit N] [--offset N]` — List alerts
- `alerts get <alert_id>` — Get alert details
- `alerts delete <alert_id>` — Delete alert
- `alerts configs list` — List alert configurations
- `alerts configs get <config_id>` — Get alert config
- `alerts configs create --data JSON` — Create alert config
- `alerts configs update <config_id> --data JSON` — Update alert config
- `alerts configs delete <config_id>` — Delete alert config

### configs
- `configs list [--device DEVICE_ID] [--limit N] [--offset N]` — List device configurations
- `configs get <config_id>` — Get configuration
- `configs update <config_id> --data JSON` — Update configuration

### remote-access
- `remote-access list [--device DEVICE_ID] [--limit N]` — List sessions
- `remote-access get <session_id>` — Get session details
- `remote-access create --device DEVICE_ID [--protocol PROTO] [--port PORT]` — Create session
- `remote-access delete <session_id>` — Delete session

### logs
- `logs list [--device DEVICE_ID] [--limit N] [--offset N]` — List logs
- `logs get <log_id>` — Get log details
- `logs delete <log_id>` — Delete log

### location
- `location get <device_id>` — Get current device location
- `location history <device_id> [--limit N] [--offset N]` — Location history

### credits
- `credits list [--limit N] [--offset N]` — List credits
- `credits transfer --code CODE` — Transfer credits
- `credits codes [--limit N]` — List transfer codes

### files
- `files list [--limit N] [--offset N]` — List files
- `files get <file_id>` — Get file details
- `files upload <file_path>` — Upload file
- `files delete <file_id>` — Delete file

### reports
- `reports list [--limit N] [--offset N]` — List reports
- `reports get <report_id>` — Get report
- `reports create --template TEMPLATE_ID [--name NAME]` — Create report
- `reports delete <report_id>` — Delete report
- `reports templates list` — List report templates

### hotspots
- `hotspots list [--device DEVICE_ID] [--limit N]` — List hotspots
- `hotspots get <hotspot_id>` — Get hotspot details
- `hotspots create --device DEVICE_ID --name NAME` — Create hotspot
- `hotspots update <hotspot_id> [--name NAME]` — Update hotspot
- `hotspots delete <hotspot_id>` — Delete hotspot

### passwords
- `passwords get <device_id>` — Get device password
- `passwords update <device_id> --password PASSWORD` — Update password
- `passwords update <device_id> --password-stdin` — Update password (reads from stdin, safer)

### smtp
- `smtp list [--limit N] [--offset N]` — List SMTP configs
- `smtp get <config_id>` — Get SMTP config
- `smtp create --host HOST [--port PORT] [--username USER] [--password PASS]` — Create SMTP config
- `smtp update <config_id> [--host HOST] [--port PORT]` — Update SMTP config
- `smtp delete <config_id>` — Delete SMTP config

### auth
- `auth test` — Test API connectivity
- `auth status` — Show current auth info

### config
- `config set <key> <value>` — Set configuration (api_token, default_limit)
- `config get [key]` — Show configuration
- `config delete <key>` — Delete configuration
- `config path` — Show config file path

## Examples

```bash
# List all online devices
cli-anything-rms devices list --status online

# Get device details as JSON
cli-anything-rms --json devices get 12345

# Check alerts for a specific device
cli-anything-rms alerts list --device 12345

# Interactive mode
cli-anything-rms
```
