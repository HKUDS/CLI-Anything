"""RPC exposure helpers."""

from __future__ import annotations

from cli_anything.eth2_quickstart.core.commands import VALID_WEB_STACKS
from cli_anything.eth2_quickstart.core.project import upsert_user_config


def start_rpc(
    backend,
    *,
    web_stack: str,
    server_name: str | None = None,
    ssl: bool = False,
) -> dict:
    if web_stack not in VALID_WEB_STACKS:
        raise ValueError(f"Unsupported web stack: {web_stack}")

    config_path = None
    if server_name:
        config_path = upsert_user_config(backend.repo_root, {"SERVER_NAME": server_name})

    suffix = "_ssl" if ssl else ""
    script = f"install/web/install_{web_stack}{suffix}.sh"
    result = backend.run_script(script)
    result["config_path"] = str(config_path) if config_path else None
    result["rpc_url"] = (
        f"{'https' if ssl else 'http'}://{server_name}/rpc" if server_name else None
    )
    result["ws_url"] = (
        f"{'https' if ssl else 'http'}://{server_name}/ws" if server_name else None
    )
    result["web_stack"] = web_stack
    result["ssl"] = ssl
    return result

