---
name: cli-anything-nslogger
description: CLI harness for NSLogger — parse, filter, export, and monitor NSLogger log files (.rawnsloggerdata / .nsloggerdata)
version: 0.1.0
install: pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=nslogger/agent-harness
binary: cli-anything-nslogger
tags: [logging, ios, macos, debugging, nslogger]
---

# cli-anything-nslogger

A complete CLI harness for [NSLogger](https://github.com/fpillet/NSLogger), the macOS log viewer for iOS/macOS apps.

## Installation

```bash
cd nslogger/agent-harness
pip install -e .
# Verify
cli-anything-nslogger --help
```

## Command Reference

### `generate` — Create sample files for testing

```bash
cli-anything-nslogger generate sample.rawnsloggerdata --count 50
```

### `read` — Display messages from a file

```bash
# All messages
cli-anything-nslogger read session.rawnsloggerdata

# Errors only (level 0)
cli-anything-nslogger read session.rawnsloggerdata --level 0

# Filter by tag and text search
cli-anything-nslogger read session.rawnsloggerdata --tag Network --search "timeout"

# First 20 messages as JSON
cli-anything-nslogger read session.rawnsloggerdata --limit 20 --json
```

### `filter` — Advanced filtering

```bash
# Errors and warnings only
cli-anything-nslogger filter session.rawnsloggerdata --level 1

# By tag
cli-anything-nslogger filter session.rawnsloggerdata --tag Auth --tag Network

# Regex search
cli-anything-nslogger filter session.rawnsloggerdata --regex "(timeout|failed|error)"

# By thread
cli-anything-nslogger filter session.rawnsloggerdata --thread "main"

# JSON output
cli-anything-nslogger filter session.rawnsloggerdata --level 0 --json
```

### `export` — Export to text/JSON/CSV

```bash
# JSON to stdout
cli-anything-nslogger export session.rawnsloggerdata --format json

# CSV to file
cli-anything-nslogger export session.rawnsloggerdata --format csv --output logs.csv

# Filtered text export
cli-anything-nslogger export session.rawnsloggerdata --format text --level 1 --tag Network
```

### `stats` — Summary statistics

```bash
# Human-readable summary
cli-anything-nslogger stats session.rawnsloggerdata

# JSON for agent consumption
cli-anything-nslogger stats session.rawnsloggerdata --json
```

JSON output shape:
```json
{
  "total": 342,
  "by_level": {"ERROR": 12, "WARNING": 34, "INFO": 200, "DEBUG": 96},
  "by_tag": {"Network": 89, "Auth": 45, "UI": 120},
  "by_thread": {"main": 200, "bg-queue": 142},
  "by_type": {"text": 340, "client_info": 1, "disconnect": 1},
  "clients": ["MyApp"],
  "first_timestamp": "2024-01-01T10:00:00+00:00",
  "last_timestamp": "2024-01-01T10:05:30+00:00",
  "duration_seconds": 330.0
}
```

### `listen` — Receive live connections

```bash
# Match the NSLogger.app GUI Bonjour behavior for iOS auto-discovery
cli-anything-nslogger listen --bonjour --name bazinga --debug

# Mirror live logs to a text file while still printing stdout
cli-anything-nslogger listen --bonjour --name bazinga --output app.log

# Write machine-readable JSON Lines
cli-anything-nslogger listen --bonjour --name bazinga --output app.jsonl --output-format jsonl

# Direct TCP/TLS mode for manually configured clients
cli-anything-nslogger listen --port 50000 --ssl --debug

# Show only errors while listening, output as JSON stream
cli-anything-nslogger listen --bonjour --name bazinga --level 0 --json

# Run until Ctrl-C
cli-anything-nslogger listen --bonjour --name bazinga
```

Use Bonjour mode first for iOS apps because it matches the desktop NSLogger GUI:
the CLI publishes a native macOS `NetService` with `_nslogger-ssl._tcp` and
accepts TLS NSLogger frames. Use direct TCP/TLS only when the app is manually
configured with the Mac host and port.

### `repl` — Interactive Python REPL

```bash
cli-anything-nslogger repl session.rawnsloggerdata
# Available: messages, parse_file, filter_messages, compute_stats, export_messages
```

## Log Levels

| Value | Name    | Use for |
|-------|---------|---------|
| 0     | ERROR   | Unrecoverable failures |
| 1     | WARNING | Recoverable issues |
| 2     | INFO    | Normal operation |
| 3     | DEBUG   | Developer details |
| 4     | VERBOSE | Trace-level noise |

## Message JSON Shape

```json
{
  "sequence": 42,
  "timestamp": "2024-01-01T10:01:23+00:00",
  "timestamp_ms": 456,
  "thread_id": "main",
  "tag": "Network",
  "level": 0,
  "level_name": "ERROR",
  "type": "text",
  "text": "Connection timed out after 30s",
  "image_width": 0,
  "image_height": 0,
  "client_name": "MyApp",
  "client_version": "2.1.0",
  "os_name": "iOS",
  "os_version": "17.0",
  "machine": "iPhone15,2"
}
```

## Agent Workflow Examples

```bash
# 1. Inspect a captured crash session
cli-anything-nslogger stats crash.rawnsloggerdata --json

# 2. Find all errors in the 5 minutes before crash
cli-anything-nslogger filter crash.rawnsloggerdata --level 0 --json

# 3. Get network failures only
cli-anything-nslogger filter crash.rawnsloggerdata --tag Network --regex "fail|timeout|error" --json

# 4. Export full log for offline analysis
cli-anything-nslogger export crash.rawnsloggerdata --format json --output crash_log.json

# 5. Monitor an iOS app live and keep a local copy
cli-anything-nslogger listen --bonjour --name bazinga --output app.log --debug
```
