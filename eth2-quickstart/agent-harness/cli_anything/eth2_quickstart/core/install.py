"""Install orchestration helpers."""

from __future__ import annotations

from cli_anything.eth2_quickstart.core.commands import (
    VALID_CONSENSUS_CLIENTS,
    VALID_EXECUTION_CLIENTS,
    VALID_MEV_OPTIONS,
    VALID_NETWORKS,
)
from cli_anything.eth2_quickstart.core.project import upsert_user_config


def _validate_choice(name: str, value: str | None, allowed: set[str]) -> None:
    if value is not None and value not in allowed:
        raise ValueError(f"Unsupported {name}: {value}")


def _config_updates(
    network: str | None,
    execution_client: str | None,
    consensus_client: str | None,
    mev: str | None,
) -> dict[str, str]:
    updates: dict[str, str] = {}
    if network:
        updates["ETH_NETWORK"] = network
        updates["ETHGAS_NETWORK"] = network
    if execution_client:
        updates["EXEC_CLIENT"] = execution_client
    if consensus_client:
        updates["CONS_CLIENT"] = consensus_client
    if mev:
        updates["MEV_SOLUTION"] = mev
    return updates


def install_clients(
    backend,
    *,
    network: str | None = None,
    execution_client: str | None = None,
    consensus_client: str | None = None,
    mev: str | None = None,
    ethgas: bool = False,
    skip_deps: bool = False,
) -> dict:
    _validate_choice("network", network, VALID_NETWORKS)
    _validate_choice("execution client", execution_client, VALID_EXECUTION_CLIENTS)
    _validate_choice("consensus client", consensus_client, VALID_CONSENSUS_CLIENTS)
    _validate_choice("mev", mev, VALID_MEV_OPTIONS)

    if ethgas and mev != "commit-boost":
        raise ValueError("ETHGas requires mev=commit-boost")

    updates = _config_updates(network, execution_client, consensus_client, mev)
    config_path = None
    if updates:
        config_path = upsert_user_config(backend.repo_root, updates)

    args = ["phase2"]
    if execution_client:
        args.append(f"--execution={execution_client}")
    if consensus_client:
        args.append(f"--consensus={consensus_client}")
    if mev:
        args.append(f"--mev={mev}")
    if ethgas:
        args.append("--ethgas")
    if skip_deps:
        args.append("--skip-deps")

    result = backend.run_wrapper(*args)
    result["config_path"] = str(config_path) if config_path else None
    result["requested"] = {
        "network": network,
        "execution_client": execution_client,
        "consensus_client": consensus_client,
        "mev": mev,
        "ethgas": ethgas,
        "skip_deps": skip_deps,
    }
    return result


def setup_node(
    backend,
    *,
    phase: str,
    network: str | None = None,
    execution_client: str | None = None,
    consensus_client: str | None = None,
    mev: str | None = None,
    ethgas: bool = False,
    skip_deps: bool = False,
) -> dict:
    if phase not in {"auto", "phase1", "phase2"}:
        raise ValueError(f"Unsupported phase: {phase}")

    if phase == "phase1":
        result = backend.run_wrapper("phase1")
        result["requested_phase"] = phase
        return result

    if phase == "phase2":
        result = install_clients(
            backend,
            network=network,
            execution_client=execution_client,
            consensus_client=consensus_client,
            mev=mev,
            ethgas=ethgas,
            skip_deps=skip_deps,
        )
        result["requested_phase"] = phase
        return result

    if any([execution_client, consensus_client, mev, ethgas, skip_deps, network]):
        result = install_clients(
            backend,
            network=network,
            execution_client=execution_client,
            consensus_client=consensus_client,
            mev=mev,
            ethgas=ethgas,
            skip_deps=skip_deps,
        )
        result["requested_phase"] = "auto-phase2"
        return result

    result = backend.run_wrapper("ensure", "--apply", "--confirm")
    result["requested_phase"] = "auto-ensure"
    return result

