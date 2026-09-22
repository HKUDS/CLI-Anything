"""SiYuan HTTP API client.

Handles connection, authentication, and request/response to the SiYuan kernel.
"""

import html
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


def _unescape_tag_names(tags: Any) -> list[dict[str, Any]]:
    """Decode HTML entities in tag names, recursively.

    The kernel escapes tag names before returning them
    (`util.EscapeHTML` in kernel/model/tag.go) because its own consumers
    render HTML; a terminal client must undo that, or a tag reads
    ``-&gt;return-type`` instead of ``->return-type``.
    """
    result: list[dict[str, Any]] = []
    if not isinstance(tags, list):
        return result
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        node = dict(tag)
        if isinstance(node.get("name"), str):
            node["name"] = html.unescape(node["name"])
        children = node.get("children")
        if isinstance(children, list):
            node["children"] = _unescape_tag_names(children)
        result.append(node)
    return result


@dataclass(frozen=True)
class SiYuanConfig:
    host: str = "127.0.0.1"
    port: int = 6806
    token: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def _parse_port(value: Any, default: int = 6806) -> int:
    """Parse a port from config/env; invalid values degrade to default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_config(config_path: str | None = None) -> SiYuanConfig:
    """Load SiYuan connection config from file or environment.

    Priority: explicit path -> env vars -> defaults.
    Config file is JSON: {"host": "...", "port": 6806, "token": "..."}
    Corrupt files / invalid values degrade to the next layer, never crash.
    """
    if config_path:
        config_file = Path(config_path)
    else:
        config_file = Path.home() / ".siyuan-cli.json"

    if config_file.is_file():
        data = None
        try:
            data = json.loads(config_file.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            data = None

        if isinstance(data, dict):
            # File values as base, env vars override; an invalid env value
            # degrades to the file-configured port, not the built-in default
            file_port = _parse_port(data.get("port", 6806))
            return SiYuanConfig(
                host=os.environ.get("SIYUAN_HOST", data.get("host", "127.0.0.1")),
                port=_parse_port(os.environ.get("SIYUAN_PORT"), file_port),
                token=os.environ.get("SIYUAN_TOKEN", data.get("token", "")),
            )

    return SiYuanConfig(
        host=os.environ.get("SIYUAN_HOST", "127.0.0.1"),
        port=_parse_port(os.environ.get("SIYUAN_PORT", "6806")),
        token=os.environ.get("SIYUAN_TOKEN", ""),
    )


class SiYuanClientError(Exception):
    """Raised when the SiYuan API returns an error."""


class SiYuanClient:
    """HTTP client for the SiYuan kernel API."""

    def __init__(self, config: SiYuanConfig | None = None):
        self.config = config or load_config()
        self._session = requests.Session()
        self._session.trust_env = False
        if self.config.token:
            self._session.headers["Authorization"] = f"Token {self.config.token}"
        self._session.headers["Content-Type"] = "application/json"

    def _request(self, endpoint: str, timeout: int = 30, **kwargs: Any) -> Any:
        """POST to the SiYuan API and unwrap the response envelope."""
        url = f"{self.config.base_url}{endpoint}"
        try:
            resp = self._session.post(url, timeout=timeout, **kwargs)
        except requests.ConnectionError as e:
            raise SiYuanClientError(
                f"Cannot connect to SiYuan at {self.config.base_url}. "
                f"Is SiYuan running? ({e})"
            ) from e
        except requests.Timeout as e:
            raise SiYuanClientError(
                f"Request to SiYuan timed out after {timeout}s ({e})"
            ) from e
        except requests.RequestException as e:
            raise SiYuanClientError(
                f"Request to SiYuan failed: {e}"
            ) from e

        if resp.status_code != 200:
            raise SiYuanClientError(
                f"API returned status {resp.status_code}: {resp.text[:200]}"
            )

        try:
            body = resp.json()
        except ValueError as e:
            raise SiYuanClientError(
                f"Response from {self.config.base_url} is not valid JSON — is "
                f"this really a SiYuan kernel? ({resp.text[:120]})"
            ) from e
        code = body.get("code", 0) if isinstance(body, dict) else -1
        if code != 0:
            msg = body.get("msg", "unknown error") if isinstance(body, dict) else str(body)
            raise SiYuanClientError(f"API error: {msg}")
        return body.get("data") if isinstance(body, dict) else body

    def _post(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """Make a JSON POST request to the SiYuan API."""
        return self._request(endpoint, json=data or {})

    def ping(self) -> bool:
        """Check if SiYuan kernel is reachable."""
        try:
            return self._post("/api/system/version") is not None
        except SiYuanClientError:
            return False

    # ── Notebook API ───────────────────────────────────────────────────

    def list_notebooks(self) -> list[dict[str, Any]]:
        """List all notebooks."""
        data = self._post("/api/notebook/lsNotebooks")
        if not isinstance(data, dict):
            return []
        return data.get("notebooks", [])

    def open_notebook(self, notebook_id: str) -> None:
        self._post("/api/notebook/openNotebook", {"notebook": notebook_id})

    def close_notebook(self, notebook_id: str) -> None:
        self._post("/api/notebook/closeNotebook", {"notebook": notebook_id})

    def create_notebook(self, name: str) -> dict[str, Any]:
        data = self._post("/api/notebook/createNotebook", {"name": name})
        if isinstance(data, dict) and "notebook" in data:
            return data["notebook"]
        return data

    def remove_notebook(self, notebook_id: str) -> None:
        self._post("/api/notebook/removeNotebook", {"notebook": notebook_id})

    def rename_notebook(self, notebook_id: str, name: str) -> None:
        self._post("/api/notebook/renameNotebook", {"notebook": notebook_id, "name": name})

    def get_notebook_conf(self, notebook_id: str) -> dict[str, Any]:
        return self._post("/api/notebook/getNotebookConf", {"notebook": notebook_id})

    def set_notebook_conf(self, notebook_id: str, conf: dict[str, Any]) -> dict[str, Any]:
        return self._post("/api/notebook/setNotebookConf", {"notebook": notebook_id, "conf": conf})

    def set_notebook_icon(self, notebook_id: str, icon: str) -> None:
        self._post("/api/notebook/setNotebookIcon", {"notebook": notebook_id, "icon": icon})

    def get_notebook_info(self, notebook_id: str) -> dict[str, Any]:
        return self._post("/api/notebook/getNotebookInfo", {"notebook": notebook_id})

    # ── Document / Filetree API ────────────────────────────────────────

    def create_doc_with_md(self, notebook_id: str, path: str, markdown: str = "") -> str:
        """Create a document with Markdown content. Returns the doc ID."""
        return self._post("/api/filetree/createDocWithMd", {
            "notebook": notebook_id, "path": path, "markdown": markdown,
        })

    def rename_doc(self, notebook_id: str, path: str, title: str) -> None:
        self._post("/api/filetree/renameDoc", {"notebook": notebook_id, "path": path, "title": title})

    def rename_doc_by_id(self, doc_id: str, title: str) -> None:
        self._post("/api/filetree/renameDocByID", {"id": doc_id, "title": title})

    def remove_doc(self, notebook_id: str, path: str) -> None:
        self._post("/api/filetree/removeDoc", {"notebook": notebook_id, "path": path})

    def remove_doc_by_id(self, doc_id: str) -> None:
        self._post("/api/filetree/removeDocByID", {"id": doc_id})

    def move_docs(self, from_paths: list[str], to_notebook: str, to_path: str) -> None:
        self._post("/api/filetree/moveDocs", {
            "fromPaths": from_paths, "toNotebook": to_notebook, "toPath": to_path,
        })

    def move_docs_by_id(self, from_ids: list[str], to_id: str) -> None:
        self._post("/api/filetree/moveDocsByID", {"fromIDs": from_ids, "toID": to_id})

    def get_hpath_by_id(self, block_id: str) -> str:
        return self._post("/api/filetree/getHPathByID", {"id": block_id})

    def get_path_by_id(self, block_id: str) -> dict[str, str]:
        return self._post("/api/filetree/getPathByID", {"id": block_id})

    def get_ids_by_hpath(self, notebook_id: str, path: str) -> list[str]:
        return self._post("/api/filetree/getIDsByHPath", {"notebook": notebook_id, "path": path})

    def list_docs_by_path(self, notebook_id: str, path: str) -> dict[str, Any]:
        return self._post("/api/filetree/listDocsByPath", {
            "notebook": notebook_id, "path": path, "maxListCount": 0,
        })

    def list_doc_tree(self, notebook_id: str, path: str = "/", max_depth: int = -1) -> dict[str, Any]:
        """Recursively list the document tree rooted at path.

        `filetree/listDocTree` returns only `{id, children}` — its `DocFile`
        struct carries no name or path (kernel/api/filetree.go), so it cannot
        feed a display. The tree is built from listDocsByPath instead, which
        does carry the fields the commands print.
        """
        return {"files": self._list_doc_dir(notebook_id, path, max_depth, 0)}

    def _list_doc_dir(self, notebook_id: str, path: str, max_depth: int, depth: int) -> list[dict[str, Any]]:
        data = self.list_docs_by_path(notebook_id, path)
        files = data.get("files") if isinstance(data, dict) else data or []
        nodes: list[dict[str, Any]] = []
        for f in files:
            node = {
                "id": f.get("id", ""),
                "name": f.get("name", ""),
                "path": f.get("path", path),
            }
            if f.get("subFileCount", 0) > 0 and (max_depth < 0 or depth < max_depth):
                node["children"] = self._list_doc_dir(notebook_id, node["path"], max_depth, depth + 1)
            nodes.append(node)
        return nodes

    def search_docs(self, keyword: str) -> list[dict[str, Any]]:
        return self._post("/api/filetree/searchDocs", {"k": keyword})

    def create_daily_note(self, notebook_id: str) -> dict[str, Any]:
        return self._post("/api/filetree/createDailyNote", {"notebook": notebook_id})

    # ── Block API ──────────────────────────────────────────────────────

    def insert_block(self, data_type: str, data: str,
                     parent_id: str = "", previous_id: str = "", next_id: str = "") -> list[dict[str, Any]]:
        params = {"dataType": data_type, "data": data}
        if parent_id:
            params["parentID"] = parent_id
        if previous_id:
            params["previousID"] = previous_id
        if next_id:
            params["nextID"] = next_id
        return self._post("/api/block/insertBlock", params)

    def prepend_block(self, data_type: str, data: str, parent_id: str) -> list[dict[str, Any]]:
        return self._post("/api/block/prependBlock", {
            "dataType": data_type, "data": data, "parentID": parent_id,
        })

    def append_block(self, data_type: str, data: str, parent_id: str) -> list[dict[str, Any]]:
        return self._post("/api/block/appendBlock", {
            "dataType": data_type, "data": data, "parentID": parent_id,
        })

    def update_block(self, data_type: str, data: str, block_id: str) -> list[dict[str, Any]]:
        try:
            return self._post("/api/block/updateBlock", {
                "dataType": data_type, "data": data, "id": block_id,
            })
        except SiYuanClientError as e:
            msg = str(e).lower()
            if any(k in msg for k in ("not found", "notfound", "未找到", "不存在")):
                raise SiYuanClientError(
                    f"{e}. The target may be a document root block (doc ID), "
                    f"which is not a block in the block tree and cannot be "
                    f"updated via block update. Update a content block inside "
                    f"the document instead — find one with `block children "
                    f"<docId>` or `sql`, then update that child ID. Avoid "
                    f"deleting and recreating the document: that would replace "
                    f"the child block IDs and invalidate any references to them."
                ) from e
            raise

    def delete_block(self, block_id: str) -> list[dict[str, Any]]:
        return self._post("/api/block/deleteBlock", {"id": block_id})

    def move_block(self, block_id: str, previous_id: str = "", parent_id: str = "") -> list[dict[str, Any]]:
        params = {"id": block_id}
        if previous_id:
            params["previousID"] = previous_id
        if parent_id:
            params["parentID"] = parent_id
        return self._post("/api/block/moveBlock", params)

    def fold_block(self, block_id: str) -> None:
        self._post("/api/block/foldBlock", {"id": block_id})

    def unfold_block(self, block_id: str) -> None:
        self._post("/api/block/unfoldBlock", {"id": block_id})

    def get_block_kramdown(self, block_id: str) -> str:
        data = self._post("/api/block/getBlockKramdown", {"id": block_id})
        return data.get("kramdown", "") if isinstance(data, dict) else ""

    def get_child_blocks(self, block_id: str) -> list[dict[str, Any]]:
        return self._post("/api/block/getChildBlocks", {"id": block_id})

    # ── Attribute API ──────────────────────────────────────────────────

    def set_block_attrs(self, block_id: str, attrs: dict[str, str]) -> None:
        self._post("/api/attr/setBlockAttrs", {"id": block_id, "attrs": attrs})

    def get_block_attrs(self, block_id: str) -> dict[str, str]:
        return self._post("/api/attr/getBlockAttrs", {"id": block_id})

    # ── Asset API ──────────────────────────────────────────────────────

    def upload_asset(self, file_paths: list[str],
                     assets_dir_path: str = "/assets/") -> dict[str, Any]:
        """Upload local files as workspace assets.

        Returns the kernel payload: ``{"errFiles": [...], "succMap": {...}}``.
        The session carries a JSON Content-Type by default; passing
        ``Content-Type: None`` drops it for this call so requests can set the
        multipart boundary itself — a leftover ``application/json`` header
        makes the kernel reject the form.
        """
        handles = []
        files = []
        try:
            for path in file_paths:
                try:
                    handle = open(path, "rb")
                except OSError as e:
                    raise SiYuanClientError(f"Cannot read '{path}': {e}") from e
                handles.append(handle)
                files.append(("file[]", (Path(path).name, handle)))
            return self._request(
                "/api/asset/upload",
                timeout=300,
                data={"assetsDirPath": assets_dir_path},
                files=files,
                headers={"Content-Type": None},
            )
        finally:
            for handle in handles:
                handle.close()

    # ── SQL Query API ──────────────────────────────────────────────────

    def query_sql(self, stmt: str) -> list[dict[str, Any]]:
        return self._post("/api/query/sql", {"stmt": stmt})

    # ── Search API ─────────────────────────────────────────────────────

    def search_blocks(self, query: str, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        return self._post("/api/search/fullTextSearchBlock", {
            "query": query, "page": page, "pageSize": page_size,
        })

    def search_tag(self, tag: str = "") -> list[str]:
        """Search tags. Returns list of tag name strings (HTML entities decoded)."""
        data = self._post("/api/search/searchTag", {"k": tag})
        if isinstance(data, dict):
            return [html.unescape(t) if isinstance(t, str) else t
                    for t in data.get("tags", [])]
        return [html.unescape(t) if isinstance(t, str) else t for t in data or []]

    def find_replace(self, keyword: str, replacement: str, ids: list[str]) -> None:
        """Search and replace text in blocks by ID."""
        self._post("/api/search/findReplace", {
            "k": keyword, "r": replacement, "ids": ids,
        })

    # ── Export API ─────────────────────────────────────────────────────

    def export_md_content(self, doc_id: str) -> dict[str, str]:
        return self._post("/api/export/exportMdContent", {"id": doc_id})

    def export_resources(self, paths: list[str], name: str = "") -> str:
        params = {"paths": paths}
        if name:
            params["name"] = name
        data = self._post("/api/export/exportResources", params)
        return data.get("path", "") if isinstance(data, dict) else ""

    # ── Tag API ────────────────────────────────────────────────────────

    def get_tags(self) -> list[dict[str, Any]]:
        """List tags. Returns tag dicts with HTML entities in names decoded.

        The kernel replies with a bare array; accept a ``{"tags": [...]}``
        wrapper too, so a shape change degrades the same way ``search_tag``
        does instead of silently listing nothing.
        """
        data = self._post("/api/tag/getTag", {"ignoreMaxListHint": True})
        if isinstance(data, dict):
            data = data.get("tags")
        return _unescape_tag_names(data)

    # ── System API ─────────────────────────────────────────────────────

    def get_version(self) -> str:
        return self._post("/api/system/version")

    def get_current_time(self) -> int:
        return self._post("/api/system/currentTime")
