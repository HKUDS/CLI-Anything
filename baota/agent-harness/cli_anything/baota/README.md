# cli-anything-baota

CLI harness for 宝塔面板 (Baota Panel) - a Linux server management panel.

## Installation

```bash
pip install cli-anything-baota
```

Or install from source:

```bash
cd agent-harness
pip install -e .
```

## Usage

### One-shot commands

```bash
# System management
cli-anything-baota system status
cli-anything-baota system restart
cli-anything-baota system info

# Site management
cli-anything-baota sites list
cli-anything-baota sites info 1
cli-anything-baota sites create --domain example.com --path /www/wwwroot/example.com

# Database management
cli-anything-baota databases list
cli-anything-baota databases create --name mydb --username myuser --password mypass

# File management
cli-anything-baota files list /www/wwwroot
cli-anything-baota files read /www/wwwroot/index.html

# Configuration
cli-anything-baota config show
cli-anything-baota config port 8888
cli-anything-baota config logs --lines 50
```

### DNS record management (via configured provider)

```bash
cli-anything-baota config dns record add example.org www A 198.51.100.1
cli-anything-baota config dns record list example.org
cli-anything-baota config dns record delete 123
```

### Site port modification

```bash
cli-anything-baota sites set-port 1 802
```

### Network information

```bash
cli-anything-baota system network
cli-anything-baota --json system network
```

### JSON output

```bash
cli-anything-baota --json sites list
cli-anything-baota --json system status
```

### Scheduled task management

```bash
cli-anything-baota cron list
cli-anything-baota cron check-le
cli-anything-baota cron ensure-le --site-id 1
cli-anything-baota cron start 3
cli-anything-baota cron stop 3
cli-anything-baota cron delete 3
```

### SSL deploy workflow (apply SSL + ensure renewal cron)

```bash
cli-anything-baota sites ssl deploy 1
cli-anything-baota sites ssl deploy 1 --domains example.com,www.example.com
cli-anything-baota sites ssl deploy 1 --skip-ssl
```

### REPL mode

```bash
cli-anything-baota
```

Then type commands interactively:

```
Baota CLI > sites list
Baota CLI > system status
Baota CLI > exit
```

## Requirements

- Baota Panel installed at `/www/server/panel/`
- Python 3.7+
