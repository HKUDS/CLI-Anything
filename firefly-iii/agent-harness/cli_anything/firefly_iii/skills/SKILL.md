---
name: "cli-anything-firefly-iii"
description: "Firefly III CLI - Personal finance management via CLI-Anything"
version: "2.0.0"
author: "CLI-Anything Community"
---

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

## Command Groups

| Command Group | Description | Corresponding API |
|--------------|-------------|-------------------|
| `accounts` | Account management (CRUD) | `/api/v1/accounts` |
| `transactions` | Transaction management (CRUD) | `/api/v1/transactions` |
| `budgets` | Budget management (CRUD + limits) | `/api/v1/budgets` |
| `categories` | Category management (CRUD) | `/api/v1/categories` |
| `tags` | Tag management (CRUD) | `/api/v1/tags` |
| `bills` | Bill management (CRUD) | `/api/v1/bills` |
| `piggy-banks` | Piggy bank management (CRUD + events) | `/api/v1/piggy-banks` |
| `autocomplete` | Autocomplete for various entities | `/api/v1/autocomplete/*` |
| `currencies` | Currency management (CRUD) | `/api/v1/currencies` |
| `recurrences` | Recurring transaction management (CRUD) | `/api/v1/recurrences` |
| `rules` | Rule management (CRUD + test/execute) | `/api/v1/rules` |
| `rule-groups` | Rule group management (CRUD + execute) | `/api/v1/rule-groups` |
| `summary` | Financial summaries | `/api/v1/summary/*` |
| `webhooks` | Webhook management (CRUD + trigger) | `/api/v1/webhooks` |
| `insights` | Insights and reports | `/api/v1/insight/*` |
| `search` | Search | `/api/v1/search/*` |
| `export` | Data export | `/api/v1/data/export/*` |
| `info` | System information | `/api/v1/about` |

## Usage Examples

### Account Management

```bash
# List all accounts
cli-anything-firefly-iii --json accounts list

# List asset accounts
cli-anything-firefly-iii --json accounts list --type asset

# Get account details
cli-anything-firefly-iii --json accounts get --id 123

# Create account
cli-anything-firefly-iii --json accounts create --name "Cash" --type asset --currency-code USD

# Update account
cli-anything-firefly-iii --json accounts update --id 123 --name "New Name"

# Delete account
cli-anything-firefly-iii accounts delete --id 123
```

### Transaction Management

```bash
# List transactions
cli-anything-firefly-iii --json transactions list --limit 10

# List transactions with date range
cli-anything-firefly-iii --json transactions list --start 2024-01-01 --end 2024-01-31

# Create transaction
cli-anything-firefly-iii --json transactions create \
  --description "Grocery" \
  --amount 50.00 \
  --source-account 1 \
  --category "Food"

# Update transaction
cli-anything-firefly-iii --json transactions update --id 456 --description "Updated"

# Delete transaction
cli-anything-firefly-iii transactions delete --id 456
```

### Budget Management

```bash
# List budgets
cli-anything-firefly-iii --json budgets list

# Get budget details
cli-anything-firefly-iii --json budgets get --id 1

# Create budget
cli-anything-firefly-iii --json budgets create --name "Monthly Budget"

# Update budget
cli-anything-firefly-iii --json budgets update --id 1 --name "New Budget Name"

# Delete budget
cli-anything-firefly-iii budgets delete --id 1

# List budget limits
cli-anything-firefly-iii --json budgets limits --budget-id 1

# Create budget limit
cli-anything-firefly-iii --json budgets limit-create --budget-id 1 --amount 1000 --start 2024-01-01 --end 2024-01-31

# Update budget limit
cli-anything-firefly-iii --json budgets limit-update --id 1 --amount 1500

# Delete budget limit
cli-anything-firefly-iii budgets limit-delete --id 1
```

### Category Management

```bash
# List categories
cli-anything-firefly-iii --json categories list

# Get category
cli-anything-firefly-iii --json categories get --id 1

# Create category
cli-anything-firefly-iii --json categories create --name "Food"

# Update category
cli-anything-firefly-iii --json categories update --id 1 --name "Food & Dining"

# Delete category
cli-anything-firefly-iii categories delete --id 1
```

### Tag Management

```bash
# List tags
cli-anything-firefly-iii --json tags list

# Get tag
cli-anything-firefly-iii --json tags get --id "uuid-here"

# Create tag
cli-anything-firefly-iii --json tags create --tag "important"

# Update tag
cli-anything-firefly-iii --json tags update --id "uuid-here" --tag "important-updated"

# Delete tag
cli-anything-firefly-iii tags delete --id "uuid-here"
```

### Bill Management

