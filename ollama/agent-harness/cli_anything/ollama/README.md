# Ollama CLI

A command-line interface for local LLM inference and model management via the Ollama REST API.
Designed for AI agents and power users who need to manage models, generate text, and chat without a GUI.

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- `click` (CLI framework)
- `requests` (HTTP client)

Optional (for interactive REPL):
- `prompt_toolkit`

## Install Dependencies

```bash
pip install click requests prompt_toolkit
```

## How to Run

All commands are run from the `agent-harness/` directory, or via the installed entry point.

### One-shot commands

```bash
# Show help
cli-anything-ollama --help

# List models
cli-anything-ollama model list

# Pull a model
cli-anything-ollama model pull llama3.2

# Generate text
cli-anything-ollama generate text --model llama3.2 --prompt "Explain quantum computing"

# Chat
cli-anything-ollama generate chat --model llama3.2 --message "user:Hello!"

# JSON output (for agent consumption)
cli-anything-ollama --json server status
```

### Interactive REPL

```bash
cli-anything-ollama
# Enter commands interactively with tab-completion and history
```

Inside the REPL, type `help` for all available commands.

## Command Reference

### Model

```bash
model list                              # List locally available models
model show <name>                       # Show model details
model pull <name> [--no-stream]         # Download a model
model rm <name>                         # Delete a model
model copy <source> <destination>       # Copy a model
model ps                                # List currently loaded models
```

### Generate

```bash
generate text --model <name> --prompt "..." [--system "..."] [--no-stream]
              [--temperature 0.7] [--top-p 0.9] [--num-predict 256]

generate chat --model <name> --message "user:Hello" [--message "assistant:Hi"]
              [--file messages.json] [--no-stream] [--continue-chat]
```

### Embed

```bash
embed text --model <name> --input "Text to embed"
```

### Server

```bash
server status                           # Check if Ollama is running
server version                          # Show Ollama version
```

### Session

```bash
session status                          # Show session state
session history                         # Show chat history
```

## JSON Mode

Add `--json` before the subcommand for machine-readable output:

```bash
cli-anything-ollama --json model list
cli-anything-ollama --json generate text --model llama3.2 --prompt "Hello"
```

## Custom Host

Connect to a remote Ollama instance:

```bash
cli-anything-ollama --host http://192.168.1.100:11434 model list
```

## Example Workflow

```bash
# Check server
cli-anything-ollama server status

# Pull a model
cli-anything-ollama model pull llama3.2

# Generate text
cli-anything-ollama generate text --model llama3.2 --prompt "Write a haiku about coding"

# Multi-turn chat
cli-anything-ollama generate chat --model llama3.2 \
  --message "user:What is Python?" \
  --message "user:How does it compare to JavaScript?"

# Generate embeddings
cli-anything-ollama embed text --model nomic-embed-text --input "Hello world"

# Check loaded models
cli-anything-ollama model ps

# Clean up
cli-anything-ollama model rm llama3.2
```

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): Tables, colors, formatted text
- **Machine-readable** (`--json` flag): Structured JSON for agent consumption

```bash
# Human output
cli-anything-ollama model list

# JSON output for agents
cli-anything-ollama --json model list
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use `--no-stream`** for generate/chat to get complete responses
5. **Verify Ollama is running** with `server status` before other commands

## Running Tests

```bash
cd agent-harness
python -m pytest cli_anything/ollama/tests/test_core.py -v        # Unit tests (no Ollama needed)
python -m pytest cli_anything/ollama/tests/test_full_e2e.py -v    # E2E tests (requires Ollama)
python -m pytest cli_anything/ollama/tests/ -v                     # All tests
```

## Version

1.0.1
