"""
Pipeline state inspection.

Inspect the full graphics/compute pipeline state at any event:
shader stages, bound resources, viewports, blend state, depth/stencil, etc.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    import renderdoc as rd

    HAS_RD = hasattr(rd, "ShaderStage")
except ImportError:
    rd = None  # type: ignore[assignment]
    HAS_RD = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: str, data: Any) -> None:
    """Write data as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Pipeline state at a given event
# ---------------------------------------------------------------------------

def get_pipeline_state(controller, event_id: int) -> Dict[str, Any]:
    """Return a comprehensive pipeline state dict at the given event."""
    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()

    result: Dict[str, Any] = {
        "eventId": event_id,
        "pipeline_type": str(controller.GetAPIProperties().pipelineType),
    }

    # Shader stages
    stages = [
        ("Vertex", rd.ShaderStage.Vertex),
        ("TessControl", rd.ShaderStage.Tess_Control),
        ("TessEval", rd.ShaderStage.Tess_Eval),
        ("Geometry", rd.ShaderStage.Geometry),
        ("Fragment", rd.ShaderStage.Fragment),
        ("Compute", rd.ShaderStage.Compute),
    ]
    shaders = {}
    for name, stage in stages:
        refl = pipe.GetShaderReflection(stage)
        if refl is not None:
            shaders[name] = {
                "bound": True,
                "resourceId": str(refl.resourceId),
                "entryPoint": str(refl.entryPoint),
                "debugInfo": str(refl.debugInfo.debuggable) if refl.debugInfo else "N/A",
                "numInputs": len(refl.inputSignature),
                "numOutputs": len(refl.outputSignature),
                "numCBuffers": len(refl.constantBlocks),
                "numReadOnly": len(refl.readOnlyResources),
                "numReadWrite": len(refl.readWriteResources),
            }
        else:
            shaders[name] = {"bound": False}
    result["shaders"] = shaders

    # Vertex inputs
    try:
        vinputs = pipe.GetVertexInputs()
        result["vertexInputs"] = [
            {
                "name": str(v.name),
                "vertexBuffer": v.vertexBuffer,
                "byteOffset": v.byteOffset,
                "perInstance": v.perInstance,
                "instanceRate": v.instanceRate,
                "format": str(v.format),
            }
            for v in vinputs
        ]
    except Exception:
        result["vertexInputs"] = []

    # Render targets
    try:
        targets = pipe.GetOutputTargets()
        result["renderTargets"] = [
            {"resourceId": str(t.resourceId), "index": i}
            for i, t in enumerate(targets)
            if t.resourceId != rd.ResourceId.Null()
        ]
    except Exception:
        result["renderTargets"] = []

    # Depth target
    try:
        depth = pipe.GetDepthTarget()
        if depth.resourceId != rd.ResourceId.Null():
            result["depthTarget"] = {"resourceId": str(depth.resourceId)}
        else:
            result["depthTarget"] = None
    except Exception:
        result["depthTarget"] = None

    # Viewports
    try:
        vp = pipe.GetViewport(0)
        result["viewport"] = {
            "x": vp.x,
            "y": vp.y,
            "width": vp.width,
            "height": vp.height,
            "minDepth": vp.minDepth,
            "maxDepth": vp.maxDepth,
        }
    except Exception:
        result["viewport"] = None

    # Rasterizer state
    result["rasterizer"] = get_rasterizer_state(pipe)

    # Blend state
    result["blend"] = get_blend_state(pipe)

    # Depth-stencil state
    result["depthStencil"] = get_depth_stencil_state(pipe)

    return result


# ---------------------------------------------------------------------------
# Stage map helper (shared)
# ---------------------------------------------------------------------------

STAGE_MAP = {
    "vertex": rd.ShaderStage.Vertex if HAS_RD else None,
    "tesscontrol": rd.ShaderStage.Tess_Control if HAS_RD else None,
    "tesseval": rd.ShaderStage.Tess_Eval if HAS_RD else None,
    "geometry": rd.ShaderStage.Geometry if HAS_RD else None,
    "fragment": rd.ShaderStage.Fragment if HAS_RD else None,
    "pixel": rd.ShaderStage.Fragment if HAS_RD else None,
    "compute": rd.ShaderStage.Compute if HAS_RD else None,
}

STAGE_PAIRS = [
    ("Vertex", "vertex"),
    ("TessControl", "tesscontrol"),
    ("TessEval", "tesseval"),
    ("Geometry", "geometry"),
    ("Fragment", "fragment"),
    ("Compute", "compute"),
]


def _resolve_stage(stage_name: str):
    """Resolve a stage name string to rd.ShaderStage enum, or None."""
    return STAGE_MAP.get(stage_name.lower())


# ---------------------------------------------------------------------------
# Rasterizer / Blend / Depth-Stencil state extraction
# ---------------------------------------------------------------------------

