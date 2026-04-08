# cli-anything-wiremock

Python CLI harness for the [WireMock](https://wiremock.org/) HTTP mock server admin API.

## Installation

```bash
pip install -e /path/to/agent-harness
```

## Quick Start

```bash
# Check server status
cli-anything-wiremock status

# Create a stub
cli-anything-wiremock stub quick GET /api/hello 200 --body '{"hello":"world"}'

# List stubs
cli-anything-wiremock stub list

# Verify a request was made
cli-anything-wiremock request count '{"method":"GET","url":"/api/hello"}'
```

## Command Groups

| Group      | Purpose                                        |
|------------|------------------------------------------------|
| `stub`     | Create, read, update, delete stub mappings     |
| `request`  | Inspect served requests and verify invocations |
| `scenario` | Manage stateful scenario state machines        |
| `record`   | Record real backend traffic as stubs           |
| `settings` | Read global settings and server version        |

## Configuration

Set via environment variables or `--option` flags:

```bash
export WIREMOCK_HOST=localhost
export WIREMOCK_PORT=8080
export WIREMOCK_SCHEME=http
```

For the full SOP and workflow recipes, see `WIREMOCK.md` in the agent-harness directory (available in the source repository, not in installed packages).
