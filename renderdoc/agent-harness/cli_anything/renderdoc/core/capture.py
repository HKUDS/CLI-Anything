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
from typing import Any, Dict, List, Optional

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


def _api_properties_summary(props: Any) -> Dict[str, Any]:
    """JSON-friendly subset of CaptureFile.APIProperties / GetAPIProperties."""
    out: Dict[str, Any] = {"api": str(props.pipelineType)}
    if hasattr(props, "degraded"):
        out["degraded"] = bool(props.degraded)
    driver = None
    for attr in ("localRenderer", "vendor"):
        if hasattr(props, attr):
            val = getattr(props, attr)
            if val is not None and str(val):
                driver = str(val)
                break
    out["driver"] = driver if driver is not None else str(props.pipelineType)
    return out


# ---------------------------------------------------------------------------
# Global RenderDoc replay API (InitialiseReplay / ShutdownReplay) — refcounted
# ---------------------------------------------------------------------------
_replay_refcount = 0


def _ensure_replay_api():
    """Initialise RenderDoc replay once; pair with ``_release_replay_api`` per handle."""
    global _replay_refcount
    _require_rd()
    if _replay_refcount == 0:
        rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    _replay_refcount += 1


def _release_replay_api():
    """Shut down replay when the last CaptureHandle in the process closes."""
    global _replay_refcount
    if not HAS_RD or _replay_refcount <= 0:
        return
    _replay_refcount -= 1
    if _replay_refcount == 0:
        rd.ShutdownReplay()


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

        _ensure_replay_api()
        try:
            self._cap = rd.OpenCaptureFile()
            result = self._cap.OpenFile(self.path, "", None)
            if result != rd.ResultCode.Succeeded:
                raise RuntimeError(f"Failed to open capture: {result}")
        except Exception:
            _release_replay_api()
            raise

        self._controller: Any = None
        self._closed = False

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
            result.update(_api_properties_summary(props))
        except AttributeError:
            self._ensure_replay()
            api_props = self._controller.GetAPIProperties()
            result.update(_api_properties_summary(api_props))
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
        if getattr(self, "_closed", False):
            return
        self._closed = True
        if self._controller is not None:
            self._controller.Shutdown()
            self._controller = None
        if self._cap is not None:
            self._cap.Shutdown()
            self._cap = None
        _release_replay_api()

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