def get_rasterizer_state(pipe) -> Optional[Dict[str, Any]]:
    """Extract rasterizer state from a PipeState object."""
    try:
        d3d11 = getattr(pipe, "GetD3D11PipelineState", None)
        d3d12 = getattr(pipe, "GetD3D12PipelineState", None)
        gl = getattr(pipe, "GetGLPipelineState", None)
        vk = getattr(pipe, "GetVulkanPipelineState", None)

        if d3d11:
            ps = d3d11()
            rs = ps.rasterizer.state
            return {
                "fillMode": str(rs.fillMode),
                "cullMode": str(rs.cullMode),
                "frontCCW": rs.frontCCW,
                "depthBias": rs.depthBias,
                "depthBiasClamp": rs.depthBiasClamp,
                "slopeScaledDepthBias": rs.slopeScaledDepthBias,
                "depthClip": rs.depthClip,
                "scissorEnable": rs.scissorEnable,
                "multisampleEnable": rs.multisampleEnable,
                "antialiasedLines": rs.antialiasedLines,
            }
        if d3d12:
            ps = d3d12()
            rs = ps.rasterizer.state
            return {
                "fillMode": str(rs.fillMode),
                "cullMode": str(rs.cullMode),
                "frontCCW": rs.frontCCW,
                "depthBias": rs.depthBias,
                "depthBiasClamp": rs.depthBiasClamp,
                "slopeScaledDepthBias": rs.slopeScaledDepthBias,
                "depthClip": rs.depthClip,
                "conservativeRasterization": str(rs.conservativeRasterization),
            }
        if gl:
            ps = gl()
            rs = ps.rasterizer.state
            return {
                "fillMode": str(rs.fillMode),
                "cullMode": str(rs.cullMode),
                "frontCCW": rs.frontCCW,
                "depthBias": rs.depthBias,
                "slopeScaledDepthBias": rs.slopeScaledDepthBias,
                "offsetClamp": rs.offsetClamp,
                "depthClamp": rs.depthClamp,
            }
        if vk:
            ps = vk()
            rs = ps.rasterizer
            return {
                "fillMode": str(rs.fillMode),
                "cullMode": str(rs.cullMode),
                "frontCCW": rs.frontCCW,
                "depthBiasEnable": rs.depthBiasEnable,
                "depthBias": rs.depthBias,
                "depthBiasClamp": rs.depthBiasClamp,
                "slopeScaledDepthBias": rs.slopeScaledDepthBias,
                "depthClampEnable": rs.depthClampEnable,
                "lineWidth": rs.lineWidth,
            }
    except Exception:
        pass
    return None


def get_blend_state(pipe) -> Optional[Dict[str, Any]]:
    """Extract blend state from a PipeState object."""
    try:
        d3d11 = getattr(pipe, "GetD3D11PipelineState", None)
        d3d12 = getattr(pipe, "GetD3D12PipelineState", None)
        gl = getattr(pipe, "GetGLPipelineState", None)
        vk = getattr(pipe, "GetVulkanPipelineState", None)

        def _blend_eq(b):
            return {
                "enabled": b.enabled,
                "colorBlendSrc": str(b.colorBlend.source),
                "colorBlendDst": str(b.colorBlend.destination),
                "colorBlendOp": str(b.colorBlend.operation),
                "alphaBlendSrc": str(b.alphaBlend.source),
                "alphaBlendDst": str(b.alphaBlend.destination),
                "alphaBlendOp": str(b.alphaBlend.operation),
                "writeMask": int(b.writeMask),
            }

        if d3d11:
            ps = d3d11()
            om = ps.outputMerger
            return {
                "alphaToCoverage": om.blendState.alphaToCoverage,
                "independentBlend": om.blendState.independentBlend,
                "blends": [dict(_blend_eq(b), index=i) for i, b in enumerate(om.blendState.blends)],
            }
        if d3d12:
            ps = d3d12()
            om = ps.outputMerger
            return {
                "alphaToCoverage": om.blendState.alphaToCoverage,
                "independentBlend": om.blendState.independentBlend,
                "blends": [dict(_blend_eq(b), index=i) for i, b in enumerate(om.blendState.blends)],
            }
        if gl:
            ps = gl()
            fb = ps.framebuffer
            return {
                "blends": [dict(_blend_eq(b), index=i) for i, b in enumerate(fb.blendState.blends)],
            }
        if vk:
            ps = vk()
            cb = ps.colorBlend
            return {
                "alphaToCoverage": cb.alphaToCoverageEnable,
                "blends": [dict(_blend_eq(b), index=i) for i, b in enumerate(cb.blends)],
            }
    except Exception:
        pass
    return None


def get_depth_stencil_state(pipe) -> Optional[Dict[str, Any]]:
    """Extract depth-stencil state from a PipeState object."""
    try:
        d3d11 = getattr(pipe, "GetD3D11PipelineState", None)
        d3d12 = getattr(pipe, "GetD3D12PipelineState", None)
        gl = getattr(pipe, "GetGLPipelineState", None)
        vk = getattr(pipe, "GetVulkanPipelineState", None)

        def _stencil_face(s):
            return {
                "failOp": str(s.failOperation),
                "depthFailOp": str(s.depthFailOperation),
                "passOp": str(s.passOperation),
                "function": str(s.function),
            }

        if d3d11:
            ps = d3d11()
            ds = ps.outputMerger.depthStencilState
            return {
                "depthEnable": ds.depthEnable,
                "depthFunction": str(ds.depthFunction),
                "depthWrites": ds.depthWrites,
                "stencilEnable": ds.stencilEnable,
                "frontFace": _stencil_face(ds.frontFace),
                "backFace": _stencil_face(ds.backFace),
            }
        if d3d12:
            ps = d3d12()
            ds = ps.outputMerger.depthStencilState
            return {
                "depthEnable": ds.depthEnable,
                "depthFunction": str(ds.depthFunction),
                "depthWrites": ds.depthWrites,
                "stencilEnable": ds.stencilEnable,
                "frontFace": _stencil_face(ds.frontFace),
                "backFace": _stencil_face(ds.backFace),
            }
        if gl:
            ps = gl()
            ds = ps.depthState
            st = ps.stencilState
            return {
                "depthEnable": ds.depthEnable,
                "depthFunction": str(ds.depthFunction),
                "depthWrites": ds.depthWrites,
                "stencilEnable": st.stencilEnable,
                "frontFace": _stencil_face(st.frontFace),
                "backFace": _stencil_face(st.backFace),
            }
        if vk:
            ps = vk()
            ds = ps.depthStencil
            return {
                "depthTestEnable": ds.depthTestEnable,
                "depthWriteEnable": ds.depthWriteEnable,
                "depthFunction": str(ds.depthFunction),
                "depthBoundsEnable": ds.depthBoundsEnable,
                "stencilTestEnable": ds.stencilTestEnable,
                "frontFace": _stencil_face(ds.frontFace),
                "backFace": _stencil_face(ds.backFace),
            }
    except Exception:
        pass
    return None


