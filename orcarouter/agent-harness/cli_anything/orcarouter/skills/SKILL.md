---
name: >-
  cli-anything-orcarouter
description: >-
  Command-line interface for OrcaRouter - an OpenAI-compatible AI gateway with two authentication choices: an existing sk-orca- API key, or OAuth 2.0 + PKCE account sign-in.
---

# cli-anything-orcarouter

A CLI harness for **[OrcaRouter](https://www.orcarouter.ai)** — an
OpenAI-compatible AI gateway that routes many providers behind one endpoint.

Two explicit authentication choices, both producing the same durable OrcaRouter
API key:

- **OrcaRouter - API** (`auth api-key`) — paste an `sk-orca-…` key.
- **OrcaRouter - Auth** (`auth login`) — browser sign-in with your own
  OrcaRouter account, using OAuth 2.0 + PKCE.

## Installation

This CLI is installed as part of the cli-anything-orcarouter package:

```bash
pip install cli-anything-orcarouter
```

**Prerequisites:**
- Python 3.10+
- An OrcaRouter account or API key from [www.orcarouter.ai](https://www.orcarouter.ai)

## Usage

### Basic Commands

```bash
# Show help
cli-anything-orcarouter --help

# Start interactive REPL mode
cli-anything-orcarouter

# Store an existing API key
cli-anything-orcarouter auth api-key --api-key sk-orca-...

# Connect with an OrcaRouter account (OAuth 2.0 + PKCE)
cli-anything-orcarouter auth login

# One real request through the provider path
cli-anything-orcarouter test

# Chat
cli-anything-orcarouter chat --prompt "What is an AI gateway?" --model orcarouter/auto

# List models for the chat capability
cli-anything-orcarouter models

# JSON output (for agent consumption)
cli-anything-orcarouter --json models
```

### REPL Mode

When invoked without a subcommand, the CLI enters an interactive REPL session:

```bash
cli-anything-orcarouter
# Enter commands interactively with tab-completion and history
```

## Command Groups

### Auth

Two authentication choices, plus status and removal.

| Command | Description |
|---------|-------------|
| `api-key` | Store an existing OrcaRouter API key |
| `login` | Connect with OrcaRouter (OAuth 2.0 + PKCE) |
| `status` | Show the credential in use and its origin |
| `logout` | Remove the stored credential |

### Models

Catalog discovery, filtered by capability.

| Command | Description |
|---------|-------------|
| `models` | List models for one capability |
| `catalog` | Show catalog provenance (live vs verified fallback) |

### Inference

| Command | Description |
|---------|-------------|
| `chat` | One chat completion |
| `stream` | Streamed chat completion |
| `test` | One real request through the provider path |

### Utility

| Command | Description |
|---------|-------------|
| `ui` | Serve the loopback settings page |
| `config path` | Show the config file path |
| `config show` | Show stored configuration, key masked |

## Origins

| Purpose | Default | Override |
|---------|---------|----------|
| Authorization and exchange | `https://www.orcarouter.ai` | `ORCA_AUTH_BASE_URL` |
| Inference and model discovery | `https://api.orcarouter.ai/v1` | `ORCA_API_BASE_URL` |
| Both (self-hosted) | — | `ORCA_BASE_URL` |

## Credential Lifecycle

- The PKCE flow issues a durable API key, not a refresh token. There is no
  refresh grant; the stored key is reused until OrcaRouter revokes it.
- At most 10 PKCE-issued keys per user per 24 hours; re-authorizing on every
  launch will hit HTTP 429.
- Revoking the app at
  [the authorized-apps console](https://www.orcarouter.ai/console/authorized-apps)
  makes the next request return `401`. The harness marks exactly the rejected
  account generation as needing re-authentication.

## Model Capabilities

Options come from `GET {api_base}/models`. Filters fail closed:

| Entry point | Rule |
|-------------|------|
| chat / agent | must advertise `openai`, `anthropic`, `gemini` or `openai-response` |
| multimodal understanding | chat, **and** must declare the uploaded modality in `architecture.input_modalities` |
| embedding | `?capability=embedding` or an `embeddings` endpoint type |
| image generation | `?capability=image` or an `image-generation` endpoint type |
| video generation | `openai-video` endpoint type |
| rerank | `jina-rerank` endpoint type |

If live discovery fails, a small verified fallback list is shown and labelled
`degraded`; it is never merged into a successful live result.

## Output Formats

All commands support dual output modes:

- **Human-readable** (default): formatted text
- **Machine-readable** (`--json` flag): structured JSON for agent consumption

```bash
# Human output
cli-anything-orcarouter models

# JSON output for agents
cli-anything-orcarouter --json models
```

## For AI Agents

When using this CLI programmatically:

1. **Always use `--json` flag** for parseable output
2. **Check return codes** - 0 for success, non-zero for errors
3. **Parse stderr** for error messages on failure
4. **Never echo the API key** - `auth status` already prints a masked form
5. **Verify model capability** with `--json models --modalities image` before
   sending an image attachment

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin

## Version

1.0.0
