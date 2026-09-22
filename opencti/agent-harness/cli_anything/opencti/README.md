# cli-anything-opencti

Agent-native CLI for the [OpenCTI](https://github.com/OpenCTI-Platform/opencti)
threat intelligence platform — built with the
[CLI-Anything](https://github.com/HKUDS/CLI-Anything) pattern.

Query and create observables, indicators, reports, cases, named threat
entities, and relationships over OpenCTI's GraphQL API v7. Every command
supports `--json` for machine-readable output, making the whole platform
scriptable by AI agents. Deletion requires an explicit `--force`.

Verified against OpenCTI **7.260824.0**.

## Installation

```bash
pip install cli-anything-opencti

# or from this repo
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=opencti/agent-harness
```

## Configuration

Precedence: CLI flags > environment variables > `~/.cli-anything/opencti/config.json`.

```bash
export OPENCTI_BASE_URL=http://localhost:8090
export OPENCTI_API_KEY=<your-api-token>

# persist instead:
cli-anything-opencti config set --url http://localhost:8090 --token <token>
cli-anything-opencti config test
```

## Usage

```bash
cli-anything-opencti status                     # version + identity + liveness
cli-anything-opencti whoami --json              # token identity as JSON

cli-anything-opencti observable search 185.220 --type ipv4-addr
cli-anything-opencti indicator list --limit 50 --json
cli-anything-opencti indicator search-pattern "[ipv4-addr:value"
cli-anything-opencti report list --all          # follow all pages
cli-anything-opencti case list --type rfi
cli-anything-opencti entity get threat-actor <uuid>
cli-anything-opencti search apt41 --types Threat-Actor,Intrusion-Set
cli-anything-opencti export-stix --id <uuid> -o bundle.json

# writes
cli-anything-opencti observable add domain-name evil.example --score 90 --create-indicator
cli-anything-opencti indicator add "C2 domain" --pattern "[domain-name:value = 'evil.example']"
cli-anything-opencti entity add threat-actor "APT-X" --alias "APT-X Prime"
cli-anything-opencti relationship add <actor-id> <observable-id> related-to
cli-anything-opencti delete <id>                # dry-run; add --force to execute
```

`--json` is a group-level flag and goes before the subcommand:

```bash
cli-anything-opencti --json indicator list
```

## Command Reference

| Group | Commands |
|-------|----------|
| observable | `search QUERY [--type csv]`, `get ID`, `add TYPE VALUE [--score] [--label] [--create-indicator]` |
| indicator | `list [--search]`, `get ID`, `search-pattern PREFIX`, `add NAME --pattern P` |
| report | `list [--search]`, `get ID`, `add NAME [--published ISO] [--type csv]` |
| relationship | `list`, `add FROM TO TYPE` |
| case | `list --type incident\|rfi\|rft`, `get ID --type ...`, `add --type T NAME [--severity] [--priority]` |
| entity | `list TYPE`, `get TYPE ID`, `add TYPE NAME [--alias csv]` for threat-actor\|intrusion-set\|malware\|campaign\|tool |
| top-level | `status`, `whoami`, `search QUERY [--types]`, `export-stix --id ID [-o FILE]`, `delete ID [--force]` |
| config | `set --url URL [--token T]`, `test` |

Run with no subcommand to enter an interactive REPL with completion.
Status/success/error messages are written to stderr; stdout stays
machine-parseable for piping into `jq`.

## Development

```bash
pip install -e ".[dev]"
pytest -m "not e2e"                                   # mocked unit tests
OPENCTI_E2E=1 OPENCTI_BASE_URL=... OPENCTI_API_KEY=... \
  pytest -m e2e                                       # live instance required
```

See [OPENCTI.md](OPENCTI.md) for architecture analysis and the SOP.
