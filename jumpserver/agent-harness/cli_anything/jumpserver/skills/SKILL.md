---
name: cli-anything-jumpserver
description: Stateful CLI harness for JumpServer bastion host management. Supports asset, user, permission, account, session, audit, and operations management via REST API, with both one-shot and interactive REPL modes.
version: 0.1.0
category: infrastructure
tags:
  - jumpserver
  - bastion
  - pam
  - security
  - ssh
  - cli
commands:
  - group: auth
    description: Authentication and session management
    subcommands:
      - name: login
        description: Authenticate to JumpServer and store session token
        options: ["--url", "--username", "--password", "--org", "--insecure"]
      - name: logout
        description: Clear the current session
      - name: status
        description: Show current authentication status
      - name: org
        description: Switch or list organizations
        options: ["--list"]

  - group: asset
    description: Manage assets (hosts, devices, databases, nodes, platforms, gateways, zones)
    subcommands:
      - name: list
        description: List assets of a given type
        options: ["--type", "--search", "--node", "--platform", "--active/--inactive", "--limit", "--offset"]
      - name: get
        description: Get details of a specific asset
      - name: create
        description: Create a new asset
        options: ["--name", "--address", "--platform", "--type", "--nodes", "--dry-run"]
      - name: update
        description: Update an existing asset
        options: ["--name", "--address", "--comment", "--active/--inactive", "--dry-run"]
      - name: delete
        description: Delete an asset
        options: ["--force", "--dry-run"]
      - name: node
        description: Manage asset nodes (tree organization)
        subcommands:
          - name: list
            description: List nodes
            options: ["--tree", "--parent"]
          - name: create
            description: Create a new node
          - name: delete
            description: Delete a node
          - name: add-assets
            description: Add assets to a node
      - name: platform
        description: Manage asset platforms
        subcommands:
          - name: list
            description: List platforms
      - name: gateway
        description: Manage gateways
        subcommands:
          - name: list
            description: List gateways
          - name: test
            description: Test gateway connectivity
      - name: zone
        description: Manage zones
        subcommands:
          - name: list
            description: List zones

  - group: user
    description: Manage users and user groups
    subcommands:
      - name: list
        description: List users
        options: ["--search", "--source", "--active/--inactive"]
      - name: get
        description: Get user details
      - name: create
        description: Create a new user
        options: ["--name", "--username", "--email", "--password", "--role", "--dry-run"]
      - name: update
        description: Update a user
      - name: delete
        description: Delete a user
      - name: reset-password
        description: Reset a user's password
      - name: unblock
        description: Unblock a locked user
      - name: profile
        description: Show current user profile
      - name: my-assets
        description: List assets the current user can access
      - name: group
        description: Manage user groups
        subcommands:
          - name: list
            description: List user groups
          - name: create
            description: Create a user group
          - name: members
            description: List members of a user group

  - group: perm
    description: Manage asset permissions
    subcommands:
      - name: list
        description: List asset permissions
        options: ["--search", "--user", "--active/--inactive"]
      - name: get
        description: Get permission details
      - name: create
        description: Create a new asset permission
        options: ["--name", "--users", "--user-groups", "--assets", "--nodes", "--actions", "--dry-run"]
      - name: update
        description: Update an asset permission
      - name: delete
        description: Delete an asset permission
      - name: users
        description: List users assigned to a permission
      - name: assets
        description: List assets authorized by a permission

  - group: account
    description: Manage asset accounts and credentials
    subcommands:
      - name: list
        description: List asset accounts
        options: ["--search", "--asset", "--secret-type", "--privileged/--unprivileged"]
      - name: get
        description: Get account details
      - name: create
        description: Create a new asset account
        options: ["--asset", "--username", "--secret-type", "--secret", "--dry-run"]
      - name: update
        description: Update an asset account
      - name: delete
        description: Delete an asset account
      - name: secret
        description: View account secrets/passwords
        subcommands:
          - name: view
            description: View an account's password/secret
          - name: history
            description: View password change history
      - name: template
        description: Manage account templates
        subcommands:
          - name: list
            description: List account templates

  - group: session
    description: Manage terminal sessions and replays
    subcommands:
      - name: list
        description: List terminal sessions
        options: ["--search", "--user", "--asset", "--protocol", "--active/--finished"]
      - name: get
        description: Get session details
      - name: replay
        description: Get session replay URL/info
      - name: kill
        description: Kill an active session
      - name: command
        description: View session command history
        subcommands:
          - name: list
            description: List command records
            options: ["--session", "--user", "--risk"]
      - name: terminal
        description: Manage terminal components
        subcommands:
          - name: list
            description: List terminal components
          - name: status
            description: Get terminal component status

  - group: audit
    description: View audit logs
    subcommands:
      - name: login
        description: View user login audit logs
      - name: operate
        description: View resource operation audit logs
      - name: ftp
        description: View FTP file transfer audit logs
      - name: password
        description: View password change audit logs
      - name: activity
        description: View user activity logs

  - group: ops
    description: Manage operations and job execution
    subcommands:
      - name: job-list
        description: List execution jobs
      - name: job-log
        description: Get job execution log
      - name: adhoc-list
        description: List ad-hoc command executions
      - name: playbook-list
        description: List Ansible playbooks

  - group: system
    description: Manage system settings
    subcommands:
      - name: settings
        description: List system settings
      - name: health
        description: Check system health
      - name: info
        description: Show system information

  - group: label
    description: Manage labels
    subcommands:
      - name: list
        description: List labels

  - group: role
    description: Manage roles and permissions
    subcommands:
      - name: list
        description: List roles
      - name: bindings
        description: List role bindings