```bash
# List bills
cli-anything-firefly-iii --json bills list

# Get bill
cli-anything-firefly-iii --json bills get --id 1

# Create bill
cli-anything-firefly-iii --json bills create \
  --name "Netflix" \
  --amount-min 15.99 \
  --amount-max 15.99 \
  --frequency monthly

# Update bill
cli-anything-firefly-iii --json bills update --id 1 --amount-min 19.99

# Delete bill
cli-anything-firefly-iii bills delete --id 1
```

### Piggy Bank Management

```bash
# List piggy banks
cli-anything-firefly-iii --json piggy-banks list

# Get piggy bank
cli-anything-firefly-iii --json piggy-banks get --id 1

# Create piggy bank
cli-anything-firefly-iii --json piggy-banks create \
  --name "Vacation Fund" \
  --account-id 1 \
  --target-amount 5000

# Update piggy bank
cli-anything-firefly-iii --json piggy-banks update --id 1 --name "New Name"

# Delete piggy bank
cli-anything-firefly-iii piggy-banks delete --id 1

# List piggy bank events
cli-anything-firefly-iii --json piggy-banks events --id 1

# Add money to piggy bank
cli-anything-firefly-iii --json piggy-banks add-money --id 1 --amount 100
```

### Autocomplete

```bash
# Autocomplete accounts
cli-anything-firefly-iii --json autocomplete accounts --query "bank"

# Autocomplete categories
cli-anything-firefly-iii --json autocomplete categories --query "food"

# Autocomplete tags
cli-anything-firefly-iii --json autocomplete tags --query "important"

# Autocomplete transactions
cli-anything-firefly-iii --json autocomplete transactions --query "grocery"

# Autocomplete budgets
cli-anything-firefly-iii --json autocomplete budgets --query "monthly"

# Autocomplete bills
cli-anything-firefly-iii --json autocomplete bills --query "netflix"

# Autocomplete piggy banks
cli-anything-firefly-iii --json autocomplete piggy-banks --query "vacation"

# Autocomplete currencies
cli-anything-firefly-iii --json autocomplete currencies --query "dollar"

# Autocomplete rules
cli-anything-firefly-iii --json autocomplete rules --query "auto"

# Autocomplete rule groups
cli-anything-firefly-iii --json autocomplete rule-groups --query "finances"

# Autocomplete recurring
cli-anything-firefly-iii --json autocomplete recurring --query "rent"

# Autocomplete object groups
cli-anything-firefly-iii --json autocomplete object-groups --query "group"

# Autocomplete transaction types
cli-anything-firefly-iii --json autocomplete transaction-types --query "with"
```

### Currency Management

```bash
# List currencies
cli-anything-firefly-iii --json currencies list

# Get currency
cli-anything-firefly-iii --json currencies get --id 1

# Create currency
cli-anything-firefly-iii --json currencies create \
  --code "CNY" \
  --name "Chinese Yuan" \
  --symbol "¥"

# Update currency
cli-anything-firefly-iii --json currencies update --id 1 --symbol "元"

# Delete currency
cli-anything-firefly-iii currencies delete --id 1

# Get exchange rates
cli-anything-firefly-iii --json currencies exchange-rates --from USD --to EUR
```

### Recurring Transaction Management

```bash
# List recurring transactions
cli-anything-firefly-iii --json recurrences list

# Get recurring transaction
cli-anything-firefly-iii --json recurrences get --id 1

# Create recurring transaction
cli-anything-firefly-iii --json recurrences create \
  --title "Rent Payment" \
  --type withdrawal \
  --amount 1500 \
  --source-account 1 \
  --destination-account 2 \
  --frequency monthly

# Update recurring transaction
cli-anything-firefly-iii --json recurrences update --id 1 --amount 1600

# Delete recurring transaction
cli-anything-firefly-iii recurrences delete --id 1
```

### Rule Management

```bash
# List rules
cli-anything-firefly-iii --json rules list

# Get rule
cli-anything-firefly-iii --json rules get --id 1

# Create rule
cli-anything-firefly-iii --json rules create \
  --title "Auto-tag groceries" \
  --trigger "description_contains" \
  --value "grocery" \
  --action set_category \
  --action-value "Food"

# Update rule
cli-anything-firefly-iii --json rules update --id 1 --title "New Title"

# Delete rule
cli-anything-firefly-iii rules delete --id 1

# Test rule
cli-anything-firefly-iii --json rules test --id 1

# Execute rule
cli-anything-firefly-iii --json rules execute --id 1
```

### Rule Group Management

