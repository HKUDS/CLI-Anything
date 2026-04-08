# Novita CLI

A CLI harness for **Novita AI** - an OpenAI-compatible API service for AI models like DeepSeek, GLM, and others.

## Prerequisites

- Python 3.10+
- `requests` (HTTP client)
- `click` (CLI framework)
- Novita API key

Optional (for interactive REPL):
- `prompt_toolkit`

## Install Dependencies

```bash
pip install requests click prompt_toolkit
```

## Get an API Key

1. Go to [novita.ai](https://novita.ai) and sign up
2. Navigate to Settings → API Keys
3. Create an API key (format: `sk-xxx`)
4. Configure it:

```bash
# Option 1: Config file (recommended)
cli-anything-novita config set api_key "sk-xxx"

# Option 2: Environment variable
export NOVITA_API_KEY="sk-xxx"
```

## How to Run

All commands are run from the `agent-harness/` directory or via the installed command.

### One-shot Commands

```bash
# Show help
cli-anything-novita --help

# Chat with model
cli-anything-novita chat --prompt "What is AI?" --model deepseek/deepseek-v3.2

# Streaming chat
cli-anything-novita stream --prompt "Write a poem about code"

# Test connectivity
cli-anything-novita test --model deepseek/deepseek-v3.2

# List available models
cli-anything-novita models

# JSON output for agent consumption
cli-anything-novita --json chat --prompt "Hello" --model deepseek/deepseek-v3.2
```

### Interactive REPL

```bash
cli-anything-novita
```

Inside the REPL, type `help` for all available commands.

## Command Reference

### Chat

```bash
chat --prompt <text> [--model <id>] [--temperature <0.0-1.0>] [--max-tokens <n>]
stream --prompt <text> [--model <id>] [--temperature <0.0-1.0>] [--max-tokens <n>]
```

### Session

```bash
session status
session clear
session history [--limit N]
```

### Config

```bash
config set api_key "sk-xxx"
config set default_model "deepseek/deepseek-v3.2"
config get [key]
config delete <key>
config path
```

### Utility

```bash
test [--model <id>]  # Test API connectivity
models              # List available models
```

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
cli-anything-novita --json chat --prompt "Hello"
cli-anything-novita --json session status
```

## Default Models

The CLI supports multiple models with `/` separator (not `-`):

- `deepseek/deepseek-v3.2` (default)
- `zai-org/glm-5`
- `minimax/minimax-m2.5`

## Running Tests

```bash
cd agent-harness

# Unit tests (mock HTTP, no API key needed)
python3 -m pytest cli_anything/novita/tests/test_core.py -v

# E2E tests (requires NOVITA_API_KEY)
NOVITA_API_KEY=sk-xxx python3 -m pytest cli_anything/novita/tests/test_full_e2e.py -v

# All tests
python3 -m pytest cli_anything/novita/tests/ -v
```

## Example Workflow

```bash
# Configure API key
cli-anything-novita config set api_key "sk-xxx"

# Chat with DeepSeek model
cli-anything-novita chat --prompt "Explain quantum computing" --model deepseek/deepseek-v3.2

# Stream response
cli-anything-novita stream --prompt "Write a Python function to calculate factorial"

# Test connectivity
cli-anything-novita test --model deepseek/deepseek-v3.2

# List available models
cli-anything-novita models
```

## Supported Models

| Model ID | Provider | Description |
|----------|----------|-------------|
| `deepseek/deepseek-v3.2` | DeepSeek | DeepSeek V3.2 model |
| `zai-org/glm-5` | Zhipu AI | GLM-5 model |
| `minimax/minimax-m2.5` | MiniMax | MiniMax M2.5 model |

## License

MIT License
