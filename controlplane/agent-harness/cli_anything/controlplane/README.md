# cli-anything-controlplane

Agent-native CLI for compose-based infrastructure repos: stacks, services, published
ports, Caddy site routing and preflight checks — without a Docker daemon, SSH, or any
mutation.

## Install

```bash
pip install -e .
# or from the repo:
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=controlplane/agent-harness
```

## Usage

```bash
cli-anything-controlplane --repo ~/infra stack list
cli-anything-controlplane --repo ~/infra stack show caddy
cli-anything-controlplane --repo ~/infra stack validate
cli-anything-controlplane --repo ~/infra service list
cli-anything-controlplane --repo ~/infra caddy sites
cli-anything-controlplane --repo ~/infra caddy hosts
cli-anything-controlplane --repo ~/infra caddy find app.example.com
cli-anything-controlplane --repo ~/infra caddy validate
cli-anything-controlplane --repo ~/infra doctor
```

Add `--json` to any command for machine-readable output. `stack validate`,
`caddy validate` and `doctor` exit non-zero when they find errors, so they drop
straight into CI.

## Layout it expects

```
infra/
  docker-compose.yml          # include: each stack
  caddy/
    docker-compose.yml
    Caddyfile
  adguard-home/docker-compose.yml
  portainer/docker-compose.yml
  ...
```

A plain repo with several independent compose files (no root `include:`) also works —
`--repo` then just needs to point at the directory containing the stacks.

## What it does not do

No `docker compose up`, no restarts, no logs, no SSH. This harness only reads files, so
it can run anywhere the repo exists. Pair it with a runtime tool (or your own deploy
script) when you need to change state.

## Tests

```bash
python -m pytest cli_anything/controlplane/tests/ -q
```
