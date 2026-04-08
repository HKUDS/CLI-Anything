# WireMock CLI Harness — Standard Operating Procedure

## What is WireMock?

WireMock is a flexible HTTP mock server used to stub and record HTTP interactions. It exposes a REST Admin API at `/__admin/` for managing stubs, inspecting requests, controlling stateful scenarios, and recording traffic from real backends.

This CLI harness wraps those admin endpoints so agents and developers can control WireMock from the terminal or scripts without needing to craft raw HTTP calls.

---

## Starting WireMock Standalone

### Download

```bash
curl -fsSL https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/3.3.1/wiremock-standalone-3.3.1.jar \
     -o wiremock-standalone.jar
```

### Start (default port 8080)

```bash
java -jar wiremock-standalone.jar --port 8080 --verbose
```

### Start with persistent mappings directory

```bash
java -jar wiremock-standalone.jar \
  --port 8080 \
  --root-dir ./wiremock-data \
  --verbose
```

### Start with HTTPS

```bash
java -jar wiremock-standalone.jar \
  --port 8443 \
  --https-port 8443 \
  --verbose
```

### Docker (alternative)

```bash
docker run -d --name wiremock \
  -p 8080:8080 \
  wiremock/wiremock:latest
```

---

## Installing the CLI

```bash
cd /path/to/agent-harness
pip install -e .
cli-anything-wiremock --help
```

---

## Connection Configuration

All connection parameters can be set via environment variables or CLI flags.

| Environment Variable | CLI Flag     | Default     | Description          |
|----------------------|--------------|-------------|----------------------|
| `WIREMOCK_HOST`      | `--host`     | `localhost` | WireMock host        |
| `WIREMOCK_PORT`      | `--port`     | `8080`      | WireMock port        |
| `WIREMOCK_SCHEME`    | `--scheme`   | `http`      | `http` or `https`    |
| `WIREMOCK_USER`      | `--user`     | (none)      | Basic auth username  |
| `WIREMOCK_PASSWORD`  | `--password` | (none)      | Basic auth password  |
| `WIREMOCK_JSON`      | `--json`     | false       | JSON output mode     |

**Example — connect to a remote WireMock instance:**

```bash
export WIREMOCK_HOST=wiremock.internal
export WIREMOCK_PORT=9090
cli-anything-wiremock status
```

---

## Common Workflows

### 1. Verify the server is running

```bash
cli-anything-wiremock status
```

### 2. Create a simple stub

```bash
# Quick form: METHOD URL STATUS_CODE [--body JSON]
cli-anything-wiremock stub quick GET /api/users 200 --body '{"users":[]}'

# Full JSON form
cli-anything-wiremock stub create '{
  "request": { "method": "POST", "url": "/api/orders" },
  "response": { "status": 201, "body": "{\"id\":42}", "headers": { "Content-Type": "application/json" } }
}'
```

### 3. List all stubs

```bash
cli-anything-wiremock stub list
cli-anything-wiremock stub list --json   # machine-readable
```

### 4. Get a specific stub

```bash
cli-anything-wiremock stub get <stub-id>
```

### 5. Delete a stub

```bash
cli-anything-wiremock stub delete <stub-id>
```

### 6. Reset all stubs to defaults

```bash
cli-anything-wiremock stub reset
```

### 7. Persist stubs to disk

```bash
cli-anything-wiremock stub save
```

### 8. Import stubs from a file

```bash
cli-anything-wiremock stub import ./my-stubs.json
```

---

### Request Verification

```bash
# List recent requests
cli-anything-wiremock request list
cli-anything-wiremock request list --limit 10

# Find requests matching a pattern
cli-anything-wiremock request find '{"method": "GET", "url": "/api/users"}'

# Count matching requests (useful for assertion)
cli-anything-wiremock request count '{"method": "POST", "urlPath": "/api/orders"}'

# List unmatched requests (404s)
cli-anything-wiremock request unmatched

# Clear the request journal
cli-anything-wiremock request reset
```

---

### Stateful Scenario Testing

WireMock supports state machines (scenarios) to simulate multi-step workflows.

```bash
# List all scenarios and their current state
cli-anything-wiremock scenario list

# Set a specific scenario to a state
cli-anything-wiremock scenario set "login-flow" "logged-in"

# Reset all scenarios to initial state
cli-anything-wiremock scenario reset
```

---

### Recording Traffic from a Real Backend

Use recording to auto-generate stubs from real API traffic.

```bash
# Start recording — proxy traffic to a real backend
cli-anything-wiremock record start https://api.example.com

# ... make requests to http://localhost:8080 — they are proxied and captured ...

# Stop recording and inspect captured stubs
cli-anything-wiremock record stop

# Check if currently recording
cli-anything-wiremock record status

# Take a snapshot of in-memory requests as stubs
cli-anything-wiremock record snapshot
```

---

### Server Management

```bash
# Check WireMock version
cli-anything-wiremock settings version

# Get global settings
cli-anything-wiremock settings get

# Full reset (stubs + requests + scenarios)
cli-anything-wiremock reset

# Shutdown the server
cli-anything-wiremock shutdown
```

---

## JSON Output Mode

All commands support `--json` for machine-readable output suitable for scripting or agent use:

```bash
cli-anything-wiremock --json stub list
cli-anything-wiremock --json request count '{"method":"GET","url":"/health"}'
```

JSON output varies by command type:

- **Data commands** return the raw WireMock API JSON directly (e.g. `stub list` returns `{"mappings": [...], "total": N}`)
- **Void operations** (delete, reset, save) return `{"status": "ok"}`
- **`status` command** returns `{"status": "running"|"stopped", "host": "...", "port": N}`
- **Errors** return `{"status": "error", "message": "..."}` (printed to stderr in human mode)
