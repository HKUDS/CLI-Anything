"""SiYuan backend integration.

Provides helper functions to find a running SiYuan instance and verify
connectivity. Since SiYuan has no headless CLI mode, this module handles
the connection check and configuration discovery.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from cli_anything.siyuan.core.client import SiYuanClient, SiYuanClientError, SiYuanConfig


def find_siyuan_data_dir() -> str | None:
    """Try to locate the SiYuan data directory.

    Checks platform-specific default locations:
    - Windows: %USERPROFILE%\\SiYuan\\data\\
    - Linux: ~/.config/siyuan/data/
    - macOS: ~/.config/siyuan/data/
    """
    home = Path.home()
    candidates = []

    if sys.platform == "win32":
        candidates.append(home / "SiYuan" / "data")
    else:
        candidates.append(home / ".config" / "siyuan" / "data")

    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate.resolve())

    return None


def check_siyuan_running(config: SiYuanConfig | None = None) -> dict[str, Any]:
    """Check if a SiYuan instance is reachable and return its status.

    Returns:
        dict with keys: connected (bool), version (str), error (str)
    """
    if config is None:
        from cli_anything.siyuan.core.client import load_config
        config = load_config()

    client = SiYuanClient(config)
    try:
        version = client.get_version()
        return {"connected": True, "version": version, "error": ""}
    except SiYuanClientError as e:
        return {"connected": False, "version": "", "error": str(e)}


def get_api_token_from_conf() -> str:
    """Try to read the API token from SiYuan config files.

    Returns empty string if not found.
    """
    home = Path.home()
    candidates = []

    if sys.platform == "win32":
        candidates.append(home / "SiYuan" / "conf" / "conf.json")
    else:
        candidates.append(home / ".config" / "siyuan" / "conf" / "conf.json")

    import json
    for conf_path in candidates:
        if conf_path.is_file():
            try:
                data = json.loads(conf_path.read_text(encoding="utf-8"))
                token = data.get("api", {}).get("token", "")
                if token:
                    return token
            except (json.JSONDecodeError, KeyError, OSError):
                continue

    return ""
