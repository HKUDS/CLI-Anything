# cli-anything-minimax

CLI harness for **MiniMax AI** — chat and text-to-speech via the MiniMax API.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=minimax/agent-harness
```

## Prerequisites

- Python 3.10+
- MiniMax API key from [platform.minimax.io](https://platform.minimax.io)

## Quick Start

```bash
export MINIMAX_API_KEY="your-api-key"
cli-anything-minimax chat --prompt "Hello!"
cli-anything-minimax tts --text "Hello world" --output hello.mp3
```

## Usage

### Chat

```bash
# Simple chat (default model: MiniMax-M2.7)
cli-anything-minimax chat --prompt "Explain quantum computing"

# High-speed model
cli-anything-minimax chat --prompt "Quick answer please" --model MiniMax-M2.7-highspeed

# Streaming output
cli-anything-minimax stream --prompt "Write a haiku about AI"

# JSON output for agents
cli-anything-minimax --json chat --prompt "Hello"
```

### TTS

```bash
# Synthesize speech (default model: speech-2.8-hd, default voice: English_Graceful_Lady)
cli-anything-minimax tts --text "Hello, world!" --output hello.mp3

# Use turbo model
cli-anything-minimax tts --text "Fast speech" --model speech-2.8-turbo --output fast.mp3

# List available voices
cli-anything-minimax voices
```

### Session & Config

```bash
# Session management
cli-anything-minimax session status
cli-anything-minimax session clear

# Configuration
cli-anything-minimax config set api_key "your-key"
cli-anything-minimax config get

# Test connectivity
cli-anything-minimax test

# List models
cli-anything-minimax models
cli-anything-minimax models --tts
```

## Models

### Chat

| Model | Description |
|-------|-------------|
| `MiniMax-M2.7` | Peak Performance. Ultimate Value. (default) |
| `MiniMax-M2.7-highspeed` | Same performance, faster and more agile |

### TTS

| Model | Description |
|-------|-------------|
| `speech-2.8-hd` | High-definition TTS (default) |
| `speech-2.8-turbo` | Fast TTS |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MINIMAX_API_KEY` | MiniMax API key (required) |
| `MINIMAX_BASE_URL` | Override API base URL (optional) |
