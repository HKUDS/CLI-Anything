"""
Mesh data decoding: vertex inputs, post-VS outputs, index buffers.
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


def _unpack_data(fmt, data):
    """Unpack vertex data according to resource format."""
    if fmt.Special():
        return None  # packed formats not supported

    format_chars = {}
    format_chars[rd.CompType.UInt] = "xBHxIxxxL"
    format_chars[rd.CompType.SInt] = "xbhxixxxl"
    format_chars[rd.CompType.Float] = "xxexfxxxd"
    format_chars[rd.CompType.UNorm] = format_chars[rd.CompType.UInt]
    format_chars[rd.CompType.UScaled] = format_chars[rd.CompType.UInt]
    format_chars[rd.CompType.SNorm] = format_chars[rd.CompType.SInt]
    format_chars[rd.CompType.SScaled] = format_chars[rd.CompType.SInt]

    vertex_format = str(fmt.compCount) + format_chars[fmt.compType][fmt.compByteWidth]
    value = _struct.unpack_from(vertex_format, data, 0)

    if fmt.compType == rd.CompType.UNorm:
        divisor = float((2 ** (fmt.compByteWidth * 8)) - 1)
        value = tuple(float(i) / divisor for i in value)
    elif fmt.compType == rd.CompType.SNorm:
        max_neg = -float(2 ** (fmt.compByteWidth * 8)) / 2
        divisor = float(-(max_neg - 1))
        value = tuple(
            (float(i) if (i == max_neg) else (float(i) / divisor)) for i in value
        )

    if fmt.BGRAOrder():
        value = tuple(value[i] for i in [2, 1, 0, 3])

    return value


def get_mesh_inputs(controller, event_id: int, max_vertices: int = 100) -> Dict[str, Any]:
    """Get vertex shader input data at a draw call.

    Returns decoded vertex data for up to *max_vertices* vertices.
    """
    controller.SetFrameEvent(event_id, True)
    state = controller.GetPipelineState()

    ib = state.GetIBuffer()
    vbs = state.GetVBuffers()
    attrs = state.GetVertexInputs()

    # get draw info
    action = None
    for a in _flatten(controller.GetRootActions()):
        if a.eventId == event_id:
            action = a
            break
    if action is None:
        return {"error": f"No action at event {event_id}"}

    # Decode indices
    indices = _get_indices(controller, ib, action)
    num = min(len(indices), max_vertices)

    attributes = []
    for attr in attrs:
        attr_data = {
            "name": str(attr.name),
            "format": str(attr.format),
            "vertices": [],
        }
        if attr.perInstance:
            attr_data["perInstance"] = True
            attributes.append(attr_data)
            continue

        vb = vbs[attr.vertexBuffer]
        for i in range(num):
            idx = indices[i]
            offset = (
                attr.byteOffset
                + vb.byteOffset
                + (idx + action.vertexOffset) * vb.byteStride
            )
            data = controller.GetBufferData(vb.resourceId, offset, 64)
            try:
                val = _unpack_data(attr.format, bytes(data))
                attr_data["vertices"].append({"index": idx, "value": list(val) if val else None})
            except Exception as e:
                attr_data["vertices"].append({"index": idx, "error": str(e)})

        attributes.append(attr_data)

    return {
        "eventId": event_id,
        "numIndices": action.numIndices,
        "decoded_count": num,
        "attributes": attributes,
    }


def get_mesh_outputs(controller, event_id: int, max_vertices: int = 100) -> Dict[str, Any]:
    """Get post-vertex-shader output data at a draw call."""
    controller.SetFrameEvent(event_id, True)

    postvs = controller.GetPostVSData(0, 0, rd.MeshDataStage.VSOut)
    if postvs.vertexResourceId == rd.ResourceId.Null():
        return {"eventId": event_id, "error": "No post-VS data available"}

    vs = controller.GetPipelineState().GetShaderReflection(rd.ShaderStage.Vertex)
    if vs is None:
        return {"eventId": event_id, "error": "No vertex shader bound"}

    outputs = []
    for attr in vs.outputSignature:
        outputs.append({
            "name": attr.semanticIdxName if attr.varName == "" else str(attr.varName),
            "compCount": attr.compCount,
            "systemValue": str(attr.systemValue),
        })

    return {
        "eventId": event_id,
        "numIndices": postvs.numIndices,
        "outputs": outputs,
    }


def _flatten(actions, out=None):
    if out is None:
        out = []
    for a in actions:
        out.append(a)
        if len(a.children) > 0:
            _flatten(a.children, out)
    return out


def _get_indices(controller, ib, action):
    """Decode index buffer."""
    if action.flags & rd.ActionFlags.Indexed and ib.resourceId != rd.ResourceId.Null():
        idx_fmt = "B"
        if ib.byteStride == 2:
            idx_fmt = "H"
        elif ib.byteStride == 4:
            idx_fmt = "I"

        ibdata = controller.GetBufferData(ib.resourceId, ib.byteOffset, 0)
        offset = action.indexOffset * ib.byteStride
        fmt_str = str(action.numIndices) + idx_fmt
        try:
            indices = _struct.unpack_from(fmt_str, bytes(ibdata), offset)
            return [i + action.baseVertex for i in indices]
        except Exception:
            return list(range(action.numIndices))
    else:
        return list(range(action.numIndices))
