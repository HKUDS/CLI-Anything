# 宝塔面板 (Baota Panel) CLI Harness - SOP

## Overview

宝塔面板 (Baota Panel) is a Linux server management panel with a web-based GUI. The source code is at `/www/server/panel/`. This CLI harness provides command-line access to all major panel functions.

## Architecture

### Source Layout
- `/www/server/panel/BT-Panel` - Main entry point (Python/Flask)
- `/www/server/panel/class/` - Core Python modules
  - `ajax.py` - API endpoints
  - `panelSite.py` - Website management (257 methods)
  - `panelAuth.py` - Authentication
  - `config.py` - Panel configuration
  - `database.py` - Database management (MySQL)
  - `files.py` - File management
  - `public.py` - Shared utilities
  - `panelFirewall.py` - Firewall management
  - `panelSSL.py` - SSL certificate management
  - `panelPlugin.py` - Plugin management
- `/www/server/panel/config/` - Configuration files
- `/www/server/panel/data/` - SQLite databases and runtime data
- `/www/server/panel/BTPanel/` - Flask web application

### Backend
- Python 3 + Flask web framework
- SQLite for panel data (data/default.db)
- Shell commands for system operations
- PluginLoader for C-extension module loading

## CLI Command Groups

### `sites` - Website Management
- `list` - List all websites
- `create` - Create a new website
- `delete` - Delete a website
- `start` - Start a website
- `stop` - Stop a website
- `info` - Get website details
- `domains` - Manage site domains
- `ssl` - Manage SSL certificates
- `php-version` - Get/set PHP version
- `path` - Get/set site path
- `limits` - Manage bandwidth limits
- `set-port <site_id> <port>` - Change a site's listening port

### `databases` - Database Management
- `list` - List all databases
- `create` - Create a database
- `delete` - Delete a database
- `backup` - Backup a database
- `user` - Manage database users

### `files` - File Management
- `list` - List files in a directory
- `upload` - Upload a file
- `download` - Download a file
- `delete` - Delete a file/directory
- `permissions` - Set file permissions

### `config` - Panel Configuration
- `show` - Show panel configuration
- `set` - Set configuration values
- `port` - Manage panel port
- `ssl` - Manage panel SSL
- `security` - Security settings
- `dns set` - Configure DNS API provider (DNSPod, Aliyun, Cloudflare)
- `dns list` - List configured DNS API providers
- `dns record add <domain> <subdomain> <type> <value>` - Add a DNS record
- `dns record list <domain>` - List DNS records for a domain
- `dns record delete <record_id>` - Delete a DNS record

### `system` - System Management
- `status` - Panel status
- `restart` - Restart panel services
- `logs` - View panel logs
- `info` - System information
- `network` - Show server IPv4/IPv6 addresses

### `plugins` - Plugin Management
- `list` - List installed plugins
- `install` - Install a plugin
- `uninstall` - Uninstall a plugin

### `cron` - Scheduled Task (计划任务) Management
- `list` - List all scheduled tasks
- `info` - Get details of a specific task
- `add` - Add a new scheduled task
- `delete` - Delete a scheduled task
- `start` - Start/enable a task
- `stop` - Stop/disable a task
- `check-le` - Check if Let's Encrypt renewal task exists and is active
- `ensure-le` - Ensure Let's Encrypt renewal task exists (create/restart if needed)

### `sites ssl deploy` - SSL Deploy Workflow
- Applies SSL certificate to a site
- Then checks/ensures Let's Encrypt auto-renewal cron task
- `--skip-ssl` flag to only run the renewal cron check

## Output Formats

- Default: Human-readable text
- `--json`: Machine-readable JSON output
- JSON structure: `{"status": true/false, "data": {...}, "msg": "..."}`

## REPL Mode

Run `cli-anything-baota` without arguments to enter REPL mode:
```
Baota CLI > sites list
Baota CLI > sites create --domain example.com --path /www/wwwroot/example.com
Baota CLI > config show
Baota CLI > exit
```