def get_shader_disasm(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
    disasm_target_index: int = 0,
) -> Dict[str, Any]:
    """Get only the disassembly text from RenderDoc.

    Returns a lightweight dict with encoding info and the disassembly string,
    without gathering signatures, cbuffer values, or debug source files.
    """
    stage = _resolve_stage(stage_name)
    if stage is None:
        return {"error": "Unknown stage: %s" % stage_name}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": "No shader bound at stage %s for event %d" % (stage_name, event_id)}

    pso = pipe.GetGraphicsPipelineObject()
    enc_str = _get_encoding_str(refl)
    enc_info = _get_encoding_info(enc_str)
    raw = bytes(refl.rawBytes) if refl.rawBytes else b""

    result = {
        "eventId": event_id,
        "stage": stage_name,
        "resourceId": str(refl.resourceId),
        "entryPoint": str(refl.entryPoint),
        "encoding": enc_info["format"],
        "encoding_description": enc_info["description"],
        "is_text": enc_info["is_text"],
        "disasm_ext": enc_info["disasm_ext"],
        "rawBytes_size": len(raw),
    }

    # Disassembly
    targets = controller.GetDisassemblyTargets(True)
    result["disasmTargets"] = [str(t) for t in targets]
    if targets:
        tidx = min(disasm_target_index, len(targets) - 1)
        disasm = controller.DisassembleShader(pso, refl, targets[tidx])
        result["disasmTarget"] = str(targets[tidx])
        result["disassembly"] = disasm
    else:
        result["disassembly"] = None

    # Fallback: for text encodings, if disasm failed use raw source
    disasm = result.get("disassembly", "")
    if disasm and ("failed" in disasm.lower()[:100] or "error" in disasm.lower()[:200]):
        if enc_info["is_text"] and raw:
            result["disassembly"] = raw.decode("utf-8", errors="replace")
            result["disasmTarget"] = enc_info["format"] + " (raw source fallback)"

    return result


# ---------------------------------------------------------------------------
# Shader export (human-readable)
# ---------------------------------------------------------------------------

