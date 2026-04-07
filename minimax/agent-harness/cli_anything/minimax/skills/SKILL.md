---
name: >-
  cli-anything-minimax
description: >-
  Command-line interface for MiniMax AI — chat (MiniMax-M2.7) and TTS (speech-2.8-hd) via the MiniMax API.
---

# cli-anything-minimax

A CLI harness for **MiniMax AI** — providing chat completions and text-to-speech synthesis through the MiniMax API.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=minimax/agent-harness
```

**Prerequisites:**
- Python 3.10+
- MiniMax API key from [platform.minimax.io](https://platform.minimax.io)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-minimax --help

# Start interactive REPL
cli-anything-minimax

# Chat with MiniMax-M2.7
cli-anything-minimax chat --prompt "What is AI?"

# High-speed model
cli-anything-minimax chat --prompt "Quick answer" --model MiniMax-M2.7-highspeed

# Stream chat response
cli-anything-minimax stream --prompt "Write a poem about code"

# Synthesize speech
cli-anything-minimax tts --text "Hello world" --output hello.mp3

# JSON output for agents
cli-anything-minimax --json chat --prompt "Hello"
```

## Command Groups

### Chat

| Command | Description |
|---------|-------------|
| `chat` | Chat with MiniMax LLM |
| `stream` | Stream chat completion |

### TTS

| Command | Description |
|---------|-------------|
| `tts` | Synthesize text to speech (hex-decoded MP3 via SSE) |
| `voices` | List available voice IDs |

### Session

| Command | Description |
|---------|-------------|
| `session status` | Show session status |
| `session clear` | Clear session history |
| `session history` | Show command history |

### Config

| Command | Description |
|---------|-------------|
| `config set` | Set a configuration value |
| `config get` | Get a configuration value (or show all) |
| `config delete` | Delete a configuration value |
| `config path` | Show the config file path |

### Utility

| Command | Description |
|---------|-------------|
| `test` | Test API connectivity |
| `models` | List chat models |
| `models --tts` | List TTS models |

## Examples

### Configure API Key

```bash
export MINIMAX_API_KEY="your-api-key"
# or
cli-anything-minimax config set api_key "your-api-key"
```

### Chat

```bash
cli-anything-minimax chat --prompt "Explain quantum computing"
cli-anything-minimax stream --prompt "Write a Python quicksort"
```

### TTS

```bash
cli-anything-minimax tts --text "Hello!" --output hello.mp3
cli-anything-minimax tts --text "Fast" --model speech-2.8-turbo --voice English_Insightful_Speaker --output fast.mp3
```

## Chat Models

| Model ID | Description |
|----------|-------------|
| `MiniMax-M2.7` | Peak Performance. Ultimate Value. (default) |
| `MiniMax-M2.7-highspeed` | Same performance, faster and more agile |

## TTS Models

| Model ID | Description |
|----------|-------------|
| `speech-2.8-hd` | High-definition TTS (default) |
| `speech-2.8-turbo` | Fast TTS |

## For AI Agents

1. **Always use `--json` flag** for parseable output
2. **Check return codes** — 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Use absolute paths** for TTS output files

## Version

1.0.0
