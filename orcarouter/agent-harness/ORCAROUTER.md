# ORCAROUTER SOP: CLI Harness Design

## Software Identity
- **Name**: OrcaRouter
- **Type**: Hosted AI gateway / router (OpenAI-compatible HTTP API) with a web console
- **Purpose**: One endpoint in front of many model providers; a single OrcaRouter API key routes requests to whichever upstream model the caller names
- **Core operations**: credential acquisition (existing API key or account sign-in), inference (chat, streaming, multimodal input), model discovery, credential lifecycle

## Architecture Analysis

### Provider surface
- **Inference + model discovery**: `https://api.orcarouter.ai/v1` — OpenAI wire format, `Authorization: Bearer sk-orca-…`
- **Authorization + code exchange**: `https://www.orcarouter.ai` — `/auth` (consent screen) and `/api/v1/auth/keys` (exchange)
- **Console**: `https://www.orcarouter.ai/console/authorized-apps` — revoke every key issued to this app in one click
- The two origins are independent. The auth API is **not** under `/v1`; `https://api.orcarouter.ai/v1/auth/keys` is a 404.

### Authentication model
| Choice | ID | Credential |
|--------|----|------------|
| Existing key | `api_key` | User pastes `sk-orca-…` |
| Account sign-in | `oauth_pkce` | OAuth 2.0 + PKCE (S256) issues an `sk-orca-…` key |

The PKCE result is a **durable API key**, not an access/refresh pair. There is
no refresh grant. `401` is terminal: mark the exact rejected account generation
`needs_reauth` and require a new sign-in.

### Flow choice
- **Flow A — loopback redirect** (default): the client is a local CLI with a
  browser and can bind `127.0.0.1:0`. The listener starts before the browser
  opens, so the port is known.
- **Flow B — out-of-band code** (`--oob`): SSH sessions, containers, and any
  host where the user's browser cannot reach the local listener.
- **Flow C — device grant**: not implemented; it is optional and cannot replace
  PKCE.

## Command Map

| Capability | Command Group | Data Source |
|------------|---------------|-------------|
| Store an existing API key | `auth api-key` | `~/.config/cli-anything-orcarouter/config.json` (mode 0600) |
| Connect with an account | `auth login [--oob]` | `https://www.orcarouter.ai/auth` + `/api/v1/auth/keys` |
| Credential status | `auth status` | config file + environment |
| Remove the credential | `auth logout` | config file |
| Model discovery | `models`, `catalog` | `GET {api_base}/models` |
| Inference | `chat`, `stream`, `test` | `POST {api_base}/chat/completions` |
| Settings UI | `ui` | loopback `ThreadingHTTPServer` |
| Config paths | `config path`, `config show` | config file |

## Verification Entry Points

| Command | What it proves | Needs a key |
|---------|----------------|-------------|
| `python3 -m pytest cli_anything/orcarouter/tests/` | Both credential adapters, PKCE, catalog filters, settings server, CLI, loopback e2e | no |
| `python3 -m pytest orcarouter/agent-harness/tools/test_live_provider.py` | Live catalog + one real chat completion through `core.catalog`/`core.provider` | yes |
| `python3 -m pytest orcarouter/agent-harness/tools/test_gui_evidence.py` | Screenshots and `orca-evidence/manifest.json` from the real settings page | yes |

Run the two `tools/` modules from the repository root. Both read
`ORCAROUTER_API_KEY` from the environment and never print it. The GUI module
writes its artifacts into the checkout's ignored `orca-evidence/` directory.

## Module Layout

```
cli_anything/orcarouter/
├── core/credentials.py     # the credential seam: API key and PKCE both end here
├── core/pkce.py            # verifier/challenge/state, authorize URL, exchange
├── core/login_manager.py   # one in-flight login, generation-guarded
├── core/catalog.py         # live /v1/models, capability filters, verified seed
├── core/provider.py        # Bearer transport, chat, streaming, modality guard
├── core/server.py          # loopback settings UI (key never reaches the browser)
├── ui/                     # index.html, styles.css, app.js, official logo
└── orcarouter_cli.py       # Click commands, REPL, --json output
```

## Rendering Gap Assessment
- **Partial gap.** OrcaRouter is an HTTP API, so the CLI covers everything the
  service exposes. What a CLI cannot do well is present the *two authentication
  choices side by side* and show a browsable model catalog, which is exactly the
  part of this integration a user has to decide about.
- The harness therefore also serves a small settings page on loopback
  (`cli-anything-orcarouter ui`), following the repository's existing pattern of
  serving a self-contained page from a stdlib `ThreadingHTTPServer`
  (`cli-hub previews`, `live2d snapshot`). It is a front end over the same
  credential seam and provider code path the CLI uses; it holds no
  authentication logic of its own, and the API key is never sent to the browser.

## Security Notes
- The API key is never printed, logged, or included in errors or telemetry.
  `auth status` and `config show` print a masked form (`sk-orca…abcd`).
- The PKCE verifier is generated per attempt from a cryptographic RNG and is
  sent only in the exchange body. It never appears in a URL.
- `state` is compared in constant time before a code is accepted.
- The config file is written with mode 0600.
- Non-loopback origins must be HTTPS.
