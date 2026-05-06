# cli-anything-nslogger

CLI harness for [NSLogger](https://github.com/fpillet/NSLogger) — read, filter, export, and monitor NSLogger log files from the command line or from AI agents.

## Installation

```bash
cd agent-harness
pip install -e .
```

## Quick Start

```bash
# Generate a sample file
cli-anything-nslogger generate sample.rawnsloggerdata --count 50

# Read and display all messages
cli-anything-nslogger read sample.rawnsloggerdata

# Show only errors
cli-anything-nslogger read sample.rawnsloggerdata --level 0

# Filter by tag
cli-anything-nslogger filter sample.rawnsloggerdata --tag Network

# Export to JSON
cli-anything-nslogger export sample.rawnsloggerdata --format json

# Statistics
cli-anything-nslogger stats sample.rawnsloggerdata

# Listen for live iOS logs via Bonjour, matching the NSLogger.app GUI
cli-anything-nslogger listen --bonjour --name bazinga --debug

# Direct TCP/TLS mode for manually configured clients
cli-anything-nslogger listen --port 50000 --ssl --debug

# Listen and write received live logs to a file
cli-anything-nslogger listen --bonjour --name bazinga --output app.log

# Write machine-readable live logs as JSON Lines
cli-anything-nslogger listen --bonjour --name bazinga --output app.jsonl --output-format jsonl

# Interactive REPL
cli-anything-nslogger repl sample.rawnsloggerdata
```

## JSON Output (Agent Mode)

Every command accepts `--json` for machine-readable output:

```bash
cli-anything-nslogger read sample.rawnsloggerdata --json
cli-anything-nslogger stats sample.rawnsloggerdata --json
```

## Commands

| Command    | Description |
|-----------|-------------|
| `read`    | Parse and display messages from a file |
| `filter`  | Advanced filtering (level, tag, thread, regex) |
| `export`  | Export to text / JSON / CSV |
| `stats`   | Summary statistics |
| `listen`  | Receive live NSLogger connections via Bonjour or TCP/TLS |
| `generate`| Create sample `.rawnsloggerdata` for testing |
| `repl`    | Interactive Python REPL with loaded messages |

## Log Levels

| Level | Name    |
|-------|---------|
| 0     | ERROR   |
| 1     | WARNING |
| 2     | INFO    |
| 3     | DEBUG   |
| 4     | VERBOSE |

## File Formats

| Extension | Description |
|-----------|-------------|
| `.rawnsloggerdata` | Raw NSLogger wire-protocol capture |
| `.nsloggerdata` | Binary plist archive saved by NSLogger.app |
