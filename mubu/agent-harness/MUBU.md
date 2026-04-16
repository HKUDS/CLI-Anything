# MUBU Harness Notes

## Target

- Software: Mubu desktop app
- User goal: let Codex inspect, search, navigate, and perform careful atomic edits on the same local Mubu workspace the user is actively using

## Backend Surfaces

Read surfaces:

- local backup snapshots
- local RxDB `.storage`
- client-sync logs

Live surfaces:

- `/v3/api/document/get`
- `/v3/api/colla/events`

Auth and context sources:

- local users store for `token` and `userId`
- sync logs for `memberId`
- live `/document/get` for current `baseVersion`

## Current Command Groups

Grouped Click domains:

- `discover`
- `inspect`
- `mutate`
- `session`

Discover / inspect examples:

- `recent`
- `folders`
- `path-docs`
- `daily-current`
- `daily-nodes`
- `open-path`
- `doc-nodes`

Mutate:

- `update-text`
- `create-child`
- `delete-node`

Packaging:

- `cli-anything-mubu`
- `python -m cli_anything.mubu`
- editable install root: `agent-harness/`
- canonical source root: `agent-harness/cli_anything/mubu/...`
- compatibility wrappers remain at the project root
- packaged skill regeneration: `python3 agent-harness/skill_generator.py agent-harness`

## Current State Model

Subcommand mode:

- stateless per invocation

REPL mode:

- persisted `current_doc`
- persisted `current_node`
- persisted local command history
- session JSON stored at `~/.config/cli-anything-mubu/session.json`
- REPL history stored at `~/.config/cli-anything-mubu/history.txt`
- startup banner exposes the packaged `SKILL.md` absolute path
- override via `CLI_ANYTHING_MUBU_STATE_DIR`

## Safety Model

- inspect before mutate
- dry-run first for live mutations
- `update-text` is live-verified
- `create-child` is live-verified
- `delete-node` is live-verified

## Current Gaps

- no undo/redo
- no move primitive
- no broader live multi-command E2E suite beyond the reversible scratch verification
