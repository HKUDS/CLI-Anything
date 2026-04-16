# AdGuardHome - CLI Harness SOP

## Overview

AdGuardHome is a DNS-based ad blocker and privacy protection server written in Go.
It exposes a REST HTTP API with 58 endpoints organized in 14 tag groups, secured with HTTP Basic Auth.

**Real software:** The running AdGuardHome HTTP API (not a binary to invoke directly).
**CLI role:** Generate structured commands - call the real API - verify responses.

## Architecture

- **API base:** `http://<host>:<port>/control/`
- **Auth:** HTTP Basic Auth (`Authorization: Basic base64(user:pass)`)
- **Port:** 3000 by default
- **OpenAPI spec:** `openapi/openapi.yaml` in the AdGuardHome source

## API Tag Groups

| Group | Description | Key Endpoints |
|-------|-------------|---------------|
| `global` | Server settings and controls | `/status`, `/version`, `/restart` |
| `filtering` | Rule-based filtering | `/filtering/status`, `/filtering/add_url`, `/filtering/remove_url` |
| `blocked_services` | Block service categories | `/blocked_services/get`, `/blocked_services/set` |
| `clients` | Known clients | `/clients`, `/clients/add`, `/clients/delete` |
| `stats` | DNS query statistics | `/stats`, `/stats_reset`, `/stats_config` |
| `log` | Query log | `/querylog`, `/querylog_config`, `/querylog_clear` |
| `dhcp` | Built-in DHCP server | `/dhcp/status`, `/dhcp/leases`, `/dhcp/set_config` |
| `rewrite` | DNS rewrites | `/rewrite/list`, `/rewrite/add`, `/rewrite/delete` |
| `parental` | Adult content blocking | `/parental/status`, `/parental/enable`, `/parental/disable` |
| `safebrowsing` | Malware/phishing blocking | `/safebrowsing/status`, `/safebrowsing/enable`, `/safebrowsing/disable` |
| `safesearch` | Safe search enforcement | `/safesearch/status`, `/safesearch/enable`, `/safesearch/disable` |
| `tls` | HTTPS/DoH/DoT settings | `/tls/status`, `/tls/configure`, `/tls/validate` |

## CLI Command Map

```
cli-anything-adguardhome
├── config show / save / test
├── server status / version / restart
├── filter list / add / remove / enable / disable / refresh / status / toggle
├── blocking parental status/enable/disable
│          safebrowsing status/enable/disable
│          safesearch status/enable/disable
├── blocked-services list / set
├── clients list / add / remove / show
├── stats show / reset / config
├── log show / config / clear
├── rewrite list / add / remove
├── dhcp status / leases / add-static / remove-static
└── tls status
```

## Connection Config

Settings resolved in order:
1. CLI flags (`--host`, `--port`, `--username`, `--password`)
2. Environment vars (`AGH_HOST`, `AGH_PORT`, `AGH_USERNAME`, `AGH_PASSWORD`)
3. Config file (`~/.config/cli-anything-adguardhome.json`)
4. Defaults: `localhost:3000`

## Testing Strategy

- **Unit tests:** Mock HTTP calls via `unittest.mock` - no real AdGuardHome needed
- **E2E tests:** Spin up `adguard/adguardhome` via Docker on port 3001 for isolation
- **Subprocess tests:** `_resolve_cli("cli-anything-adguardhome")` tests the installed CLI binary
