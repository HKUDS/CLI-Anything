"""Connection configuration management for cli-anything-adguardhome."""

import json
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "cli-anything-adguardhome.json"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3000


def load_config(config_path: Path | None = None) -> dict:
    """Load connection config from file, with env var and default fallbacks."""
    path = config_path or DEFAULT_CONFIG_PATH
    config: dict = {
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "username": "",
        "password": "",
    }
    if path.exists():
        try:
            with open(path) as f:
                file_config = json.load(f)
            for key in ("host", "port", "username", "password"):
                if key in file_config:
                    config[key] = file_config[key]
        except (json.JSONDecodeError, OSError):
            pass
    if os.getenv("AGH_HOST"):
        config["host"] = os.environ["AGH_HOST"]
    if os.getenv("AGH_PORT"):
        config["port"] = int(os.environ["AGH_PORT"])
    if os.getenv("AGH_USERNAME"):
        config["username"] = os.environ["AGH_USERNAME"]
    if os.getenv("AGH_PASSWORD"):
        config["password"] = os.environ["AGH_PASSWORD"]
    return config


def save_config(host: str, port: int, username: str, password: str,
                config_path: Path | None = None) -> Path:
    """Save connection settings to config file."""
    path = config_path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"host": host, "port": port, "username": username, "password": password}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path
