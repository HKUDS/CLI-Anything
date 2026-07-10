# cli-anything-jumpserver

JumpServer bastion host CLI harness for AI agents and humans.

## Quick Start

```bash
# Install
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=jumpserver/agent-harness

# Configure
cli-anything-jumpserver config set base_url https://jumpserver.example.com
cli-anything-jumpserver config set token YOUR_PRIVATE_TOKEN

# Test connection
cli-anything-jumpserver config test

# Start using
cli-anything-jumpserver asset list
cli-anything-jumpserver --interactive
```

## Prerequisites

- Python 3.10+
- JumpServer v3.0+ instance with API access
- JumpServer Private Token (generated via Django shell: `u.create_private_token()`)

## Features

- Asset management (hosts, devices, databases, clouds, nodes, platforms, gateways)
- User management (CRUD, groups, MFA reset, password management)
- Permission management (asset permissions, user permissions)
- Account management (credentials, secrets, templates)
- Session management (list, kill, replay, terminal status)
- Audit logs (login, operate, FTP, password change)
- System operations (settings, health, labels, roles)

## Output Formats

- Table (default, human-readable)
- JSON (`--json-output` flag for programmatic consumption)

## Testing

```bash
# Unit tests (no backend required)
pytest cli_anything/jumpserver/tests/test_core.py -v

# E2E tests (requires JumpServer instance)
JUMPSERVER_URL=https://jumpserver.example.com \
JUMPSERVER_TOKEN=your_token \
pytest cli_anything/jumpserver/tests/test_full_e2e.py -v
```