---

# cli-anything-jumpserver

Stateful CLI harness for JumpServer bastion host. Manage assets, users, permissions, accounts, sessions, audits, and more via the JumpServer REST API.

## Quick Start

```bash
# Install
cd agent-harness && pip install -e .

# Authenticate
cli-anything-jumpserver auth login --url https://jumpserver.example.com --username admin

# List hosts
cli-anything-jumpserver asset list --type host

# Interactive REPL mode
cli-anything-jumpserver --interactive
```

## Agent Usage Guidance

This CLI is designed for AI agent consumption. Key features for agents:

### JSON Output Mode
All commands support `--output json` for machine-parseable output:
```bash
cli-anything-jumpserver asset list --type host --output json
```

### Dry Run Mode
All mutation commands support `--dry-run` to preview without execution:
```bash
cli-anything-jumpserver asset create --name test --address 10.0.0.1 --platform 1 --dry-run --output json
```

### Environment Variables
- `JUMPSERVER_URL` - Default JumpServer URL
- `JUMPSERVER_USERNAME` - Default username
- `JUMPSERVER_PASSWORD` - Default password

### Typical Agent Workflows

**1. Discovery and Inventory**
```bash
# Check connection
cli-anything-jumpserver auth status --output json

# List all hosts
cli-anything-jumpserver asset list --type host --output json

# Get asset details
cli-anything-jumpserver asset get <ID> --type host --output json

# List all users
cli-anything-jumpserver user list --output json
```

**2. User and Permission Management**
```bash
# Create user
cli-anything-jumpserver user create --name "New User" --username newuser --email user@example.com --output json --dry-run

# Grant asset access
cli-anything-jumpserver perm create --name "App Access" --users "user1,user2" --assets "asset1,asset2" --output json --dry-run

# Verify permissions
cli-anything-jumpserver perm users <PERM_ID> --output json
```

**3. Security Audit**
```bash
# Check failed logins
cli-anything-jumpserver audit login --status failed --output json

# Review operations
cli-anything-jumpserver audit operate --action delete --output json

# Check active sessions
cli-anything-jumpserver session list --active --output json

# View command history
cli-anything-jumpserver session command list --risk 5 --output json
```

**4. Session Management**
```bash
# Monitor active sessions
cli-anything-jumpserver session list --active --output json

# Check terminal health
cli-anything-jumpserver session terminal list --output json
cli-anything-jumpserver session terminal status <TERMINAL_ID> --output json
```

## Output Formats

| Format | Flag | Use Case |
|--------|------|----------|
| Table | `--output table` (default) | Human-readable display |
| JSON | `--output json` | Agent consumption, scripting |
| YAML | `--output yaml` | Configuration, readability |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | CLI error (auth, API, etc.) |
| 2 | Usage error (invalid options/arguments) |
| 130 | Interrupted (Ctrl+C) |

## File Locations

| Path | Purpose |
|------|---------|
| `~/.jumpserver-cli/session.json` | Authentication session |
| `~/.jumpserver-cli/state.json` | CLI operational state |
