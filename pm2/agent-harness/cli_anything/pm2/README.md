# cli-anything PM2

CLI-Anything harness for PM2 process management. All PM2 commands are executed via subprocess -- no PM2 API dependency required.

## Quick Start

```bash
# Install
cd agent-harness && pip install -e .

# REPL mode
cli-anything-pm2

# Direct commands
cli-anything-pm2 process list
cli-anything-pm2 --json process list
cli-anything-pm2 lifecycle restart seaclip-dev
cli-anything-pm2 logs view voice-agent --lines 50
cli-anything-pm2 system version
```

## Command Groups

- **process**: list, describe, metrics
- **lifecycle**: start, stop, restart, delete
- **logs**: view, flush
- **system**: save, startup, version

## Architecture

```
pm2_cli.py          Click CLI + REPL entry point
core/
  processes.py      list, describe, metrics
  lifecycle.py      start, stop, restart, delete
  logs.py           view, flush
  system.py         save, startup, version
utils/
  pm2_backend.py    subprocess wrapper for pm2 commands
  repl_skin.py      cli-anything REPL skin
```
