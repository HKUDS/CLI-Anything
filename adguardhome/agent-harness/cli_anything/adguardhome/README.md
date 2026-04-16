# cli-anything-adguardhome

CLI harness for AdGuardHome - control your ad blocker from the command line or via agents.

## Prerequisites

AdGuardHome must be running. Install:

```bash
# Linux - native
curl -s -S -L https://raw.githubusercontent.com/AdguardTeam/AdGuardHome/master/scripts/install.sh | sh -s -- -v

# Docker
docker run --name adguardhome -p 3000:3000 adguard/adguardhome
```

## Installation

```bash
cd agent-harness
pip install -e .
cli-anything-adguardhome --help
```

## Configuration

```bash
export AGH_HOST=localhost
export AGH_PORT=3000
export AGH_USERNAME=admin
export AGH_PASSWORD=secret

# Or save to config file
cli-anything-adguardhome --host localhost --port 3000 --username admin --password secret config save
```

## Usage

```bash
# Interactive REPL (default)
cli-anything-adguardhome

# One-shot commands
cli-anything-adguardhome server status
cli-anything-adguardhome filter list
cli-anything-adguardhome --json stats show

# Filtering
cli-anything-adguardhome filter add --url https://somehost.com/list.txt --name "My List"
cli-anything-adguardhome filter refresh

# DNS rewrites
cli-anything-adguardhome rewrite add --domain "myserver.local" --answer "192.168.1.50"
cli-anything-adguardhome rewrite list

# Clients
cli-anything-adguardhome clients add --name "My PC" --ip 192.168.1.100

# Stats
cli-anything-adguardhome stats show
cli-anything-adguardhome stats reset
```

## Tests

```bash
cd agent-harness
python3 -m pytest cli_anything/adguardhome/tests/test_core.py -v
python3 -m pytest cli_anything/adguardhome/tests/test_full_e2e.py -v -s
CLI_ANYTHING_FORCE_INSTALLED=1 python3 -m pytest cli_anything/adguardhome/tests/ -v -s
```
