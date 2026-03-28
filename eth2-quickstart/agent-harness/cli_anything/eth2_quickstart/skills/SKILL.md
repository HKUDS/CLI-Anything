---
name: cli-anything-eth2-quickstart
description: >-
  Use eth2-quickstart to autonomously deploy a hardened Ethereum node, install
  execution and consensus clients, configure validator metadata, expose RPC
  safely, and inspect node health with structured JSON output.
---

# cli-anything-eth2-quickstart

Agent-native harness for the `chimera-defi/eth2-quickstart` automation repo.
This CLI wraps the repo's canonical shell scripts instead of replacing them.

## When To Use

Use this skill when the task involves:

- bootstrapping a fresh Ethereum node host
- installing execution and consensus clients with explicit client diversity
- enabling MEV-Boost or Commit-Boost workflows
- exposing RPC through Nginx or Caddy
- updating validator fee recipient or graffiti settings without handling secrets
- checking machine-readable health with `--json`

## Core Commands

```bash
# Canonical machine-readable health
cli-anything-eth2-quickstart --json health-check

# Phase 2 install with explicit client choices
cli-anything-eth2-quickstart --json install-clients \
  --network mainnet \
  --execution-client geth \
  --consensus-client lighthouse \
  --mev mev-boost \
  --confirm

# Guided node setup
cli-anything-eth2-quickstart --json setup-node \
  --phase auto \
  --execution-client geth \
  --consensus-client prysm \
  --mev commit-boost \
  --confirm

# Validator metadata only; no key import
cli-anything-eth2-quickstart --json configure-validator \
  --consensus-client prysm \
  --fee-recipient 0x1111111111111111111111111111111111111111 \
  --graffiti "CLI-Anything"

# Install nginx-backed RPC exposure
cli-anything-eth2-quickstart --json start-rpc \
  --web-stack nginx \
  --server-name rpc.example.org \
  --confirm
```

## Safety Rules

- Always use `--json` for agent parsing.
- Require human confirmation before `setup-node`, `install-clients`, or `start-rpc`.
- Do not generate validator keys.
- Do not remove secrets or wallet material.
- Treat `configure-validator` as metadata and operator-guidance only.
- Respect the reboot boundary between Phase 1 and Phase 2.

## Runtime Expectations

- Operates on a local `eth2-quickstart` checkout.
- Discovers repo root from `--repo-root`, `ETH2QS_REPO_ROOT`, or current working directory.
- Writes compatible overrides into `config/user_config.env` when flags map directly to repo settings.