```bash
# List rule groups
cli-anything-firefly-iii --json rule-groups list

# Get rule group
cli-anything-firefly-iii --json rule-groups get --id 1

# Create rule group
cli-anything-firefly-iii --json rule-groups create --title "Finance Rules"

# Update rule group
cli-anything-firefly-iii --json rule-groups update --id 1 --title "New Title"

# Delete rule group
cli-anything-firefly-iii rule-groups delete --id 1

# Execute rule group
cli-anything-firefly-iii --json rule-groups execute --id 1
```

### Summary Reports

```bash
# Default summary set
cli-anything-firefly-iii --json summary default-set --start 2024-01-01 --end 2024-01-31

# Account summary
cli-anything-firefly-iii --json summary account-summary --start 2024-01-01 --end 2024-01-31

# Available budget summary
cli-anything-firefly-iii --json summary available-budget --start 2024-01-01 --end 2024-01-31

# Bill summary
cli-anything-firefly-iii --json summary bill-summary --start 2024-01-01 --end 2024-01-31

# Budget summary
cli-anything-firefly-iii --json summary budget-summary --start 2024-01-01 --end 2024-01-31

# Category summary
cli-anything-firefly-iii --json summary category-summary --start 2024-01-01 --end 2024-01-31

# Tag summary
cli-anything-firefly-iii --json summary tag-summary --start 2024-01-01 --end 2024-01-31

# Transfer summary
cli-anything-firefly-iii --json summary transfer-summary --start 2024-01-01 --end 2024-01-31
```

### Webhook Management

```bash
# List webhooks
cli-anything-firefly-iii --json webhooks list

# Get webhook
cli-anything-firefly-iii --json webhooks get --id 1

# Create webhook
cli-anything-firefly-iii --json webhooks create \
  --title "My Webhook" \
  --trigger create \
  --url "https://example.com/webhook" \
  --secret "my-secret"

# Update webhook
cli-anything-firefly-iii --json webhooks update --id 1 --title "New Title"

# Delete webhook
cli-anything-firefly-iii webhooks delete --id 1

# Trigger webhook manually
cli-anything-firefly-iii --json webhooks trigger --id 1
```

### Insights and Reports

```bash
# Expense report (by category)
cli-anything-firefly-iii --json insights expense \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --group-by category

# Income report
cli-anything-firefly-iii --json insights income \
  --start 2024-01-01 \
  --end 2024-01-31

# Transfer insights
cli-anything-firefly-iii --json insights transfer \
  --start 2024-01-01 \
  --end 2024-01-31

# Account overview
cli-anything-firefly-iii --json insights overview \
  --start 2024-01-01 \
  --end 2024-01-31
```

### Search

```bash
# Search transactions
cli-anything-firefly-iii --json search transactions --query "grocery"
```

### Data Export

```bash
# Export transactions
cli-anything-firefly-iii --json export transactions \
  --start 2024-01-01 \
  --end 2024-01-31

# Export accounts
cli-anything-firefly-iii --json export accounts

# Export budgets
cli-anything-firefly-iii --json export budgets

# Export categories
cli-anything-firefly-iii --json export categories
```

### System Information

```bash
# System information
cli-anything-firefly-iii --json info about

# Connection status
cli-anything-firefly-iii info status
```

## Preset Filtering

Use `--preset` parameter to filter available commands:

```bash
# Default preset
cli-anything-firefly-iii --preset default accounts list

# Full preset
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

## Agent Guidelines

### Basic Usage

1. **Use `--json` for structured output**: All commands support `--json` flag, returning JSON format data
2. **Call `info status` first to check connection**: Confirm Firefly III connection is normal before executing operations
3. **Use presets to reduce command count**: Filter unnecessary commands via `--preset`

### Common Workflows

#### View Account Balances

```bash
# 1. Check connection
cli-anything-firefly-iii info status

# 2. List asset accounts
cli-anything-firefly-iii --json accounts list --type asset

# 3. View account details (get balance)
cli-anything-firefly-iii --json accounts get --id <account_id>
```

#### Record Expense

```bash
# 1. Find expense accounts
cli-anything-firefly-iii --json accounts list --type expense

# 2. Create transaction
cli-anything-firefly-iii --json transactions create \
  --description "Lunch" \
  --amount 15.50 \
  --source-account <asset_account_id> \
  --destination-account <expense_account_id> \
  --category "Food"
```

#### Set Up Recurring Budget

```bash
# 1. Create budget
cli-anything-firefly-iii --json budgets create --name "Monthly Groceries"

# 2. Set budget limit
cli-anything-firefly-iii --json budgets limit-create \
  --budget-id <budget_id> \
  --amount 500 \
  --start 2024-01-01 \
  --end 2024-01-31
```

#### Create Automation Rule

```bash
# 1. List rule groups
cli-anything-firefly-iii --json rule-groups list

