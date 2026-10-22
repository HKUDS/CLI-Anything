---
name: "cli-anything-bluesky"
description: "Bluesky (AT Protocol) — post, read timeline, search, and check profiles from an agent-native CLI. Auth via App Passwords; token stored in a 0600 session file."
---

# cli-anything-bluesky

Bluesky (AT Protocol) harness. Requires a Bluesky account with an App Password
(Settings -> App Passwords on bsky.app). No other software needed.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=bluesky/agent-harness
```

## Commands

```bash
cli-anything-bluesky login                          # creates the session (prompts hidden)
cli-anything-bluesky whoami                         # current handle + did
cli-anything-bluesky post "text"                    # create one post
cli-anything-bluesky timeline --limit 20            # home timeline
cli-anything-bluesky profile [handle]               # profile (default: self)
cli-anything-bluesky search "query" --limit 25      # search posts
cli-anything-bluesky endpoints                      # the XRPC map
```

## JSON Output

All commands support `--json`:

```bash
cli-anything-bluesky --json timeline --limit 5
```

## Rules for agents

- Always `login` (or check `whoami`) before any authenticated command; a
  missing session is a clean exit-2 error, not a crash.
- `post` is the only mutating command and writes to a public network. Confirm
  the text with the user before posting on their behalf.
- Never ask for or log the account password — only App Passwords are accepted.
- Credentials come from flags, `BSKY_HANDLE`/`BSKY_APP_PASSWORD`, or a prompt.
  Do not pass them as positional arguments (they leak into shell history).
- The session token lives in `~/.config/cli-anything-bluesky/session.json`
  (0600). Respect `CLI_ANYTHING_BLUESKY_SESSION` if set.

## Evidence

Endpoints from the public AT Protocol documentation (docs.bsky.app), verified
live: `app.bsky.feed.getTimeline` returns 401 unauthenticated (exists),
`com.atproto.server.createSession` returns 400 on an empty body (exists).
Unit tests mock the network; E2E tests need real credentials and post+delete
a self-test.
