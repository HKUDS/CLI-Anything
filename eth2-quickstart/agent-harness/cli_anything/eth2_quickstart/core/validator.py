"""Validator configuration helpers."""

from __future__ import annotations

from cli_anything.eth2_quickstart.core.commands import validator_plan
from cli_anything.eth2_quickstart.core.project import upsert_user_config


def configure_validator(
    backend,
    *,
    consensus_client: str,
    fee_recipient: str | None = None,
    graffiti: str | None = None,
    keys_dir: str | None = None,
    secrets_dir: str | None = None,
    wallet_password_file: str | None = None,
) -> dict:
    plan = validator_plan(
        consensus_client=consensus_client,
        fee_recipient=fee_recipient,
        graffiti=graffiti,
        keys_dir=keys_dir,
        secrets_dir=secrets_dir,
        wallet_password_file=wallet_password_file,
    )
    config_path = None
    if plan["config_updates"]:
        config_path = upsert_user_config(backend.repo_root, plan["config_updates"])

    return {
        "repo_root": str(backend.repo_root),
        "config_path": str(config_path) if config_path else None,
        "plan": plan,
        "ok": True,
    }

