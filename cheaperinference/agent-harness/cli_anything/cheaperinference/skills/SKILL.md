---
name: >-
  cli-anything-cheaperinference
description: >-
  Command-line interface for Cheaper Inference - An OpenAI-compatible AI API client for GPT, Claude, DeepSeek, GLM, and other models.
---

# cli-anything-cheaperinference

A CLI harness for **Cheaper Inference** - an OpenAI-compatible API service for models like GPT, Claude, DeepSeek, GLM, and others.

## Installation

This CLI is installed as part of the cli-anything-cheaperinference package:

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=cheaperinference/agent-harness
```

**Prerequisites:**
- Python 3.10+
- Cheaper Inference API key from [cheaperinference.com](https://cheaperinference.com)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-cheaperinference --help

# Start interactive REPL mode
cli-anything-cheaperinference

# Chat with model
cli-anything-cheaperinference chat --prompt "What is AI?" --model gpt-5.4-mini

# Streaming chat
cli-anything-cheaperinference stream --prompt "Write a poem about code"

# List available models
cli-anything-cheaperinference models

# JSON output (for agent consumption)
cli-anything-cheaperinference --json chat --prompt "Hello"
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-cheaperinference
# Enter commands interactively with tab-completion and history
```

## Command Groups

### Chat

Chat with AI models through the Cheaper Inference API.

| Command | Description |
|---------|-------------|
| `chat` | Chat with the Cheaper Inference API |
| `stream` | Stream chat completion |

### Session

Session management for chat history.

| Command | Description |
|---------|-------------|
| `status` | Show session status |
| `clear` | Clear session history |
| `history` | Show command history |

### Config

Configuration management.

| Command | Description |
|---------|-------------|
| `set` | Set a configuration value (`api_key`, `default_model`) |
| `get` | Get a configuration value (or show all) |
| `delete` | Delete a configuration value |
| `path` | Show the config file path |

### Utility

| Command | Description |
|---------|-------------|
| `test` | Test API connectivity |
| `models` | List available models |

## Examples

### Configure API Key

```bash
# Set API key via config file (recommended)
cli-anything-cheaperinference config set api_key "ci_live_xxx"

# Or use environment variable
export CHEAPER_INFERENCE_API_KEY="ci_live_xxx"
```

### Chat

```bash
# Simple chat
cli-anything-cheaperinference chat --prompt "Explain quantum computing" --model claude-sonnet-5

# Streaming chat
cli-anything-cheaperinference stream --prompt "Write a Python function to calculate factorial"
```

### Test Connectivity

```bash
# Verify API key and connectivity
cli-anything-cheaperinference test --model gpt-5.4-mini

# List all available models
cli-anything-cheaperinference models
```

## Default Models

Model IDs are plain names without a provider prefix:

| Model ID | Provider | Description |
|----------|----------|-------------|
| `gpt-5.4-mini` | OpenAI | GPT-5.4 mini model (default) |
| `gpt-5.4` | OpenAI | GPT-5.4 model |
| `claude-sonnet-5` | Anthropic | Claude Sonnet 5 model |
| `deepseek-v4-flash` | DeepSeek | DeepSeek V4 Flash model |
| `glm-5.3` | Zhipu AI | GLM-5.3 model |

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-cheaperinference chat --prompt "Hello"

# JSON output for agents
cli-anything-cheaperinference --json chat --prompt "Hello"
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for all file operations
5. **Verify outputs exist** after export operations

## More Information

- Full documentation: See README.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0
