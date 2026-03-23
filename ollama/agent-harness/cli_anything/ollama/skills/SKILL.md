---
name: >-
  cli-anything-ollama
description: >-
  Command-line interface for Ollama - Local LLM inference and model management via Ollama REST API. Designed for AI agents and power users who need to manage models, generate text, chat, and create embeddings without a GUI.
---

# cli-anything-ollama

Local LLM inference and model management via the Ollama REST API. Designed for AI agents and power users who need to manage models, generate text, chat, and create embeddings without a GUI.

## Installation

This CLI is installed as part of the cli-anything-ollama package:

```bash
pip install cli-anything-ollama
```

**Prerequisites:**
- Python 3.10+
- Ollama must be installed and running (`ollama serve`)


## Usage

### Basic Commands

```bash
# Show help
cli-anything-ollama --help

# Start interactive REPL mode
cli-anything-ollama

# List available models
cli-anything-ollama model list

# Run with JSON output (for agent consumption)
cli-anything-ollama --json model list
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-ollama
# Enter commands interactively with tab-completion and history
```


## Command Groups


### Model

Model management commands.

| Command | Description |
|---------|-------------|
| `list` | List locally available models |
| `show` | Show model details (parameters, template, license) |
| `pull` | Download a model from the Ollama library |
| `rm` | Delete a model from local storage |
| `copy` | Copy a model to a new name |
| `ps` | List models currently loaded in memory |


### Generate

Text generation and chat commands.

| Command | Description |
|---------|-------------|
| `text` | Generate text from a prompt |
| `chat` | Send a chat completion request |


### Embed

Embedding generation commands.

| Command | Description |
|---------|-------------|
| `text` | Generate embeddings for text |


### Server

Server status and info commands.

| Command | Description |
|---------|-------------|
| `status` | Check if Ollama server is running |
| `version` | Show Ollama server version |


### Session

Session state commands.

| Command | Description |
|---------|-------------|
| `status` | Show current session state |
| `history` | Show chat history for current session |



## Examples


### List and Pull Models

```bash
# List available models
cli-anything-ollama model list

# Pull a model
cli-anything-ollama model pull llama3.2

# Show model details
cli-anything-ollama model show llama3.2
```


### Generate Text

```bash
# Stream text (default)
cli-anything-ollama generate text --model llama3.2 --prompt "Explain quantum computing in one sentence"

# Non-streaming with JSON output (for agents)
cli-anything-ollama --json generate text --model llama3.2 --prompt "Hello" --no-stream
```


### Chat

```bash
# Single-turn chat
cli-anything-ollama generate chat --model llama3.2 --message "user:What is Python?"

# Multi-turn chat
cli-anything-ollama generate chat --model llama3.2 \
  --message "user:What is Python?" \
  --message "user:How does it compare to JavaScript?"

# Chat from JSON file
cli-anything-ollama generate chat --model llama3.2 --file messages.json
```


### Embeddings

```bash
cli-anything-ollama embed text --model nomic-embed-text --input "Hello world"
cli-anything-ollama embed text --model nomic-embed-text --input "Hello" --input "World"
```


### Interactive REPL Session

Start an interactive session for exploratory use.

```bash
cli-anything-ollama
# Enter commands interactively
# Use 'help' to see available commands
```


### Connect to Remote Host

```bash
cli-anything-ollama --host http://192.168.1.100:11434 model list
```


## State Management

The CLI maintains lightweight session state:

- **Current host URL**: Configurable via `--host`
- **Chat history**: Tracked for multi-turn conversations in REPL
- **Last used model**: Shown in REPL prompt

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

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.1
