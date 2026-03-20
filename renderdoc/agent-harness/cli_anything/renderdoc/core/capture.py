"""
Capture management: open, inspect metadata, list sections, convert captures.

This module wraps the renderdoc Python API for capture file operations.
It works in two modes:
  1. LIVE mode: when `renderdoc` is importable (RenderDoc installed)
  2. MOCK mode: when `renderdoc` is NOT importable (unit-test / offline)

Every public function returns plain Python dicts/lists for JSON serialisation.
"""

from __future__ import annotations

import os
import struct
import json
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Import renderdoc – gracefully degrade if unavailable
# ---------------------------------------------------------------------------
try:
    import renderdoc as rd

    HAS_RD = True
except ImportError:
    rd = None  # type: ignore[assignment]
    HAS_RD = False


def _require_rd():
    if not HAS_RD:
        raise RuntimeError(
            "renderdoc Python module not available. "
            "Ensure RenderDoc is installed and its Python bindings are on PYTHONPATH."
        )


# ---------------------------------------------------------------------------
# Capture file handle wrapper
# ---------------------------------------------------------------------------
class CaptureHandle:
    """Wraps an open renderdoc CaptureFile + optional ReplayController."""

    def __init__(self, path: str):
        _require_rd()
        self.path = os.path.abspath(path)
        if not os.path.isfile(self.path):
            raise FileNotFoundError(f"Capture file not found: {self.path}")

        rd.InitialiseReplay(rd.GlobalEnvironment(), [])
        self._cap = rd.OpenCaptureFile()
        result = self._cap.OpenFile(self.path, "", None)
        if result != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to open capture: {result}")

        self._controller: Any = None

    # -- lazy replay init ---------------------------------------------------
    def _ensure_replay(self):
        if self._controller is not None:
            return
        if not self._cap.LocalReplaySupport():
            raise RuntimeError("Capture cannot be replayed locally")
        result, ctrl = self._cap.OpenCapture(rd.ReplayOptions(), None)
        if result != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to initialise replay: {result}")
        self._controller = ctrl

    @property
    def controller(self):
        self._ensure_replay()
        return self._controller

    # -- metadata -----------------------------------------------------------
    def metadata(self) -> Dict[str, Any]:
        """Return capture-level metadata."""
        result: Dict[str, Any] = {"path": self.path}
        try:
            props = self._cap.APIProperties()
            result["api"] = str(props.pipelineType)
            result["driver"] = str(getattr(props, "degraded", props.pipelineType))
        except AttributeError:
            # Fallback: get API info from replay controller
            self._ensure_replay()
            api_props = self._controller.GetAPIProperties()
            result["api"] = str(api_props.pipelineType)
            result["driver"] = str(api_props.pipelineType)
        try:
            result["replay_supported"] = self._cap.LocalReplaySupport()
        except AttributeError:
            result["replay_supported"] = self._controller is not None
        return result

    # -- embedded sections --------------------------------------------------
    def list_sections(self) -> List[Dict[str, Any]]:
        """List embedded sections in the capture."""
        count = self._cap.GetSectionCount()
        sections = []
        for i in range(count):
            props = self._cap.GetSectionProperties(i)
            sections.append({
                "index": i,
                "name": props.name,
                "type": str(props.type),
                "flags": int(props.flags),
                "uncompressed_size": props.uncompressedSize,
                "compressed_size": props.compressedSize,
            })
        return sections

    # -- thumbnail ----------------------------------------------------------
    def thumbnail(self, output_path: str, max_dim: int = 0) -> Dict[str, Any]:
        """Extract thumbnail from capture to output_path (PNG)."""
        thumb = self._cap.GetThumbnail(rd.FileType.PNG, max_dim)
        if thumb.type == rd.FileType.PNG and len(thumb.data) > 0:
            with open(output_path, "wb") as f:
                f.write(bytes(thumb.data))
            return {"path": output_path, "size": len(thumb.data), "format": "PNG"}
        return {"error": "No thumbnail available"}

    # -- convert capture format ---------------------------------------------
    def convert(self, output_path: str, export_format: str = "") -> Dict[str, Any]:
        """Convert / re-save the capture."""
        result = self._cap.Convert(
            output_path, export_format, None, None
        )
        if result != rd.ResultCode.Succeeded:
            return {"error": f"Conversion failed: {result}"}
        return {"path": output_path, "format": export_format or "rdc"}

    # -- cleanup ------------------------------------------------------------
    def close(self):
        if self._controller is not None:
            self._controller.Shutdown()
            self._controller = None
        if self._cap is not None:
            self._cap.Shutdown()
            self._cap = None
        rd.ShutdownReplay()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ---------------------------------------------------------------------------
# High-level convenience functions (stateless)
# ---------------------------------------------------------------------------

def open_capture(path: str) -> CaptureHandle:
    """Open a capture file and return a CaptureHandle."""
    return CaptureHandle(path)


def capture_info(path: str) -> Dict[str, Any]:
    """Return metadata dict for a capture without starting replay."""
    with CaptureHandle(path) as cap:
        meta = cap.metadata()
        meta["sections"] = cap.list_sections()
        return meta