# 2. Create rule
cli-anything-firefly-iii --json rules create \
  --title "Auto-tag groceries" \
  --trigger description_contains \
  --value "grocery" \
  --action set_category \
  --action-value "Food"

# 3. Execute rule to apply to existing transactions
cli-anything-firefly-iii --json rules execute --id <rule_id>
```

#### Monthly Financial Report

```bash
# 1. Expense report
cli-anything-firefly-iii --json insights expense \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --group-by category

# 2. Income report
cli-anything-firefly-iii --json insights income \
  --start 2024-01-01 \
  --end 2024-01-31

# 3. Budget summary
cli-anything-firefly-iii --json summary budget-summary \
  --start 2024-01-01 \
  --end 2024-01-31

# 4. Export data
cli-anything-firefly-iii --json export transactions \
  --start 2024-01-01 \
  --end 2024-01-31
```

### Error Handling

Common errors and solutions:

1. **Connection failed**: Check if FIREFLY_III_BASE_URL is correct
2. **Authentication failed**: Check if FIREFLY_III_PAT is valid
3. **Resource not found**: Check if ID is correct
4. **Parameter error**: Check if required parameters are provided
5. **Validation error**: Check API documentation for valid parameter values

### Best Practices

1. **Use environment variables for credentials**: Avoid exposing PAT in command line
2. **Use `--json` for scripting**: Facilitates parsing and processing output
3. **Use presets to control permissions**: Choose appropriate preset based on scenario
4. **Query before modifying**: Avoid accidental operations
5. **Use autocomplete for quick lookups**: Great for finding existing entities

## Troubleshooting

### Connection Issues

```
Error: Cannot connect to Firefly III instance
```

- Check if Firefly III instance is running
- Check network connection
- Check if base URL is correct

### Authentication Issues

```
Error: Authentication failed: Personal Access Token is invalid
```

- Check if PAT is correct
- Generate new PAT in Firefly III Options > Profile > OAuth
- Ensure PAT has not expired

### Parameter Validation Errors

```
Error: Request parameter error: [details]
```

- Check required parameters are provided
- Verify date formats (YYYY-MM-DD)
- Verify currency codes (ISO 4217)
- Verify enum values match allowed choices

## Comparison with MCP Version

| Feature | MCP Version | CLI-Anything Version |
|---------|------------|---------------------|
| Process Lifecycle | Long-running | Single call, immediate exit |
| Memory Usage | Continuous | On-demand, released after |
| Communication | Stdio/SSE | Command args + stdout |
| State Management | Stateful | Stateless |
| Preset Filtering | Supported | Supported |
| JSON Output | Built-in | `--json` flag |
| Full API Coverage | Partial | Full API coverage |

## API Coverage

This CLI covers the following Firefly III API endpoints:

- [x] `/api/v1/about` - System information
- [x] `/api/v1/accounts` - Account management (full CRUD)
- [x] `/api/v1/transactions` - Transaction management (full CRUD)
- [x] `/api/v1/budgets` - Budget management (full CRUD + limits)
- [x] `/api/v1/categories` - Category management (full CRUD)
- [x] `/api/v1/tags` - Tag management (full CRUD)
- [x] `/api/v1/bills` - Bill management (full CRUD)
- [x] `/api/v1/piggy-banks` - Piggy bank management (full CRUD + events)
- [x] `/api/v1/autocomplete/*` - All autocomplete endpoints
- [x] `/api/v1/currencies` - Currency management (full CRUD)
- [x] `/api/v1/recurrences` - Recurring transaction management (full CRUD)
- [x] `/api/v1/rules` - Rule management (full CRUD + test/execute)
- [x] `/api/v1/rule-groups` - Rule group management (full CRUD + execute)
- [x] `/api/v1/summary/*` - Summary endpoints
- [x] `/api/v1/webhooks` - Webhook management (full CRUD + trigger)
- [x] `/api/v1/insight/*` - Insight endpoints
- [x] `/api/v1/search/*` - Search endpoints
- [x] `/api/v1/data/export/*` - Export endpoints
- [x] `/api/v1/chart/*` - Chart endpoints
- [x] `/api/v1/configuration` - Configuration
- [x] `/api/v1/preferences` - User preferences
- [x] `/api/v1/available_budgets` - Available budgets
- [x] `/api/v1/object-groups` - Object groups
- [x] `/api/v1/links` - Transaction links
- [x] `/api/v1/attachments` - Attachments
- [x] `/api/v1/currency_exchange_rates` - Exchange rates
- [x] `/api/v1/data/bulk` - Bulk operations
- [x] `/api/v1/user-groups` - User groups (read-only)
- [x] `/api/v1/users` - User management (admin)

## License

MIT License