def export_shader(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Export a shader in human-readable form, plus the raw binary.

    Saves two files into *output_dir*:

    1. **Raw shader** — the original bytes (e.g. ``.dxbc``, ``.glsl``)
    2. **Readable shader** (only if raw is binary) — tried in order:
       a. Embedded debug source (HLSL/GLSL compiled with ``/Zi``)
       b. RenderDoc disassembly (bytecode asm)

    For text encodings (GLSL, HLSL, Slang) the raw file *is* the readable
    file, so only one file is produced.

    Returns a summary dict with ``saved_files``, ``readable_path``,
    ``readable_kind`` (``"source"`` | ``"disasm"`` | ``None``).
    """
    stage = _resolve_stage(stage_name)
    if stage is None:
        return {"error": "Unknown stage: %s" % stage_name}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": "No shader bound at stage %s for event %d" % (stage_name, event_id)}

    enc_str = _get_encoding_str(refl)
    enc_info = _get_encoding_info(enc_str)
    raw = bytes(refl.rawBytes) if refl.rawBytes else b""
    if not raw:
        return {"error": "Shader has no rawBytes data"}

    rid_str = str(refl.resourceId).replace("::", "_")
    if output_dir is None:
        output_dir = os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    # --- Save raw ---
    raw_ext = enc_info.get("file_ext", ".bin")
    raw_name = "shader_%s_%s_eid%d%s" % (rid_str, stage_name, event_id, raw_ext)
    raw_path = os.path.join(output_dir, raw_name)
    mode = "w" if enc_info["is_text"] else "wb"
    with open(raw_path, mode,
              encoding="utf-8" if enc_info["is_text"] else None) as f:
        if enc_info["is_text"]:
            f.write(raw.decode("utf-8", errors="replace"))
        else:
            f.write(raw)
    raw_path = os.path.abspath(raw_path)

    saved_files = [raw_path]
    readable_path = None
    readable_kind = None

    if enc_info["is_text"]:
        # Raw is already human-readable
        readable_path = raw_path
        readable_kind = "source"
    else:
        # Binary — try embedded debug source first
        source_text, source_ext = _extract_debug_source(refl, enc_str)

        if source_text:
            src_name = "shader_%s_%s_eid%d%s" % (
                rid_str, stage_name, event_id, source_ext)
            readable_path = os.path.abspath(os.path.join(output_dir, src_name))
            with open(readable_path, "w", encoding="utf-8") as f:
                f.write(source_text)
            readable_kind = "source"
            saved_files.append(readable_path)
        else:
            # Fallback: disassembly
            disasm_data = get_shader_disasm(controller, event_id, stage_name, 0)
            disasm_text = disasm_data.get("disassembly") or ""
            if disasm_text:
                disasm_ext = enc_info.get("disasm_ext", ".asm")
                asm_name = "shader_%s_%s_eid%d%s" % (
                    rid_str, stage_name, event_id, disasm_ext)
                readable_path = os.path.abspath(os.path.join(output_dir, asm_name))
                with open(readable_path, "w", encoding="utf-8") as f:
                    f.write(disasm_text)
                readable_kind = "disasm"
                saved_files.append(readable_path)

    return {
        "eventId": event_id,
        "stage": stage_name,
        "resourceId": str(refl.resourceId),
        "entryPoint": str(refl.entryPoint),
        "encoding": enc_info["format"],
        "encoding_description": enc_info["description"],
        "is_text": enc_info["is_text"],
        "size_bytes": len(raw),
        "raw_path": raw_path,
        "saved_files": saved_files,
        "readable_path": readable_path,
        "readable_kind": readable_kind,
    }


def _extract_debug_source(refl, enc_str: str):
    """Try to extract embedded debug source from ShaderReflection.

    Returns ``(source_text, extension)`` or ``(None, None)``.
    """
    if not refl.debugInfo or not refl.debugInfo.files:
        return None, None

    for f in refl.debugInfo.files:
        contents = str(f.contents)
        if not contents:
            continue

        # Determine file extension from debug encoding
        ext = None
        if hasattr(refl.debugInfo, "encoding"):
            dbg_enc = str(refl.debugInfo.encoding)
            if "HLSL" in dbg_enc:
                ext = ".hlsl"
            elif "GLSL" in dbg_enc:
                ext = ".glsl"

        if ext is None:
            # Guess from filename
            fname = str(f.filename)
            if fname.endswith(".hlsl"):
                ext = ".hlsl"
            elif fname.endswith(".glsl"):
                ext = ".glsl"

        if ext is None:
            # Guess from shader encoding: SPIR-V → GLSL, DXBC/DXIL → HLSL
            if enc_str in ("SPIRV", "OpenGLSPIRV"):
                ext = ".glsl"
            else:
                ext = ".hlsl"

        return contents, ext

    return None, None


# ---------------------------------------------------------------------------
# Constant buffer contents
# ---------------------------------------------------------------------------

def get_cbuffer_contents(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
    cbuffer_index: int = 0,
) -> Dict[str, Any]:
    """Get constant buffer variable contents at a specific event."""
    stage = _resolve_stage(stage_name)
    if stage is None:
        return {"error": f"Unknown stage: {stage_name}"}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": f"No shader bound at stage {stage_name}"}

    if cbuffer_index >= len(refl.constantBlocks):
        return {"error": f"CBuffer index {cbuffer_index} out of range (max {len(refl.constantBlocks) - 1})"}

    pso = pipe.GetGraphicsPipelineObject()
    entry = pipe.GetShaderEntryPoint(stage)
    cb = pipe.GetConstantBlock(stage, cbuffer_index, 0)

    variables = controller.GetCBufferVariableContents(
        pso, refl.resourceId, stage, entry,
        cbuffer_index, cb.descriptor.resource, 0, 0
    )

    return {
        "eventId": event_id,
        "stage": stage_name,
        "cbuffer_index": cbuffer_index,
        "variables": [_runtime_var_to_dict(v) for v in variables],
    }


# ---------------------------------------------------------------------------
# Shader encoding info map
# ---------------------------------------------------------------------------

_ENCODING_INFO = {
    "DXBC": {
        "format": "DXBC",
        "description": "Direct3D 11 bytecode container (binary)",
        "is_text": False,
        "file_ext": ".dxbc",
        "disasm_ext": ".dxbc.asm",
    },
    "DXIL": {
        "format": "DXIL",
        "description": "Direct3D 12 DXIL bytecode (binary)",
        "is_text": False,
        "file_ext": ".dxil",
        "disasm_ext": ".dxil.asm",
    },
    "GLSL": {
        "format": "GLSL",
        "description": "OpenGL/ES GLSL source code (text, already human-readable)",
        "is_text": True,
        "file_ext": ".glsl",
        "disasm_ext": ".glsl",
    },
    "SPIRV": {
        "format": "SPIR-V",
        "description": "Vulkan SPIR-V binary module (binary)",
        "is_text": False,
        "file_ext": ".spv",
        "disasm_ext": ".spv.asm",
    },
    "OpenGLSPIRV": {
        "format": "OpenGL SPIR-V",
        "description": "OpenGL variant of SPIR-V binary (binary)",
        "is_text": False,
        "file_ext": ".spv",
        "disasm_ext": ".spv.asm",
    },
    "HLSL": {
        "format": "HLSL",
        "description": "High Level Shading Language source (text, already human-readable)",
        "is_text": True,
        "file_ext": ".hlsl",
        "disasm_ext": ".hlsl",
    },
    "Slang": {
        "format": "Slang",
        "description": "Slang shader source (text, already human-readable)",
        "is_text": True,
        "file_ext": ".slang",
        "disasm_ext": ".slang",
    },
}


def _get_encoding_str(refl) -> str:
    """Extract encoding name string from ShaderReflection."""
    enc = str(refl.encoding)
    if "." in enc:
        enc = enc.split(".")[-1]
    return enc


def _get_encoding_info(enc_str: str) -> Dict[str, Any]:
    return _ENCODING_INFO.get(enc_str, {
        "format": enc_str,
        "description": "Unknown shader encoding",
        "is_text": False,
        "file_ext": ".bin",
        "disasm_ext": ".asm",
    })


# ---------------------------------------------------------------------------
# Internal: get raw shader info (used by disasm fallback)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Pipeline dump (full PipelineState + ShaderReflection export)
# ---------------------------------------------------------------------------

def _serialize_sig(sig) -> Dict[str, Any]:
    """Serialize a SigParameter to dict."""
    return {
        "varName": str(sig.varName),
        "semanticName": str(sig.semanticName),
        "semanticIndex": sig.semanticIndex,
        "regIndex": sig.regIndex,
        "systemValue": str(sig.systemValue),
        "varType": str(sig.varType),
        "compCount": sig.compCount,
    }


def _serialize_shader_type(t) -> Dict[str, Any]:
    """Serialize a ShaderVariableType to dict."""
    result = {}
    for attr in ("name", "rows", "columns", "elements", "arrayByteStride",
                 "matrixByteStride", "pointerTypeID", "baseType"):
        if hasattr(t, attr):
            val = getattr(t, attr)
            result[attr] = str(val) if not isinstance(val, (int, float, bool)) else val
    if hasattr(t, "members") and t.members:
        result["members"] = [_serialize_cbuffer_var(m) for m in t.members]
    return result


def _serialize_cbuffer_var(v) -> Dict[str, Any]:
    """Serialize a ShaderConstant (cbuffer variable) to dict."""
    d = {
        "name": str(v.name),
        "byteOffset": v.byteOffset,
    }
    if hasattr(v, "type"):
        d["type"] = _serialize_shader_type(v.type)
    if hasattr(v, "defaultValue"):
        d["defaultValue"] = v.defaultValue
    return d


def dump_shader_reflection(refl, include_file_contents: bool = False) -> Dict[str, Any]:
    """Serialize a ShaderReflection object to a JSON-friendly dict.

    Maps all fields from the RenderDoc Python API ShaderReflection class.

    Parameters
    ----------
    include_file_contents : bool
        If False (default), debugInfo.files[].contents is replaced with
        ``contents_length`` to avoid multi-MB JSON blobs.
        If True, the full source text is included (for disk export).
    """
    if refl is None:
        return None

    enc_str = _get_encoding_str(refl)
    raw = bytes(refl.rawBytes) if refl.rawBytes else b""

    result = {
        "resourceId": str(refl.resourceId),
        "entryPoint": str(refl.entryPoint),
        "encoding": enc_str,
        "stage": str(refl.stage) if hasattr(refl, "stage") else None,
        "rawBytes_size": len(raw),
    }

    # outputTopology / dispatchThreadsDimension
    if hasattr(refl, "outputTopology"):
        result["outputTopology"] = str(refl.outputTopology)
    if hasattr(refl, "dispatchThreadsDimension"):
        dim = refl.dispatchThreadsDimension
        result["dispatchThreadsDimension"] = [dim[0], dim[1], dim[2]]

    # constantBlocks
    cblocks = []
    for cb in refl.constantBlocks:
        entry = {
            "name": str(cb.name),
            "byteSize": cb.byteSize,
        }
        if hasattr(cb, "bindPoint"):
            entry["bindPoint"] = cb.bindPoint
        if hasattr(cb, "fixedBindNumber"):
            entry["fixedBindNumber"] = cb.fixedBindNumber
            entry["fixedBindSetOrSpace"] = cb.fixedBindSetOrSpace
        if cb.variables:
            entry["variables"] = [_serialize_cbuffer_var(v) for v in cb.variables]
        cblocks.append(entry)
    result["constantBlocks"] = cblocks

    # readOnlyResources
    def _serialize_resource(r):
        d = {"name": str(r.name)}
        if hasattr(r, "resType"):
            d["resType"] = str(r.resType)
        if hasattr(r, "textureType"):
            d["textureType"] = str(r.textureType)
        if hasattr(r, "fixedBindSetOrSpace"):
            d["fixedBindSetOrSpace"] = r.fixedBindSetOrSpace
            d["fixedBindNumber"] = r.fixedBindNumber
        if hasattr(r, "isTexture"):
            d["isTexture"] = r.isTexture
        if hasattr(r, "isReadOnly"):
            d["isReadOnly"] = r.isReadOnly
        return d

    result["readOnlyResources"] = [_serialize_resource(r) for r in refl.readOnlyResources]
    result["readWriteResources"] = [_serialize_resource(r) for r in refl.readWriteResources]

    # samplers
    samps = []
    for s in refl.samplers:
        d = {"name": str(s.name)}
        if hasattr(s, "fixedBindSetOrSpace"):
            d["fixedBindSetOrSpace"] = s.fixedBindSetOrSpace
            d["fixedBindNumber"] = s.fixedBindNumber
        samps.append(d)
    result["samplers"] = samps

    # signatures
    result["inputSignature"] = [_serialize_sig(s) for s in refl.inputSignature]
    result["outputSignature"] = [_serialize_sig(s) for s in refl.outputSignature]

    # interfaces
    if hasattr(refl, "interfaces"):
        result["interfaces"] = [str(i) for i in refl.interfaces]

    # debugInfo
    if refl.debugInfo:
        dbg = refl.debugInfo
        debug = {
            "debuggable": dbg.debuggable,
        }
        if hasattr(dbg, "compiler"):
            debug["compiler"] = str(dbg.compiler)
        if hasattr(dbg, "encoding"):
            debug["encoding"] = str(dbg.encoding)
        if hasattr(dbg, "debugStatus"):
            debug["debugStatus"] = str(dbg.debugStatus)
        if hasattr(dbg, "entrySourceName"):
            debug["entrySourceName"] = str(dbg.entrySourceName)
        try:
            flags = dbg.compileFlags
            if flags and hasattr(flags, "flags"):
                debug["compileFlags"] = [
                    {"name": str(f.name), "value": str(f.value)}
                    for f in flags.flags
                ]
        except Exception:
            debug["compileFlags"] = None
        try:
            if dbg.files:
                if include_file_contents:
                    debug["files"] = [
                        {
                            "filename": str(f.filename),
                            "contents": str(f.contents),
                        }
                        for f in dbg.files
                    ]
                else:
                    debug["files"] = [
                        {
                            "filename": str(f.filename),
                            "contents_length": len(str(f.contents)),
                        }
                        for f in dbg.files
                    ]
        except Exception:
            debug["files"] = []
        result["debugInfo"] = debug
    else:
        result["debugInfo"] = None

    return result


def export_shader_reflection(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Export complete ShaderReflection for a shader stage to a folder.

    Creates:
      <output_dir>/
        reflection.json        — full ShaderReflection (with debugInfo file contents)
        bindings.json          — runtime GPU bindings (bound resources, cbuffers, samplers)
        cbuffer_values.json    — runtime constant buffer variable values
        sources/               — individual debug source files (if available)
          <filename>

    Returns a summary dict with paths and metadata.
    """
    stage = _resolve_stage(stage_name)
    if stage is None:
        return {"error": "Unknown stage: %s" % stage_name}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": "No shader bound at stage %s for event %d" % (stage_name, event_id)}

    pso = pipe.GetGraphicsPipelineObject()
    entry = pipe.GetShaderEntryPoint(stage)

    # Build output directory
    if output_dir is None:
        rid_str = str(refl.resourceId).replace("::", "_")
        output_dir = "shader_%s_%s_eid%d_reflection" % (rid_str, stage_name, event_id)
    os.makedirs(output_dir, exist_ok=True)

    files_written = []

    # 1. reflection.json — full ShaderReflection including source contents
    refl_data = dump_shader_reflection(refl, include_file_contents=True)
    refl_path = os.path.join(output_dir, "reflection.json")
    _write_json(refl_path, refl_data)
    files_written.append("reflection.json")

    # 2. bindings.json — runtime GPU bindings
    bindings_data = dump_stage_bindings(controller, pipe, pso, stage, refl)
    bindings_path = os.path.join(output_dir, "bindings.json")
    _write_json(bindings_path, bindings_data)
    files_written.append("bindings.json")

    # 3. cbuffer_values.json — runtime constant buffer variable values
    cbuffer_values = []
    for idx in range(len(refl.constantBlocks)):
        cb_block = refl.constantBlocks[idx]
        entry_dict: Dict[str, Any] = {
            "index": idx,
            "name": str(cb_block.name),
        }
        try:
            cb = pipe.GetConstantBlock(stage, idx, 0)
            variables = controller.GetCBufferVariableContents(
                pso, refl.resourceId, stage, entry,
                idx, cb.descriptor.resource, 0, 0,
            )
            entry_dict["variables"] = [_runtime_var_to_dict(v) for v in variables]
        except Exception as e:
            entry_dict["variables"] = []
            entry_dict["error"] = str(e)
        cbuffer_values.append(entry_dict)
    cbuf_path = os.path.join(output_dir, "cbuffer_values.json")
    _write_json(cbuf_path, cbuffer_values)
    files_written.append("cbuffer_values.json")

    # 4. sources/ — individual debug source files
    source_files = []
    if refl.debugInfo and refl.debugInfo.files:
        sources_dir = os.path.join(output_dir, "sources")
        os.makedirs(sources_dir, exist_ok=True)
        for f in refl.debugInfo.files:
            fname = str(f.filename)
            contents = str(f.contents)
            if not contents:
                continue
            safe_name = fname.replace("\\", "/").replace("/", "_").replace(":", "_")
            if not safe_name:
                safe_name = "unnamed_source"
            src_path = os.path.join(sources_dir, safe_name)
            with open(src_path, "w", encoding="utf-8") as fh:
                fh.write(contents)
            source_files.append({
                "original_path": fname,
                "saved_as": safe_name,
                "size": len(contents),
            })
            files_written.append("sources/%s" % safe_name)

    # 5. raw shader bytes
    raw = bytes(refl.rawBytes) if refl.rawBytes else b""
    if raw:
        enc_str = _get_encoding_str(refl)
        enc_info = _get_encoding_info(enc_str)
        raw_ext = enc_info.get("file_ext", ".bin")
        raw_name = "shader_raw%s" % raw_ext
        raw_path = os.path.join(output_dir, raw_name)
        mode = "w" if enc_info["is_text"] else "wb"
        with open(raw_path, mode,
                  encoding="utf-8" if enc_info["is_text"] else None) as fh:
            if enc_info["is_text"]:
                fh.write(raw.decode("utf-8", errors="replace"))
            else:
                fh.write(raw)
        files_written.append(raw_name)

    return {
        "eventId": event_id,
        "stage": stage_name,
        "resourceId": str(refl.resourceId),
        "entryPoint": str(refl.entryPoint),
        "encoding": _get_encoding_str(refl),
        "output_dir": os.path.abspath(output_dir),
        "files": files_written,
        "source_files": source_files,
        "constantBlocks_count": len(refl.constantBlocks),
        "readOnlyResources_count": len(refl.readOnlyResources),
        "readWriteResources_count": len(refl.readWriteResources),
        "samplers_count": len(refl.samplers),
    }


def _serialize_used_descriptor(idx, used) -> Dict[str, Any]:
    """Serialize a UsedDescriptor to dict."""
    desc = used.descriptor
    entry_d = {"index": idx, "resource": str(desc.resource)}
    if hasattr(desc, "type"):
        entry_d["type"] = str(desc.type)
    if hasattr(desc, "textureType"):
        entry_d["textureType"] = str(desc.textureType)
    if hasattr(desc, "byteOffset"):
        entry_d["byteOffset"] = desc.byteOffset
    if hasattr(desc, "byteSize") and desc.byteSize:
        entry_d["byteSize"] = desc.byteSize
    return entry_d


def dump_stage_bindings(controller, pipe, pso, stage, refl) -> Dict[str, Any]:
    """Serialize GPU runtime bindings for a shader stage.

    Returns the actual resources bound at capture time:
    constant buffers, textures, UAVs, samplers.

    Note: GetConstantBlock(stage, idx, 0) is per-index.
    GetReadOnlyResources(stage), GetReadWriteResources(stage),
    GetSamplers(stage) return full lists.
    """
    bindings = {}

    # Constant block bindings (per-index API)
    cb_bindings = []
    for idx in range(len(refl.constantBlocks)):
        try:
            cb = pipe.GetConstantBlock(stage, idx, 0)
            desc = cb.descriptor
            cb_bindings.append({
                "index": idx,
                "resource": str(desc.resource),
                "byteOffset": desc.byteOffset,
                "byteSize": desc.byteSize,
            })
        except Exception:
            cb_bindings.append({
                "index": idx,
                "error": "failed to read",
            })
    bindings["constantBlocks"] = cb_bindings

    # Read-only resource bindings (list API)
    try:
        ro_list = pipe.GetReadOnlyResources(stage)
        bindings["readOnlyResources"] = [
            _serialize_used_descriptor(i, used) for i, used in enumerate(ro_list)
        ]
    except Exception:
        bindings["readOnlyResources"] = []

    # Read-write resource bindings (list API)
    try:
        rw_list = pipe.GetReadWriteResources(stage)
        bindings["readWriteResources"] = [
            _serialize_used_descriptor(i, used) for i, used in enumerate(rw_list)
        ]
    except Exception:
        bindings["readWriteResources"] = []

    # Sampler bindings (list API)
    try:
        sam_list = pipe.GetSamplers(stage)
        bindings["samplers"] = [
            _serialize_used_descriptor(i, used) for i, used in enumerate(sam_list)
        ]
    except Exception:
        bindings["samplers"] = []

    return bindings


def _runtime_var_to_dict(v) -> Dict[str, Any]:
    """Serialize a runtime CBuffer variable (ShaderVariable) to dict.

    This is the module-level equivalent of the nested ``_var_to_dict``
    formerly duplicated as nested ``_var_to_dict`` in several functions.
    """
    d: Dict[str, Any] = {"name": v.name, "rows": v.rows, "columns": v.columns}
    if len(v.members) == 0:
        vals = []
        for r in range(v.rows):
            for c in range(v.columns):
                vals.append(v.value.f32v[r * v.columns + c])
        d["values"] = vals
    else:
        d["members"] = [_runtime_var_to_dict(m) for m in v.members]
    return d


def dump_pipeline_for_diff(controller, event_id: int) -> Dict[str, Any]:
    """Build a complete pipeline snapshot suitable for ``diff_pipeline``.

    Calls :func:`dump_pipeline` for the base structure, then enriches every
    bound stage's ``bindings.constantBlocks[i]`` with a ``variables`` list
    containing runtime CBuffer values (via ``GetCBufferVariableContents``).
    """
    data = dump_pipeline(controller, event_id)
    ps = data.get("PipelineState", {})

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    pso = pipe.GetGraphicsPipelineObject()

    stage_defs = [
        ("Vertex", rd.ShaderStage.Vertex),
        ("TessControl", rd.ShaderStage.Tess_Control),
        ("TessEval", rd.ShaderStage.Tess_Eval),
        ("Geometry", rd.ShaderStage.Geometry),
        ("Fragment", rd.ShaderStage.Fragment),
        ("Compute", rd.ShaderStage.Compute),
    ]

    for name, stage_enum in stage_defs:
        stage_data = ps.get("stages", {}).get(name)
        if stage_data is None:
            continue
        refl = pipe.GetShaderReflection(stage_enum)
        if refl is None:
            continue
        entry = pipe.GetShaderEntryPoint(stage_enum)
        cb_bindings = stage_data.get("bindings", {}).get("constantBlocks", [])
        for cb_entry in cb_bindings:
            idx = cb_entry.get("index")
            if idx is None or "error" in cb_entry:
                continue
            try:
                cb = pipe.GetConstantBlock(stage_enum, idx, 0)
                variables = controller.GetCBufferVariableContents(
                    pso, refl.resourceId, stage_enum, entry,
                    idx, cb.descriptor.resource, 0, 0,
                )
                cb_entry["variables"] = [_runtime_var_to_dict(v) for v in variables]
            except Exception:
                cb_entry["variables"] = []

    return data


def dump_pipeline(controller, event_id: int) -> Dict[str, Any]:
    """Dump the complete pipeline state and shader reflections at an event.

    Produces a JSON-serializable dict with:
    - PipelineState: vertex inputs, render targets, viewport, rasterizer,
      blend, depth/stencil
    - For each bound shader stage: ShaderReflection + runtime bindings

    This is intended for human debugging, not for AI consumption.
    """
    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    pso = pipe.GetGraphicsPipelineObject()

    pipeline_type = str(controller.GetAPIProperties().pipelineType)

    ps = {
        "pipelineType": pipeline_type,
    }

    # Vertex inputs
    try:
        vinputs = pipe.GetVertexInputs()
        ps["vertexInputs"] = [
            {
                "name": str(v.name),
                "vertexBuffer": v.vertexBuffer,
                "byteOffset": v.byteOffset,
                "perInstance": v.perInstance,
                "instanceRate": v.instanceRate,
                "format": v.format.Name() if hasattr(v.format, "Name") else str(v.format),
            }
            for v in vinputs
        ]
    except Exception:
        ps["vertexInputs"] = []

    # Output targets
    try:
        targets = pipe.GetOutputTargets()
        ps["outputTargets"] = [
            {"resourceId": str(t.resourceId), "index": i}
            for i, t in enumerate(targets)
            if t.resourceId != rd.ResourceId.Null()
        ]
    except Exception:
        ps["outputTargets"] = []

    # Depth target
    try:
        depth = pipe.GetDepthTarget()
        if depth.resourceId != rd.ResourceId.Null():
            ps["depthTarget"] = {"resourceId": str(depth.resourceId)}
        else:
            ps["depthTarget"] = None
    except Exception:
        ps["depthTarget"] = None

    # Viewport
    try:
        vp = pipe.GetViewport(0)
        ps["viewport"] = {
            "x": vp.x, "y": vp.y,
            "width": vp.width, "height": vp.height,
            "minDepth": vp.minDepth, "maxDepth": vp.maxDepth,
        }
    except Exception:
        ps["viewport"] = None

    # State blocks — use new unified PipeState API
    # Blend state
    try:
        color_blends = pipe.GetColorBlends()
        def _blend_eq(b):
            return {
                "enabled": b.enabled,
                "colorBlendSrc": str(b.colorBlend.source),
                "colorBlendDst": str(b.colorBlend.destination),
                "colorBlendOp": str(b.colorBlend.operation),
                "alphaBlendSrc": str(b.alphaBlend.source),
                "alphaBlendDst": str(b.alphaBlend.destination),
                "alphaBlendOp": str(b.alphaBlend.operation),
                "writeMask": int(b.writeMask),
                "logicOperationEnabled": b.logicOperationEnabled,
                "logicOperation": str(b.logicOperation),
            }
        ps["blend"] = {
            "independentBlend": pipe.IsIndependentBlendingEnabled(),
            "blends": [dict(_blend_eq(b), index=i) for i, b in enumerate(color_blends)],
        }
    except Exception:
        ps["blend"] = get_blend_state(pipe)

    # Depth-stencil state
    try:
        stencil_faces = pipe.GetStencilFaces()
        def _stencil_face(s):
            return {
                "failOp": str(s.failOperation),
                "depthFailOp": str(s.depthFailOperation),
                "passOp": str(s.passOperation),
                "function": str(s.function),
                "reference": s.reference,
                "compareMask": s.compareMask,
                "writeMask": s.writeMask,
            }
        ps["depthStencil"] = {
            "frontFace": _stencil_face(stencil_faces[0]),
            "backFace": _stencil_face(stencil_faces[1]),
        }
    except Exception:
        ps["depthStencil"] = get_depth_stencil_state(pipe)

    # Rasterizer state
    try:
        ps["rasterizer"] = {
            "topology": str(pipe.GetPrimitiveTopology()),
        }
        sc = pipe.GetScissor(0)
        ps["rasterizer"]["scissor"] = {
            "enabled": sc.enabled,
            "x": sc.x, "y": sc.y,
            "width": sc.width, "height": sc.height,
        }
    except Exception:
        ps["rasterizer"] = get_rasterizer_state(pipe)

    # Shader stages
    stages_dict = {}
    stage_defs = [
        ("Vertex", rd.ShaderStage.Vertex),
        ("TessControl", rd.ShaderStage.Tess_Control),
        ("TessEval", rd.ShaderStage.Tess_Eval),
        ("Geometry", rd.ShaderStage.Geometry),
        ("Fragment", rd.ShaderStage.Fragment),
        ("Compute", rd.ShaderStage.Compute),
    ]
    for name, stage_enum in stage_defs:
        refl = pipe.GetShaderReflection(stage_enum)
        if refl is None:
            continue
        stage_data = {
            "shader": str(refl.resourceId),
            "entryPoint": str(refl.entryPoint),
            "ShaderReflection": dump_shader_reflection(refl),
            "bindings": dump_stage_bindings(controller, pipe, pso, stage_enum, refl),
        }
        stages_dict[name] = stage_data
    ps["stages"] = stages_dict

    return {
        "eventId": event_id,
        "PipelineState": ps,
    }


def get_shader_raw(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
) -> Dict[str, Any]:
    """Get raw shader encoding info. For text shaders includes source."""
    stage = _resolve_stage(stage_name)
    if stage is None:
        return {"error": "Unknown stage: %s" % stage_name}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": "No shader bound at stage %s for event %d" % (stage_name, event_id)}

    enc_str = _get_encoding_str(refl)
    enc_info = _get_encoding_info(enc_str)
    raw = bytes(refl.rawBytes) if refl.rawBytes else b""

    result = {
        "encoding": enc_info["format"],
        "is_text": enc_info["is_text"],
        "size_bytes": len(raw),
    }
    if enc_info["is_text"] and raw:
        result["source"] = raw.decode("utf-8", errors="replace")

    return result


# ---------------------------------------------------------------------------
# Save raw shader to file (equivalent to RenderDoc UI "Save" button)
# ---------------------------------------------------------------------------

def save_shader_raw(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
    output_path: Optional[str] = None,
    default_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Save raw shader bytes to file, identical to RenderDoc UI Save.

    Parameters
    ----------
    default_dir : str or None
        Directory for auto-generated filename when output_path is None.
        If None, uses current working directory.
    """
    stage = _resolve_stage(stage_name)
    if stage is None:
        return {"error": "Unknown stage: %s" % stage_name}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": "No shader bound at stage %s for event %d" % (stage_name, event_id)}

    enc_str = _get_encoding_str(refl)
    enc_info = _get_encoding_info(enc_str)

    raw = bytes(refl.rawBytes) if refl.rawBytes else b""
    if not raw:
        return {"error": "Shader has no rawBytes data"}

    if output_path is None:
        rid_str = str(refl.resourceId).replace("::", "_")
        fname = "shader_%s_%s_eid%d%s" % (
            rid_str, stage_name, event_id, enc_info["file_ext"])
        if default_dir:
            output_path = os.path.join(default_dir, fname)
        else:
            output_path = fname

    mode = "w" if enc_info["is_text"] else "wb"
    with open(output_path, mode,
              encoding="utf-8" if enc_info["is_text"] else None) as f:
        if enc_info["is_text"]:
            f.write(raw.decode("utf-8", errors="replace"))
        else:
            f.write(raw)

    # Query available disassembly targets from RenderDoc runtime
    disasm_targets = []
    try:
        targets = controller.GetDisassemblyTargets(True)
        disasm_targets = [str(t) for t in targets]
    except Exception:
        pass

    return {
        "eventId": event_id,
        "stage": stage_name,
        "resourceId": str(refl.resourceId),
        "encoding": enc_info["format"],
        "encoding_description": enc_info["description"],
        "is_text": enc_info["is_text"],
        "size_bytes": len(raw),
        "output_path": os.path.abspath(output_path),
        "disasm_targets": disasm_targets,
    }
