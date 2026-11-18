---
name: cli-anything-controlplane
description: Inspect a compose-based infrastructure repo — stacks, services, published ports, Caddy site routing, and preflight checks. No Docker daemon or SSH required.
---

# cli-anything-controlplane

CLI harness for infrastructure repos that follow the control-plane layout: a root
`docker-compose.yml` that `include:`s one directory per stack, plus a Caddyfile for
reverse-proxy routing.

Everything is **static file analysis**. The CLI never talks to Docker, never SSHes
anywhere and never mutates the repo, so it is safe on a laptop, in CI, or inside an
agent sandbox without a daemon.

## Why an agent wants this

When a site returns 502, or a port conflict shows up at deploy time, the questions are
always the same: *which site block owns this domain, what upstream does it point at,
which stack publishes that container port, and does the repo parse at all?* Answering
them by grepping a 1000-line Caddyfile and 17 compose files is where agents usually
burn context and make mistakes. These commands answer them with one call and `--json`.

## Prerequisites

- Python 3.10+, `pip install cli-anything-controlplane` (or `pip install -e .`)
- A repo with at least one compose file per stack
- Optional Caddyfile at `<repo>/caddy/Caddyfile` (override with `--caddyfile`)

## Global options

| Option | Meaning |
|--------|---------|
| `--repo PATH` | Repo root. Default: detected from cwd (walks up to the compose file that has `include:`) |
| `--json` | Machine-readable output |
| `--caddyfile PATH` | Caddyfile location (default `<repo>/caddy/Caddyfile`) |

## Commands

### stack — compose stacks

| Command | Description |
|---------|-------------|
| `stack list` | Every directory holding a compose file, with service count |
| `stack show <name>` | One stack: services, images, published ports |
| `stack validate` | Repo-wide checks: YAML errors, missing `include` targets, services without `image`/`build`, duplicate `container_name`, conflicting host ports |

`stack validate` exits non-zero when errors exist, so it works directly in CI.

### service — cross-stack view

| Command | Description |
|---------|-------------|
| `service list` | Every service in the repo with image, container name and ports |

### caddy — routing

| Command | Description |
|---------|-------------|
| `caddy sites` | Site blocks with kind (`reverse_proxy`/`redirect`/`static`/`respond`) and upstreams |
| `caddy hosts` | Flat list of every configured address |
| `caddy find <domain>` | The site block(s) serving a domain, including handlers |
| `caddy validate` | Brace balance, duplicate addresses, `reverse_proxy` without upstream, upstream without port |

`caddy find` understands wildcard addresses (`*.example.com`) and matches subdomains.

### doctor

| Command | Description |
|---------|-------------|
| `doctor` | Preflight: repo layout, compose issues, Caddyfile presence, and published services that no site block proxies to |

## Examples

```bash
# What serves obsidian-sync.example.de?
cli-anything-controlplane --repo ~/infra caddy find obsidian-sync.example.de

# JSON, for piping into another tool
cli-anything-controlplane --json --repo ~/infra caddy sites

# Which services publish a host port but are not behind the proxy?
cli-anything-controlplane --repo ~/infra doctor

# Fail a pipeline on a broken compose tree
cli-anything-controlplane --repo ~/infra stack validate
```

## Pitfalls

- `stack validate` is static. It does not resolve `env_file` values or image digests.
- `caddy validate` is structural, not a substitute for `caddy validate --config`. It
  catches the mistakes that break deploys without needing the Caddy binary.
- Duplicate host-port findings are warnings: two stacks may intentionally bind the
  same container port on different host interfaces.
- The repo root is detected by the compose file containing `include:`; pass `--repo`
  when a repo has several compose roots.
