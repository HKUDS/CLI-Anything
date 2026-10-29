# Cheaper Inference CLI

A CLI harness for **Cheaper Inference** - an OpenAI-compatible API service for models like GPT, Claude, DeepSeek, GLM, and others.

## Prerequisites

- Python 3.10+
- `requests` (HTTP client)
- `click` (CLI framework)
- Cheaper Inference API key

Optional (for interactive REPL):
- `prompt_toolkit`

## Install Dependencies

```bash
pip install requests click prompt_toolkit
```

## Get an API Key

1. Go to [cheaperinference.com](https://cheaperinference.com) and sign up
2. Create an API key (format: `ci_live_xxx`)
3. Configure it:

```bash
# Option 1: Config file (recommended)
cli-anything-cheaperinference config set api_key "ci_live_xxx"

# Option 2: Environment variable
export CHEAPER_INFERENCE_API_KEY="ci_live_xxx"
```

The default API base is `https://api.cheaperinference.com/v1`.
Set `CHEAPER_INFERENCE_API_BASE` to use a different base URL.

## How to Run

All commands are run from the `agent-harness/` directory or via the installed command.

### One-shot Commands

```bash
# Show help
cli-anything-cheaperinference --help

# Chat with model
cli-anything-cheaperinference chat --prompt "What is AI?" --model gpt-5.4-mini

# Streaming chat
cli-anything-cheaperinference stream --prompt "Write a poem about code"

# Test connectivity
cli-anything-cheaperinference test --model gpt-5.4-mini

# List available models
cli-anything-cheaperinference models

# JSON output for agent consumption
cli-anything-cheaperinference --json chat --prompt "Hello" --model gpt-5.4-mini
```

### Interactive REPL

```bash
cli-anything-cheaperinference
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
config set api_key "ci_live_xxx"
config set default_model "gpt-5.4-mini"
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
cli-anything-cheaperinference --json chat --prompt "Hello"
cli-anything-cheaperinference --json session status
```

## Default Models

Model IDs are plain names without a provider prefix:

- `gpt-5.4-mini` (default)
- `gpt-5.4`
- `claude-sonnet-5`
- `deepseek-v4-flash`
- `glm-5.3`

Run `cli-anything-cheaperinference models` for the full list.

## Running Tests

```bash
cd agent-harness

# Unit tests (mock HTTP, no API key needed)
python3 -m pytest cli_anything/cheaperinference/tests/test_core.py -v

# E2E tests (requires CHEAPER_INFERENCE_API_KEY, skipped without it)
CHEAPER_INFERENCE_API_KEY=ci_live_xxx python3 -m pytest cli_anything/cheaperinference/tests/test_full_e2e.py -v

# All tests
python3 -m pytest cli_anything/cheaperinference/tests/ -v
```

## Example Workflow

```bash
# Configure API key
cli-anything-cheaperinference config set api_key "ci_live_xxx"

# Chat with a model
cli-anything-cheaperinference chat --prompt "Explain quantum computing" --model claude-sonnet-5

# Stream response
cli-anything-cheaperinference stream --prompt "Write a Python function to calculate factorial"

# Test connectivity
cli-anything-cheaperinference test --model gpt-5.4-mini

# List available models
cli-anything-cheaperinference models
```

## Supported Models

| Model ID | Provider | Description |
|----------|----------|-------------|
| `gpt-5.4-mini` | OpenAI | GPT-5.4 mini model |
| `gpt-5.4` | OpenAI | GPT-5.4 model |
| `claude-sonnet-5` | Anthropic | Claude Sonnet 5 model |
| `deepseek-v4-flash` | DeepSeek | DeepSeek V4 Flash model |
| `glm-5.3` | Zhipu AI | GLM-5.3 model |

## License

MIT License
