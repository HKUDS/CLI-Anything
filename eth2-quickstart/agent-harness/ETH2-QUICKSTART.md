# ETH2 QuickStart CLI Harness SOP

## Overview

This harness adds `cli-anything-eth2-quickstart`, a production-oriented CLI wrapper for the
[`chimera-defi/eth2-quickstart`](https://github.com/chimera-defi/eth2-quickstart) repository.
It does not reimplement node installation logic. Instead, it maps agent-friendly commands onto
the repo's canonical shell entrypoints:

- `scripts/eth2qs.sh`
- `run_1.sh`
- `run_2.sh`
- `install/utils/doctor.sh`
- `install/utils/stats.sh`
- `install/web/install_nginx.sh`
- `install/web/install_nginx_ssl.sh`
- `install/web/install_caddy.sh`
- `install/web/install_caddy_ssl.sh`

## Architecture

The package follows standard CLI-Anything layout:

- `cli_anything/eth2_quickstart/eth2_quickstart_cli.py`
  Click entrypoint with REPL and machine-readable `--json` mode.
- `cli_anything/eth2_quickstart/core/project.py`
  Repo-root discovery plus safe updates to `config/user_config.env`.
- `cli_anything/eth2_quickstart/utils/eth2qs_backend.py`
  Thin subprocess backend for invoking the upstream wrapper/scripts.
- `cli_anything/eth2_quickstart/core/*.py`
  Small orchestration helpers for install, RPC, validator guidance, and health.

## Command Mapping

### `setup-node`

Purpose: orchestrate phase execution with explicit client/MEV flags.

- `--phase phase1` -> `./scripts/eth2qs.sh phase1`
- `--phase phase2` -> `./scripts/eth2qs.sh phase2 --execution=... --consensus=... --mev=...`
- `--phase auto` without client flags -> `./scripts/eth2qs.sh ensure --apply --confirm`
- `--phase auto` with client flags -> phase 2 install

The harness also writes matching values into `config/user_config.env` when provided:

- `ETH_NETWORK`
- `EXEC_CLIENT`
- `CONS_CLIENT`
- `MEV_SOLUTION`
- `ETHGAS_NETWORK`

### `install-clients`

Direct phase 2 wrapper for execution/consensus/MEV installation, including optional ETHGas.

### `start-rpc`

Configures RPC exposure through either Nginx or Caddy by calling the upstream install scripts.
When `--server-name` is provided, the harness writes `SERVER_NAME` into `config/user_config.env`
before invoking the selected web installer.

### `configure-validator`

This command intentionally avoids importing validator keys or generating secrets. It updates
validator-related config values when provided:

- `FEE_RECIPIENT`
- `GRAFITTI`

Then it returns client-specific import and follow-up commands for the selected consensus client.
This keeps secret handling under operator control while still giving agents a composable surface.

### `status`

Returns:

- human mode: `stats` output plus current repo root
- JSON mode: `doctor --json`, `plan --json`, and raw `stats` output

### `health-check`

Returns the canonical `doctor --json` output and a short harness summary.

## Safety

- The harness requires `--confirm` for phase execution and RPC installer mutations.
- It never generates validator keys.
- It never deletes secrets or wallet data.
- It preserves the upstream reboot boundary between Phase 1 and Phase 2.
- It relies on upstream scripts for system mutations so behavior remains aligned with the source repo.

## Installation Model

The harness is meant to be installed from the CLI-Anything repo:

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=eth2-quickstart/agent-harness
```

At runtime it operates against an `eth2-quickstart` checkout discovered by:

1. `--repo-root`
2. `ETH2QS_REPO_ROOT`
3. current working directory / parents containing `scripts/eth2qs.sh`

## Testing Strategy

- `test_core.py`
  Uses mocked backend calls and temporary repo fixtures. No real node backend required.
- `test_full_e2e.py`
  Auto-skips unless a real `eth2-quickstart` checkout is available via `ETH2QS_E2E_REPO_ROOT`.
  E2E coverage is read-only or help-level by default so it is safe to run in CI.

