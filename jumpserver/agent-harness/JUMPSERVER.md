# JumpServer CLI Harness - Standard Operating Procedure

## Software Overview

**JumpServer** is the most popular open-source Privileged Access Management (PAM) / bastion host platform. It provides centralized management of assets (servers, databases, network devices, web applications), user authentication and authorization, session auditing and replay, and command filtering.

- **Website:** https://www.jumpserver.com
- **Repository:** https://github.com/jumpserver/jumpserver
- **Version:** v4.0
- **License:** GPLv3
- **Tech Stack:** Django 4.1 + DRF 3.14 + Celery + Channels

## Architecture

### Core Components
JumpServer is composed of multiple services:
- **Core (Django):** REST API server, web UI backend
- **KoKo:** SSH/Telnet connector (character protocol)
- **Lion:** RDP/VNC connector (graphical protocol)
- **Chen:** Database connector (Web DB)
- **Lina:** Web UI frontend
- **Luna:** Web terminal

### Data Model (Key Entities)
- **Asset:** Polymorphic (Host, Device, Database, Web, Cloud, GPT, Custom)
- **Node:** Tree-structured asset organization (key-based path)
- **Platform:** Defines protocols, automation methods (Ansible, ping, gather facts, change secret)
- **Account:** Credential management (password/SSH key), versioned with history
- **User:** Extended Django User with MFA, face recognition, multiple auth sources
- **AssetPermission:** Asset access rules linking users/groups to assets/nodes
- **Session:** Connection session logging with replay support
- **Ticket:** Multi-level approval workflow (login confirm, command confirm, asset apply)
- **Gateway/Zone:** SSH tunnel proxy for indirect network access

### Authentication
Supports 15+ auth backends: Local, LDAP, OAuth2, SAML2, OIDC, CAS, RADIUS, SSH Key, Passkey (WebAuthn/FIDO2), WeCom, DingTalk, FeiShu, Lark, Slack

## CLI Harness Design

### Command Groups Mapping

| CLI Group | API Endpoint | Function |
|-----------|-------------|----------|
| `auth` | `/api/v1/authentication/` | Session management |
| `asset` | `/api/v1/assets/` | Asset CRUD, nodes, platforms, gateways, zones |
| `user` | `/api/v1/users/` | User/group management, profile |
| `perm` | `/api/v1/perms/` | Asset permission rules |
| `account` | `/api/v1/accounts/` | Credential management, secrets, templates |
| `session` | `/api/v1/terminal/` | Session monitoring, replay, terminals |
| `audit` | `/api/v1/audits/` | Login/operate/FTP/password logs |
| `ops` | `/api/v1/ops/` | Job execution, playbooks, ad-hoc commands |
| `system` | `/api/v1/settings/` | System settings, health checks |
| `label` | `/api/v1/labels/` | Label management |
| `role` | `/api/v1/rbac/` | Role and binding management |

### State Model

```
Session (persisted to ~/.jumpserver-cli/session.json):
├── base_url       : JumpServer instance URL
├── username       : Authenticated username
├── token          : Bearer API token
├── token_expiry   : Token expiration timestamp
├── refresh_token  : Token refresh credential
├── org_id         : Current organization (multi-org)
└── verify_ssl     : SSL verification flag

CLIState (persisted to ~/.jumpserver-cli/state.json):
├── current_org_id      : Active org
├── selected_asset_ids  : Selected assets for batch ops
├── selected_node_ids   : Selected nodes for batch ops
├── last_filters        : Previous search filters
├── pagination          : Page state
└── dry_run             : Dry run mode flag
```

### Output Format Principles

1. **table** (default): Human-readable aligned columns
2. **json**: Machine-parseable, supports `jq` processing
3. **yaml**: Human-readable structured output

### Dry Run Pattern

All mutation commands support `--dry-run`:
- Skips authentication check
- Outputs planned action and payload
- Returns exit code 0
- Prevents any API calls

### Error Handling

- `CLIError`: User-facing error with message + detail
- `CLI_ANYTHING_FORCE_INSTALLED=1`: Forces subprocess tests to use installed command
- HTTP errors convert to CLIError with API detail message

## File Structure

```
agent-harness/
├── JUMPSERVER.md                              # This SOP document
├── README.md                                  # Installation and usage guide
├── setup.py                                   # PyPI package configuration
└── cli_anything/                              # PEP 420 namespace package (no __init__.py)
    └── jumpserver/                            # Sub-package (has __init__.py)
        ├── __init__.py                        # Package metadata
        ├── jumpserver_cli.py                  # Main CLI entry point (Click)
        ├── core/
        │   ├── __init__.py                    # Core module exports
        │   ├── session.py                     # Session + JumpServerClient
        │   ├── state.py                       # CLIState management
        │   ├── output.py                      # Output formatting (table/json/yaml)
        │   ├── commands_auth.py               # Auth commands
        │   ├── commands_asset.py              # Asset commands
        │   ├── commands_user.py               # User commands
        │   ├── commands_perm.py               # Permission commands
        │   ├── commands_account.py            # Account commands
        │   ├── commands_session.py            # Session commands
        │   ├── commands_audit.py              # Audit + Ops commands
        │   └── commands_system.py             # System + Label + Role commands
        ├── utils/
        │   └── __init__.py                    # Utility functions and decorators
        ├── skills/
        │   └── SKILL.md                       # Packaged skill compatibility copy
        └── tests/
            ├── TEST.md                        # Test plan and results
            ├── test_core.py                   # 59 unit tests
            └── test_full_e2e.py               # 44 E2E tests
skills/
└── cli-anything-jumpserver/
    └── SKILL.md                               # Canonical skill definition
```

## Testing Summary

- **103 tests total** (59 unit + 44 E2E), **100% pass rate**
- Unit tests: Session, Client, State, Output formatting, Utilities
- E2E tests: CLI discovery, Help output, Parameter validation, Dry run, Output formats, Workflow scenarios

## Known Limitations

1. Requires network access to JumpServer API for data-operating commands
2. No local caching of assets/users (all queries hit API)
3. REPL tab completion is command-aware but not context-aware
4. No support for WebSocket operations (session logging, terminal status streaming)
