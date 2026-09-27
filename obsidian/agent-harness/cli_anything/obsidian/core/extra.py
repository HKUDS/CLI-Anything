"""Tags, local vault registry, and daily notes.

Local REST API v5 dropped /periodic/, so daily notes are plain vault files at
<folder>/<YYYY-MM-DD>.md (Obsidian's default Daily Notes format).
"""

import datetime as _dt
import json
import os
import re
import sys
from urllib.parse import quote

from cli_anything.obsidian.utils.obsidian_backend import api_get
from cli_anything.obsidian.core import vault as vault_mod


def list_tags(base_url: str, api_key: str) -> dict:
    return api_get(base_url, "/tags/", api_key)


def _registry_path() -> str:
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("APPDATA", "")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "obsidian", "obsidian.json")


def list_vaults(registry: str | None = None) -> list[dict]:
    """Vaults known to the Obsidian app (reads its obsidian.json; no API needed)."""
    registry = registry or _registry_path()
    if not os.path.exists(registry):
        return []
    with open(registry, encoding="utf-8") as fh:
        vaults = json.load(fh).get("vaults", {})
    return [{"id": vid, "name": os.path.basename(v["path"].rstrip("/")),
             "path": v["path"], "open": bool(v.get("open"))}
            for vid, v in vaults.items()]


def vault_uri(name: str, file: str | None = None) -> str:
    uri = f"obsidian://open?vault={quote(name)}"
    return uri + (f"&file={quote(file)}" if file else "")


def daily_path(date: str | None = None, folder: str = "") -> str:
    d = _dt.date.fromisoformat(date) if date else _dt.date.today()
    folder = folder.strip("/")
    return f"{folder}/{d.isoformat()}.md" if folder else f"{d.isoformat()}.md"


def daily_list(base_url: str, api_key: str, folder: str = "") -> list[str]:
    files = vault_mod.list_files(base_url, api_key, folder or "/").get("files", [])
    prefix = f"{folder.strip('/')}/" if folder.strip("/") else ""
    return sorted(prefix + f for f in files if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f))


def daily_create(base_url: str, api_key: str, date: str | None = None,
                 folder: str = "", content: str | None = None) -> dict:
    """Create the daily note if missing; never overwrites an existing one."""
    path = daily_path(date, folder)
    try:
        existing = vault_mod.read_note(base_url, api_key, path)
        return {"path": path, "created": False, "content": existing.get("content", "")}
    except RuntimeError as e:
        if " 404 " not in str(e):
            raise
    body = content if content is not None else f"# {path.rsplit('/', 1)[-1][:-3]}\n"
    vault_mod.create_note(base_url, api_key, path, body)
    return {"path": path, "created": True, "content": body}
