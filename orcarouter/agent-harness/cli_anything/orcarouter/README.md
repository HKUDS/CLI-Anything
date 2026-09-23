# OrcaRouter CLI - Agent Harness

A CLI harness for **[OrcaRouter](https://www.orcarouter.ai)** — an
OpenAI-compatible AI gateway that routes many providers behind one endpoint.

Two explicit authentication choices, both producing the same durable
OrcaRouter API key:

| Choice | Command | Credential source |
|--------|---------|-------------------|
| **OrcaRouter - API** | `auth api-key` | You paste an `sk-orca-…` key you already created. |
| **OrcaRouter - Auth** | `auth login` | Browser sign-in with your own OrcaRouter account (OAuth 2.0 + PKCE). |

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=orcarouter/agent-harness
```

Or for local development:

```bash
cd orcarouter/agent-harness
pip install -e ".[dev]"
```

**Requirements:** Python 3.10+, `click`, `prompt-toolkit`. No third-party HTTP
library is needed — the client uses the standard library.

## Origins

| Purpose | Default | Override |
|---------|---------|----------|
| Authorization and code exchange | `https://www.orcarouter.ai` | `ORCA_AUTH_BASE_URL` |
| Inference and model discovery | `https://api.orcarouter.ai/v1` | `ORCA_API_BASE_URL` |
| Both (self-hosted, one origin) | — | `ORCA_BASE_URL` |

Explicit `ORCA_AUTH_BASE_URL` / `ORCA_API_BASE_URL` take precedence over the
shared `ORCA_BASE_URL`. Non-loopback origins must be HTTPS.

## Authentication

### Choice 1 — an existing API key

```bash
# Store a key (written to ~/.config/cli-anything-orcarouter/config.json, mode 0600)
cli-anything-orcarouter auth api-key --api-key sk-orca-...

# Or keep it out of the config file entirely
export ORCAROUTER_API_KEY=sk-orca-...
```

Create keys at <https://www.orcarouter.ai>.

### Choice 2 — Connect with OrcaRouter (OAuth 2.0 + PKCE)

```bash
# Loopback redirect: a browser opens, you approve once, the code comes back
cli-anything-orcarouter auth login

# Out-of-band: for SSH sessions, containers and machines with no browser
cli-anything-orcarouter auth login --oob
```

No client secret is involved and there is no redirect URI to pre-register. The
flow sends `code_challenge_method=S256` with a fresh verifier per attempt; the
verifier never leaves the process and is never logged.

### Credential lifecycle

- The PKCE flow returns a **durable OrcaRouter API key**, not a refresh token.
  There is no refresh grant, and none is attempted. The stored key is reused
  until OrcaRouter revokes it.
- Re-authorizing on every launch will hit the cap of **10 PKCE-issued keys per
  user per 24 hours** (HTTP 429). Store the key once.
- Revoking the app at
  <https://www.orcarouter.ai/console/authorized-apps> deletes every key it was
  issued. The next request returns `401`; the harness marks exactly the stored
  account generation that made the rejected request as `needs_reauth` and tells
  you to sign in again — it does not loop or fake a refresh.

```bash
cli-anything-orcarouter auth status    # which credential is in use, and where from
cli-anything-orcarouter auth logout    # remove the stored credential
```

## Models

The model list comes from the live catalog at `{api_base}/models`, requested
with your own key so it reflects the models your workspace can call. Model IDs
keep their `vendor/model` namespace exactly as returned.

```bash
cli-anything-orcarouter models                       # chat models
cli-anything-orcarouter models --capability embedding
cli-anything-orcarouter models --capability image
cli-anything-orcarouter models --modalities image    # chat models that declare image input
cli-anything-orcarouter catalog                      # live vs verified fallback
```

Filters fail closed. A chat model must advertise one of
`openai` / `anthropic` / `gemini` / `openai-response`; a model that only
declares `image-generation`, `openai-video`, `jina-rerank` or `embeddings` is
never offered in the chat list. Multimodal entry points additionally require
the model to declare the modality being uploaded.

If live discovery fails, the harness falls back to a small verified seed
(`openai/gpt-5.5`, `anthropic/claude-opus-4.8`, `google/gemini-3.5-flash`,
`deepseek/deepseek-v4-pro`, `orcarouter/auto`) and labels the result
`degraded`. A successful live fetch is authoritative and is never mixed with
the seed.

## Usage

```bash
# One real request through the provider path
cli-anything-orcarouter test

# Chat
cli-anything-orcarouter chat --prompt "Explain what a gateway does" --model orcarouter/auto

# Stream
cli-anything-orcarouter stream --prompt "Write a haiku about routing"

# Attach an image (the selected model must declare image input)
cli-anything-orcarouter chat --prompt "What is in this screenshot?" --image shot.png

# Machine-readable output
cli-anything-orcarouter --json models
cli-anything-orcarouter --json chat --prompt "hi"
```

## Settings UI

```bash
cli-anything-orcarouter ui            # serves http://127.0.0.1:<port>/ and opens a browser
cli-anything-orcarouter ui --port 8765 --no-browser
```

The page shows both authentication choices side by side and a model selector
driven by the same catalog. **The API key never reaches the browser**: the page
receives a masked form only, and model metadata is served by the local process
that holds the key.

## Configuration

```bash
cli-anything-orcarouter config path    # ~/.config/cli-anything-orcarouter/config.json
cli-anything-orcarouter config show    # stored values, key masked
```

## Run Tests

```bash
cd orcarouter/agent-harness
pip install -e ".[dev]"
python -m pytest cli_anything/orcarouter/tests/ -v
```

## More Information

- Full documentation: See README.md in the package
- Test coverage: See TEST.md in the package
- Methodology: See HARNESS.md in the cli-anything-plugin
