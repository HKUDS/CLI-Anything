---
name: >-
  cli-anything-adguardhome
description: >-
  Command-line interface for AdGuard Home - Network-wide ad blocking and DNS management via AdGuard Home REST API. Designed for AI agents and power users who need to manage filtering, DNS rewrites, clients, DHCP, and query logs without a GUI.
---

# cli-anything-adguardhome

Network-wide ad blocking and DNS management via the AdGuard Home REST API. Designed for AI agents and power users who need to manage filtering, DNS rewrites, clients, DHCP, and query logs without a GUI.

## Installation

This CLI is installed as part of the cli-anything-adguardhome package:

```bash
pip install cli-anything-adguardhome
```

**Prerequisites:**
- Python 3.10+
- AdGuard Home must be installed and running
- Install AdGuard Home: `curl -s -S -L https://raw.githubusercontent.com/AdguardTeam/AdGuardHome/master/scripts/install.sh | sh -s -- -v`

## Usage

### Basic Commands

```bash
# Show help
cli-anything-adguardhome --help

# Start interactive REPL mode
cli-anything-adguardhome

# Check server status
cli-anything-adguardhome server status

# Run with JSON output (for agent consumption)
cli-anything-adguardhome --json server status
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-adguardhome
# Enter commands interactively with tab-completion and history
```

## Command Groups

### Config

Connection and configuration management.

| Command | Description |
|---------|-------------|
| `show` | Show current connection configuration |
| `save` | Save connection settings to a config file |
| `test` | Test the connection to AdGuard Home |

### Server

Server status and control commands.

| Command | Description |
|---------|-------------|
| `status` | Show server protection status |
| `version` | Show AdGuard Home version |
| `restart` | Restart the AdGuard Home server |

### Filter

DNS filter list management.

| Command | Description |
|---------|-------------|
| `list` | List all configured filter lists |
| `status` | Show filtering status |
| `toggle` | Enable or disable filtering globally |
| `add` | Add a new filter list by URL |
| `remove` | Remove a filter list |
| `enable` | Enable a specific filter list |
| `disable` | Disable a specific filter list |
| `refresh` | Force-refresh all filter lists |

### Blocking

Parental control, safe browsing, and safe search settings.

| Command | Description |
|---------|-------------|
| `parental status` | Show parental control status |
| `parental enable` | Enable parental control |
| `parental disable` | Disable parental control |
| `safebrowsing status` | Show safe browsing status |
| `safebrowsing enable` | Enable safe browsing |
| `safebrowsing disable` | Disable safe browsing |
| `safesearch status` | Show safe search status |
| `safesearch enable` | Enable safe search |
| `safesearch disable` | Disable safe search |

### Blocked-Services

Manage blocked internet services.

| Command | Description |
|---------|-------------|
| `list` | List currently blocked services |
| `set` | Set the list of blocked services |

### Clients

Client device management.

| Command | Description |
|---------|-------------|
| `list` | List all configured clients |
| `add` | Add a new client by name and IP |
| `remove` | Remove a client |
| `show` | Show details for a specific client |

### Stats

Query statistics.

| Command | Description |
|---------|-------------|
| `show` | Show DNS query statistics |
| `reset` | Reset all statistics |
| `config` | View or update statistics retention interval |

### Log

DNS query log management.

| Command | Description |
|---------|-------------|
| `show` | Show recent DNS query log entries |
| `config` | View or update query log settings |
| `clear` | Clear the query log |

### Rewrite

DNS rewrite rules.

| Command | Description |
|---------|-------------|
| `list` | List all DNS rewrite rules |
| `add` | Add a DNS rewrite rule |
| `remove` | Remove a DNS rewrite rule |

### DHCP

DHCP server management.

| Command | Description |
|---------|-------------|
| `status` | Show DHCP server status |
| `leases` | List active DHCP leases |
| `add-static` | Add a static DHCP lease |
| `remove-static` | Remove a static DHCP lease |

### TLS

TLS/HTTPS configuration.

| Command | Description |
|---------|-------------|
| `status` | Show TLS configuration status |

## Examples

### Check Server Status

```bash
cli-anything-adguardhome server status
cli-anything-adguardhome server version
```

### Manage Filter Lists

```bash
# List current filters
cli-anything-adguardhome filter list

# Add a new blocklist
cli-anything-adguardhome filter add --url https://somehost.com/list.txt --name "My List"

# Refresh all filters
cli-anything-adguardhome filter refresh
```

### DNS Rewrites

```bash
# Add a local DNS entry
cli-anything-adguardhome rewrite add --domain "myserver.local" --answer "192.168.1.50"

# List all rewrites
cli-anything-adguardhome rewrite list
```

### Client Management

```bash
cli-anything-adguardhome clients add --name "My PC" --ip 192.168.1.100
cli-anything-adguardhome clients list
```

### Query Statistics

```bash
# Show stats (human-readable)
cli-anything-adguardhome stats show

# Show stats (JSON for agents)
cli-anything-adguardhome --json stats show
```

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-adguardhome filter list

# JSON output for agents
cli-anything-adguardhome --json filter list
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Test connection first** with `config test` before other commands

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0
