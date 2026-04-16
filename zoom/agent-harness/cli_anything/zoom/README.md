# cli-anything-zoom

CLI harness for **Zoom** — manage meetings, participants, and recordings from the command line via the Zoom REST API.

## Installation

```bash
pip install cli-anything-zoom
# or from source:
cd zoom/agent-harness && pip install -e .
```

## Prerequisites

1. A Zoom account (free or paid)
2. A Zoom OAuth App — create one at https://marketplace.zoom.us/develop/create
   - App type: **General App** (OAuth)
   - Redirect URL: `http://localhost:4199/callback`
   - Required scopes: `user:read:admin`, `meeting:read:admin`, `meeting:write:admin`, `recording:read:admin`

## Quick Start

```bash
# 1. Configure OAuth credentials
cli-anything-zoom auth setup --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET

# 2. Login (opens browser)
cli-anything-zoom auth login

# 3. Create a meeting
cli-anything-zoom meeting create --topic "Team Standup" --duration 30

# 4. List meetings
cli-anything-zoom meeting list

# 5. Interactive mode
cli-anything-zoom repl
```

## Commands

| Group | Commands |
|---|---|
| `auth` | `setup`, `login`, `status`, `logout` |
| `meeting` | `create`, `list`, `info`, `update`, `delete`, `join`, `start` |
| `participant` | `add`, `add-batch`, `list`, `remove`, `attended` |
| `recording` | `list`, `files`, `download`, `delete` |

## Agent Usage (JSON mode)

All commands support `--json` for machine-readable output:

```bash
cli-anything-zoom --json meeting list
cli-anything-zoom --json meeting create --topic "Sync" --duration 60 --auto-recording cloud
```
