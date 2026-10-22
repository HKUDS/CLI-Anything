# cli-anything-bluesky

Bluesky (AT Protocol) — agent-native CLI. Post, read, and search from any
agent that can run a subprocess.

## Layout

```
cli_anything/bluesky/
  bluesky_cli.py    Click CLI, --json on every command
  core/backend.py   AT Protocol client: session handling, XRPC calls
  skills/SKILL.md   agent-facing workflow manual
  tests/            test_core.py (mocked, no network) + test_full_e2e.py (live)
```

## Install

```bash
pip install -e .
```

## Quick start

```bash
cli-anything-bluesky login            # App Password, prompted hidden
cli-anything-bluesky post "hello from an agent"
cli-anything-bluesky --json timeline --limit 10
```

## Auth

Bluesky App Passwords only. Session token in
`~/.config/cli-anything-bluesky/session.json` (0600). Set
`CLI_ANYTHING_BLUESKY_SESSION` to relocate it.

## Tests

```bash
python -m pytest cli_anything/bluesky/tests/test_core.py -v        # offline
BSKY_HANDLE=you.bsky.social BSKY_APP_PASSWORD=... \
  python -m pytest cli_anything/bluesky/tests/test_full_e2e.py -v  # live
```
