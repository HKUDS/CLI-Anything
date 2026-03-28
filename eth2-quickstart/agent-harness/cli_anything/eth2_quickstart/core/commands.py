"""Static command metadata and validator guidance."""

from __future__ import annotations

VALID_NETWORKS = {"mainnet", "holesky"}
VALID_EXECUTION_CLIENTS = {
    "geth",
    "besu",
    "erigon",
    "nethermind",
    "nimbus_eth1",
    "reth",
    "ethrex",
}
VALID_CONSENSUS_CLIENTS = {
    "prysm",
    "lighthouse",
    "lodestar",
    "teku",
    "nimbus",
    "grandine",
}
VALID_MEV_OPTIONS = {"mev-boost", "commit-boost", "none"}
VALID_WEB_STACKS = {"nginx", "caddy"}


def validator_plan(
    consensus_client: str,
    fee_recipient: str | None = None,
    graffiti: str | None = None,
    keys_dir: str | None = None,
    secrets_dir: str | None = None,
    wallet_password_file: str | None = None,
) -> dict:
    if consensus_client not in VALID_CONSENSUS_CLIENTS:
        raise ValueError(f"Unsupported consensus client: {consensus_client}")

    key_locations = {
        "prysm": {
            "keys": keys_dir or "/path/to/validator-keys",
            "secrets": secrets_dir or "~/secrets",
            "config_file": "~/prysm/prysm_validator_conf.yaml",
            "import_command": (
                "~/prysm/prysm.sh validator accounts import "
                f"--keys-dir={keys_dir or '/path/to/validator-keys'}"
            ),
        },
        "lighthouse": {
            "keys": keys_dir or "~/.lighthouse/mainnet/validators",
            "secrets": secrets_dir or "~/.lighthouse/mainnet/secrets",
            "config_file": "/etc/systemd/system/validator.service",
            "import_command": (
                "lighthouse account validator import "
                f"--directory {keys_dir or '/path/to/validator-keys'} "
                f"--secrets-dir {secrets_dir or '~/.lighthouse/mainnet/secrets'}"
            ),
        },
        "lodestar": {
            "keys": keys_dir or "~/.local/share/lodestar/validators/keystores",
            "secrets": secrets_dir or "~/.local/share/lodestar/validators/secrets",
            "config_file": "~/lodestar/validator.config.json",
            "import_command": (
                "lodestar validator import "
                f"--keystoresDir {keys_dir or '/path/to/validator-keys'} "
                f"--secretsDir {secrets_dir or '~/.local/share/lodestar/validators/secrets'}"
            ),
        },
        "teku": {
            "keys": keys_dir or "~/.local/share/teku/validator/keys",
            "secrets": secrets_dir or "~/.local/share/teku/validator/passwords",
            "config_file": "~/teku/validator.yaml",
            "import_command": (
                "teku validator-client --help  # import keys into the Teku validator key directory"
            ),
        },
        "nimbus": {
            "keys": keys_dir or "~/.local/share/nimbus/validators",
            "secrets": secrets_dir or "~/.local/share/nimbus/validators/secrets",
            "config_file": "~/nimbus/validator.toml",
            "import_command": (
                "nimbus_validator_client deposits import "
                f"--data-dir={keys_dir or '~/.local/share/nimbus/validators'}"
            ),
        },
        "grandine": {
            "keys": keys_dir or "~/.local/share/grandine/validators",
            "secrets": secrets_dir or "~/.local/share/grandine/validators/secrets",
            "config_file": "~/grandine/grandine.toml",
            "import_command": "Grandine validator import follows the upstream client workflow",
        },
    }

    selected = key_locations[consensus_client]
    post_import = [
        "sudo systemctl restart validator",
        "sudo systemctl status validator --no-pager",
        "./scripts/eth2qs.sh doctor --json",
    ]

    if consensus_client == "prysm" and wallet_password_file:
        post_import.insert(
            0,
            f"Ensure wallet-password-file points to {wallet_password_file}",
        )

    updates = {}
    if fee_recipient:
        updates["FEE_RECIPIENT"] = fee_recipient
    if graffiti:
        updates["GRAFITTI"] = graffiti

    return {
        "consensus_client": consensus_client,
        "config_updates": updates,
        "config_file": selected["config_file"],
        "keys_path": selected["keys"],
        "secrets_path": selected["secrets"],
        "import_command": selected["import_command"],
        "post_import_commands": post_import,
        "notes": [
            "The harness does not import validator keys automatically.",
            "Keep validator keystores and password files under operator control.",
            "Restart validator service after importing keys.",
        ],
    }

