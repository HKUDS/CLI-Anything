"""FileTransformBackend — read, transform, and write project files.

Supports XML (ElementTree), JSON, and plain text transformations.

Example macro step:

    - backend: file_transform
      action: json_set
      params:
        input_file: ${project_file}
        output_file: ${project_file}
        path: settings.grid_size
        value: 20

    - backend: file_transform
      action: xml_set_attr
      params:
        input_file: diagram.drawio
        output_file: diagram.drawio
        xpath: .//mxCell[@id='1']
        attr: style
        value: rounded=1;

    - backend: file_transform
      action: text_replace
      params:
        input_file: config.ini
        output_file: config.ini
        find: "theme=default"
        replace: "theme=dark"
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from cli_anything.macrocli.backends.base import Backend, BackendContext, StepResult
from cli_anything.macrocli.core.macro_model import MacroStep, substitute


class FileTransformBackend(Backend):
    """Transform project files without invoking the target application."""

    name = "file_transform"
    priority = 70

    def execute(self, step: MacroStep, params: dict, context: BackendContext) -> StepResult:
        t0 = time.time()
        action = step.action
        step_params = substitute(step.params, params)

        if context.dry_run:
            return StepResult(
                success=True,
                output={"dry_run": True, "action": action},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        dispatch = {
            "json_get": self._json_get,
            "json_set": self._json_set,
            "json_delete": self._json_delete,
            "xml_set_attr": self._xml_set_attr,
            "xml_get_attr": self._xml_get_attr,
            "text_replace": self._text_replace,
            "copy_file": self._copy_file,
        }

        handler = dispatch.get(action)
        if handler is None:
            return StepResult(
                success=False,
                error=f"FileTransformBackend: unknown action '{action}'.",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

        try:
            output = handler(step_params)
            return StepResult(
                success=True,
                output=output or {},
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )
        except Exception as exc:
            return StepResult(
                success=False,
                error=f"FileTransformBackend.{action}: {exc}",
                backend_used=self.name,
                duration_ms=(time.time() - t0) * 1000,
            )

    # ── JSON actions ─────────────────────────────────────────────────────

    def _json_get(self, p: dict) -> dict:
        """Read a value from a JSON file by dot-path."""
        data = self._load_json(p["input_file"])
        val = self._dotpath_get(data, p["path"])
        return {"value": val, "path": p["path"]}

    def _json_set(self, p: dict) -> dict:
        """Set a value in a JSON file by dot-path and write it back."""
        path = p.get("path", "")
        value = p["value"]
        data = self._load_json(p["input_file"]) if Path(p["input_file"]).is_file() else {}
        self._dotpath_set(data, path, value)
        self._save_json(p.get("output_file", p["input_file"]), data)
        return {"path": path, "value": value}

    def _json_delete(self, p: dict) -> dict:
        """Delete a key from a JSON file by dot-path."""
        data = self._load_json(p["input_file"])
        self._dotpath_delete(data, p["path"])
        self._save_json(p.get("output_file", p["input_file"]), data)
        return {"deleted": p["path"]}

    # ── XML actions ──────────────────────────────────────────────────────

    def _xml_set_attr(self, p: dict) -> dict:
        """Set an XML element attribute matched by XPath."""
        from xml.etree import ElementTree as ET
        tree = ET.parse(p["input_file"])
        root = tree.getroot()
        elements = root.findall(p["xpath"])
        if not elements:
            raise ValueError(f"XPath matched nothing: {p['xpath']}")
        for el in elements:
            el.set(p["attr"], str(p["value"]))
        tree.write(p.get("output_file", p["input_file"]), encoding="unicode", xml_declaration=True)
        return {"matched": len(elements), "attr": p["attr"]}

    def _xml_get_attr(self, p: dict) -> dict:
        """Get an XML element attribute matched by XPath."""
        from xml.etree import ElementTree as ET
        tree = ET.parse(p["input_file"])
        root = tree.getroot()
        elements = root.findall(p["xpath"])
        values = [el.get(p["attr"]) for el in elements]
        return {"values": values, "attr": p["attr"]}

    # ── Text actions ─────────────────────────────────────────────────────

    def _text_replace(self, p: dict) -> dict:
        """Simple find-and-replace in a text file."""
        content = Path(p["input_file"]).read_text(encoding="utf-8")
        count = content.count(p["find"])
        content = content.replace(p["find"], p["replace"])
        out = p.get("output_file", p["input_file"])
        Path(out).write_text(content, encoding="utf-8")
        return {"replacements": count}

    def _copy_file(self, p: dict) -> dict:
        """Copy a file from src to dst."""
        import shutil
        shutil.copy2(p["src"], p["dst"])
        size = os.path.getsize(p["dst"])
        return {"src": p["src"], "dst": p["dst"], "size": size}

    # ── Helpers ──────────────────────────────────────────────────────────

    def _load_json(self, path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, path: str, data: dict) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _dotpath_get(self, data: dict, path: str):
        keys = path.split(".")
        cur = data
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return None
        return cur

    def _dotpath_set(self, data: dict, path: str, value) -> None:
        keys = path.split(".")
        cur = data
        for k in keys[:-1]:
            if k not in cur or not isinstance(cur[k], dict):
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = value

    def _dotpath_delete(self, data: dict, path: str) -> None:
        keys = path.split(".")
        cur = data
        for k in keys[:-1]:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return
        if isinstance(cur, dict) and keys[-1] in cur:
            del cur[keys[-1]]
