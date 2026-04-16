# cli-anything-mubu

Canonical packaged entrypoint for the Mubu live bridge.

This package lives in the CLI-Anything-aligned harness tree and exposes:

- `cli-anything-mubu` console script
- `python -m cli_anything.mubu`
- default REPL when no subcommand is supplied
- REPL banner with app version, packaged skill path, and history path
- persisted `current-doc` and `current-node` REPL context
- grouped `discover` / `inspect` / `mutate` / `session` commands

Daily helpers are now explicit by default:

- pass a daily-folder reference to `discover daily-current`, `inspect daily-nodes`, or `session use-daily`
- or set `MUBU_DAILY_FOLDER` if you want those helpers to work without an argument

Canonical source paths:

- `agent-harness/mubu_probe.py`
- `agent-harness/cli_anything/mubu/...`

Compatibility wrappers remain at:

- `mubu_probe.py`
- `cli_anything/mubu/...`

Primary operator documentation remains at the project root:

- `README.md`
- `SKILL.md`
