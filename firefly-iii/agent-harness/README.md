# Firefly III CLI

Firefly III command-line interface based on CLI-Anything specification. Converts MCP mode to stateless CLI mode to avoid Node residual process issues.

## Installation

```bash
pip install cli-anything-firefly-iii
```

## Prerequisites

- Python 3.10+
- Running Firefly III instance
- Personal Access Token (PAT)

## Configuration

### Environment Variables (Recommended)

```bash
export FIREFLY_III_BASE_URL="https://firefly.yourdomain.com"
export FIREFLY_III_PAT="your-personal-access-token"
```

### Command Line Arguments

```bash
cli-anything-firefly-iii --base-url https://firefly.yourdomain.com --pat your-token
```

## Usage

### REPL Mode

```bash
cli-anything-firefly-iii
```

### Subcommand Mode

```bash
# Account management
cli-anything-firefly-iii accounts list
cli-anything-firefly-iii accounts list --type asset
cli-anything-firefly-iii accounts get --id 123
cli-anything-firefly-iii accounts create --name "Cash" --type asset --currency-code USD

# Transaction management
cli-anything-firefly-iii transactions list
cli-anything-firefly-iii transactions list --limit 10 --start 2024-01-01
cli-anything-firefly-iii transactions create --description "Grocery" --amount 50.00 --source-account 1
cli-anything-firefly-iii transactions get --id 456

# Budget management
cli-anything-firefly-iii budgets list

# Category management
cli-anything-firefly-iii categories list

# Tag management
cli-anything-firefly-iii tags list

# Bill management
cli-anything-firefly-iii bills list

# Piggy banks
cli-anything-firefly-iii piggy-banks list

# Insights and reports
cli-anything-firefly-iii insights expense --start 2024-01-01 --end 2024-01-31
cli-anything-firefly-iii insights income --start 2024-01-01 --end 2024-01-31

# Search
cli-anything-firefly-iii search transactions --query "grocery"

# Data export
cli-anything-firefly-iii export transactions --start 2024-01-01 --end 2024-01-31

# System information
cli-anything-firefly-iii info about
cli-anything-firefly-iii info status
```

### JSON Output

All commands support `--json` flag for structured output:

```bash
cli-anything-firefly-iii --json accounts list
```

### Preset Filtering

Use `--preset` parameter to filter available commands:

```bash
# Default preset (core features)
cli-anything-firefly-iii --preset default accounts list

# Full preset (all features)
cli-anything-firefly-iii --preset full accounts list

# Budget preset
cli-anything-firefly-iii --preset budget budgets list

# Reporting preset
cli-anything-firefly-iii --preset reporting insights expense --start 2024-01-01 --end 2024-01-31
```

Available presets:
- `default`: Core features (accounts, transactions, categories, tags, bills, search)
- `full`: All features
- `basic`: Basic features (accounts, transactions, categories, tags, search)
- `budget`: Budget-related (accounts, budgets, transactions, summary, insight)
- `reporting`: Reporting-related (accounts, transactions, categories, insight, summary, search)
- `admin`: Admin features (about, configuration, currencies, users, preferences)
- `automation`: Automation (rules, recurrences, webhooks, transactions)

## Comparison with MCP Version

| Feature | MCP Version | CLI-Anything Version |
|------|----------|-------------------|
| Process Lifecycle | Long-running | Single call, immediate exit |
| Memory Usage | Continuous | On-demand, released after |
| Communication | Stdio/SSE | Command args + stdout |
| State Management | Stateful | Stateless |
| Preset Filtering | Supported | Supported |
| JSON Output | Built-in | `--json` flag |

## Troubleshooting

### Connection Failed

```
Error: Cannot connect to Firefly III instance: https://firefly.yourdomain.com
```

Check:
1. Is Firefly III instance running
2. Is base URL correct
3. Is network connection normal

### Authentication Failed

```
Error: Authentication failed: Personal Access Token is invalid
```

Check:
1. Is PAT correct
2. Has PAT expired
3. Generate new PAT in Firefly III Options > Profile > OAuth

## Development

```bash
# Clone repository
git clone https://github.com/HKUDS/CLI-Anything.git
cd CLI-Anything/firefly-iii/agent-harness

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting
black cli_anything/
```

## License

MIT License
