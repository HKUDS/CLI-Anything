# cli-anything-n8n

[![PyPI](https://img.shields.io/pypi/v/cli-anything-n8n.svg)](https://pypi.org/project/cli-anything-n8n/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CLI-Anything](https://img.shields.io/badge/CLI--Anything-harness-orange.svg)](https://github.com/HKUDS/CLI-Anything)
[![n8n API v1.1.1](https://img.shields.io/badge/n8n-API%20v1.1.1-EA4B71.svg)](https://docs.n8n.io/api/api-reference/)

Control your [n8n](https://n8n.io) instance from the terminal. List workflows, check executions, manage tags — all without opening the browser.

Built with the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) pattern, so AI agents can use it too.

## Installation

```bash
pip install cli-anything-n8n
```

## Quick Start

```bash
# Connect to your n8n
export N8N_BASE_URL=https://your-n8n-instance.com
export N8N_API_KEY=your-api-key

# Try it!
cli-anything-n8n workflow list
```

> **Where do I get my API key?** In n8n, go to Settings > API > Create API Key.

## JSON Output Mode

All commands support `--json` for machine-readable output:

```bash
cli-anything-n8n --json workflow list
cli-anything-n8n --json execution list --status error
```

## Interactive REPL

```bash
cli-anything-n8n
n8n> workflow list
n8n> tag list
n8n> exit
```

## Command Groups

### Workflow Management
```
workflow list          - List all workflows
workflow get           - Get workflow details
workflow create        - Create a workflow from JSON
workflow update        - Update a workflow from JSON
workflow delete        - Delete a workflow
workflow activate      - Activate a workflow
workflow deactivate    - Deactivate a workflow
workflow tags          - List tags on a workflow
workflow set-tags      - Set tags on a workflow
workflow transfer      - Transfer ownership
workflow export        - Export to file
workflow import        - Import from file
workflow backup-all    - Backup all workflows
workflow restore-all   - Restore from backup
workflow diff          - Compare two workflows
workflow bulk-activate - Activate multiple workflows
workflow bulk-deactivate - Deactivate multiple workflows
workflow validate      - Validate workflow structure
workflow autofix       - Auto-fix common issues
workflow patch         - Patch workflow fields
workflow test          - Test a webhook workflow
workflow scaffold      - Create from built-in patterns
workflow patterns      - List available patterns
workflow versions      - Local version snapshots (list/show/rollback/diff/prune/stats)
```

### Execution Management
```
execution list    - List executions
execution get     - Get execution details
execution delete  - Delete an execution
execution retry   - Retry a failed execution
execution errors  - List failed executions
execution watch   - Watch executions in real-time
```

### Template Management
```
template search   - Search n8n.io templates
template get      - Get template details
template deploy   - Deploy a template
```

### Node Discovery
```
node search   - Search community nodes
node info     - Get node package details
```

### Credential Management
```
credential create    - Create a credential
credential delete    - Delete a credential
credential schema    - Show credential schema
credential transfer  - Transfer ownership
```

### Variable Management
```
variable list    - List variables
variable create  - Create a variable
variable update  - Update a variable
variable delete  - Delete a variable
```

### Tag Management
```
tag list    - List tags
tag get     - Get tag details
tag create  - Create a tag
tag update  - Update a tag
tag delete  - Delete a tag
```

### Configuration
```
config show   - Show current configuration
config set    - Set a configuration value
config test   - Test the connection
```

### Standalone
```
status       - Show n8n instance status
health       - Health check
expression   - Validate n8n expressions offline
completions  - Generate shell completions
```

## Configuration

| Method | Priority | Example |
|--------|----------|---------|
| CLI flags | 1 (highest) | `--url https://... --api-key xxx` |
| Environment variables | 2 | `N8N_BASE_URL`, `N8N_API_KEY` |
| Config file | 3 | `cli-anything-n8n config set ...` |

Extra env vars: `N8N_TIMEOUT` (default: 30 seconds)

## Running Tests

```bash
# From the agent-harness directory:

# Run all unit tests
python3 -m pytest cli_anything/n8n/tests/test_core.py -v

# Run E2E tests (needs a running n8n instance)
export N8N_BASE_URL=https://your-n8n.com
export N8N_API_KEY=your-key
python3 -m pytest cli_anything/n8n/tests/test_full_e2e.py -v
```

## Architecture

```
cli_anything/n8n/
├── n8n_cli.py          # CLI + interactive REPL (55+ commands)
├── core/               # API wrappers (one file per resource)
│   ├── workflows.py
│   ├── executions.py
│   ├── credentials.py
│   ├── variables.py
│   ├── tags.py
│   ├── templates.py
│   ├── nodes.py
│   ├── versions.py     # Local SQLite version snapshots
│   ├── fixers.py       # Workflow autofix engine
│   ├── scaffolds.py    # Built-in workflow patterns
│   ├── expressions.py  # Offline expression validator
│   └── project.py      # Config management
├── utils/
│   ├── n8n_backend.py  # HTTP client
│   └── repl_skin.py    # Terminal UI (standard cli-anything skin)
├── skills/
│   └── SKILL.md        # Agent discovery metadata
└── tests/
    ├── test_core.py    # Unit tests (mocked HTTP)
    └── test_full_e2e.py # E2E tests (live n8n)
```

## n8n Compatibility

Verified against **n8n 2.43.0** (Public API v1.1.1). Works with any n8n >= 1.0.0.

> **Note**: Some n8n features (Data Tables, credential listing, execution stop) are not available through the public API. This CLI only exposes verified, working endpoints.
