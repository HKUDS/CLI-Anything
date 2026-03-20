"""
Resource inspection: list buffers, get buffer data, enumerate all resources.
"""

from __future__ import annotations

import struct as _struct
from typing import Any, Dict, List, Optional

try:
    import renderdoc as rd

    HAS_RD = True
except ImportError:
    rd = None  # type: ignore[assignment]
    HAS_RD = False


def list_resources(controller) -> List[Dict[str, Any]]:
    """List all resources in the capture."""
    resources = controller.GetResources()
    return [
        {
            "resourceId": str(r.resourceId),
            "name": str(r.name),
            "type": str(r.type),
        }
        for r in resources
    ]


def list_buffers(controller) -> List[Dict[str, Any]]:
    """List all buffer resources."""
    buffers = controller.GetBuffers()
    return [
        {
            "resourceId": str(b.resourceId),
            "length": b.length,
            "creationFlags": int(b.creationFlags),
        }
        for b in buffers
    ]


def get_buffer_data(
    controller,
    resource_id_str: str,
    offset: int = 0,
    length: int = 0,
    fmt: str = "hex",
) -> Dict[str, Any]:
    """Read raw buffer data.

    Parameters
    ----------
    fmt : str
        'hex' returns hex string, 'float32' unpacks as floats,
        'uint32' unpacks as unsigned ints, 'raw' returns byte list.
    """
    buf_id = None
    for b in controller.GetBuffers():
        if str(b.resourceId) == resource_id_str:
            buf_id = b.resourceId
            break
    if buf_id is None:
        return {"error": f"Buffer {resource_id_str} not found"}

    data = controller.GetBufferData(buf_id, offset, length)
    raw_bytes = bytes(data)

    result: Dict[str, Any] = {
        "resourceId": resource_id_str,
        "offset": offset,
        "length": len(raw_bytes),
    }

    if fmt == "hex":
        result["data"] = raw_bytes.hex()
    elif fmt == "float32":
        count = len(raw_bytes) // 4
        result["data"] = list(_struct.unpack(f"<{count}f", raw_bytes[: count * 4]))
    elif fmt == "uint32":
        count = len(raw_bytes) // 4
        result["data"] = list(_struct.unpack(f"<{count}I", raw_bytes[: count * 4]))
    elif fmt == "raw":
        result["data"] = list(raw_bytes)
    else:
        result["data"] = raw_bytes.hex()

    return result
