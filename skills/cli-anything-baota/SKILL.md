---
name: "cli-anything-baota"
description: >-
  Command-line interface for 宝塔面板 (Baota Panel) - A Linux server management panel for website, database, DNS, SSL, firewall, and cron management. Designed for AI agents and server administrators.
---

# cli-anything-baota

CLI harness for 宝塔面板 (Baota Panel) - a Linux server management panel. Provides command-line access to all major panel functions including site management, SSL certificates, databases, DNS records, firewalls, and scheduled tasks.

## Installation

This CLI is installed as part of the cli-anything-baota package:

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=baota/agent-harness
```

**Prerequisites:**
- 宝塔面板 installed at `/www/server/panel/`
- Python 3.7+
- Root/sudo access for panel operations

## Usage

### Basic Commands

```bash
# Show help
cli-anything-baota --help

# Start interactive REPL mode
cli-anything-baota

# Run with JSON output (for agent consumption)
cli-anything-baota --json system status
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-baota
# Enter commands interactively
# Type 'help' for commands, 'exit' to quit
```

## Command Groups

### Sites

Website management commands.

| Command | Description |
|---------|-------------|
| `list` | List all websites |
| `info <id>` | Show website details |
| `create --domain D --path P` | Create a new website |
| `delete <id>` | Delete a website |
| `start <id>` | Start a website |
| `stop <id>` | Stop a website |
| `domains <id>` | List domains for a site |
| `add-domain <id> <domain>` | Add a domain to a site |
| `set-port <id> <port>` | Change a site's listening port |

### Sites SSL

SSL certificate management.

| Command | Description |
|---------|-------------|
| `apply <id>` | Apply Let's Encrypt SSL certificate |
| `info <id>` | Show SSL certificate info |
| `close <id>` | Disable SSL on a site |
| `deploy <id>` | Apply SSL + ensure auto-renewal cron |

### Sites Proxy

Reverse proxy management.

| Command | Description |
|---------|-------------|
| `create <id> --target URL` | Create a reverse proxy |

### Databases

Database management commands.

| Command | Description |
|---------|-------------|
| `list` | List all databases |
| `create --name N --user U --pass P` | Create a new database |
| `delete <id>` | Delete a database |
| `backup <id>` | Backup a database |

### Files

File management commands.

| Command | Description |
|---------|-------------|
| `list <path>` | List files and directories |
| `read <path>` | Read a file's content |
| `write <path> <content>` | Write content to a file |
| `mkdir <path>` | Create a directory |
| `delete <path>` | Delete a file or directory |

### Config

Panel configuration commands.

| Command | Description |
|---------|-------------|
| `show` | Show panel configuration |
| `port [port]` | Get or set panel port |
| `password <pw>` | Set panel password |
| `username <user>` | Set panel username |
| `logs [--lines N]` | View panel error logs |

### Config DNS

DNS API provider management.

| Command | Description |
|---------|-------------|
| `set <provider>` | Configure DNS API provider |
| `list` | List configured DNS providers |

### Config DNS Record

DNS record management (via configured provider).

| Command | Description |
|---------|-------------|
| `add <domain> <sub> <type> <value>` | Add a DNS record |
| `list <domain>` | List DNS records for a domain |
| `delete <domain> <id>` | Delete a DNS record |

### System

System management commands.

| Command | Description |
|---------|-------------|
| `status` | Show panel status |
| `restart` | Restart panel services |
| `stop` | Stop panel services |
| `start` | Start panel services |
| `auth` | Show panel authentication info |
| `info` | Show system information |
| `network` | Show server IPv4/IPv6 addresses |
| `firewall-open <port>` | Open a firewall port |
| `firewall-list` | List firewall rules |
| `firewall-delete <id>` | Delete a firewall rule |

### Cron

Scheduled task management.

| Command | Description |
|---------|-------------|
| `list` | List all scheduled tasks |
| `info <id>` | Get task details |
| `add --name N --type T --time T` | Add a scheduled task |
| `delete <id>` | Delete a scheduled task |
| `start <id>` | Start/enable a task |
| `stop <id>` | Stop/disable a task |
| `check-le` | Check Let's Encrypt renewal status |
| `ensure-le [--site-id N]` | Ensure LE renewal task exists |

### BT

Baota Panel menu commands.

| Command | Description |
|---------|-------------|
| `1`-`36` | Named bt menu options |
| `raw <N>` | Run any bt menu by number |

### Export

Export and reporting commands.

| Command | Description |
|---------|-------------|
| `sites [--format json/csv]` | Export sites data |
| `report` | Generate panel summary report |

## Architecture

The CLI uses a bridge pattern to communicate with the Baota Panel:

```
cli-anything-baota → Click CLI → Python subprocess → sudo + bridge script → Baota Panel API
```

- **Bridge script** (`/tmp/baota_bridge.py`): Executes panel operations via sudo with the panel's bundled Python
- **Panel Python**: `/www/server/panel/pyenv/bin/python3` (Python 3.7.8)
- **Panel class path**: `/www/server/panel/class/` + `/www/server/panel/` on `sys.path`
- **Nginx binary**: `/www/server/nginx/sbin/nginx`
- **DNS**: Direct DNSPod API calls via `dnsapi.cn/Record.*`
- **Config**: DNS API credentials stored in `/www/server/panel/config/dns_mager.conf`

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Formatted text with headers and tables
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-baota system status

# JSON output for agents
cli-anything-baota --json system status
```

## Examples

### List all websites

```bash
cli-anything-baota sites list
cli-anything-baota --json sites list
```

### Create a new website

```bash
cli-anything-baota sites create --domain example.com --path /www/wwwroot/example.com
```

### Apply SSL and ensure auto-renewal

```bash
cli-anything-baota sites ssl deploy 1 --domains example.com,www.example.com
```

### Manage firewall rules

```bash
cli-anything-baota system firewall-open 8080 --desc "My app"
cli-anything-baota system firewall-list
cli-anything-baota system firewall-delete 1
```

### DNS record management

```bash
cli-anything-baota config dns record add example.org www A 198.51.100.1
cli-anything-baota config dns record list example.org
cli-anything-baota config dns record delete example.org 12345
```

### Scheduled tasks

```bash
cli-anything-baota cron list
cli-anything-baota cron check-le
cli-anything-baota cron ensure-le --site-id 1
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** — 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use `--json` for all operations** to get structured data
5. **Site operations require sudo** through the bridge script
6. **DNS operations require configured API credentials** (`config dns set`)
7. **SSL operations require DNS API** configured for the domain's root

## Version

1.0.0
