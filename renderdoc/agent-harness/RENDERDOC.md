# RENDERDOC.md – Software-Specific SOP

## About RenderDoc

RenderDoc is a free, open-source GPU frame capture and analysis tool for
Vulkan, D3D11, D3D12, OpenGL, and OpenGL ES. It captures a single frame
of GPU commands and allows detailed inspection of every draw call, resource,
shader, and pipeline state.

## Key Concepts

### Capture File (.rdc)
A binary file containing all GPU state and commands for a single frame.
Contains embedded sections (textures, shaders, structured data, thumbnails).

### Actions
GPU operations recorded in the capture. Hierarchical tree structure:
- **PushMarker / PopMarker**: Debug groups (like `RenderPass: ForwardOpaque`)
- **Drawcall**: Actual draw calls with triangle/vertex counts
- **Clear**: Clear render target/depth
- **Dispatch**: Compute shader dispatch
- **Copy/Resolve**: Resource copy operations
- **Present**: Frame present

### Resources
GPU resources tracked by unique `ResourceId`:
- **Textures**: 2D, 3D, cube, array textures with mips
- **Buffers**: Vertex, index, constant, structured buffers
- **Shaders**: Compiled shader programs

### Pipeline State
At any event, the complete GPU pipeline is inspectable:
- Bound shaders (VS, HS, DS, GS, PS, CS)
- Vertex inputs (attribute layout)
- Render targets and depth target
- Viewports and scissors
- Blend, depth/stencil, rasterizer state
- Shader resources (textures, buffers, samplers)
- Constant buffer contents

### Replay
Captures can be replayed on the local GPU. The ReplayController allows:
- Setting the current event (seeking to any draw call)
- Reading back textures, buffers, mesh data
- Picking pixels
- Fetching GPU counters
- Disassembling shaders

## CLI Coverage Map

| RenderDoc Feature            | CLI Command                | Status    |
|-----------------------------|---------------------------|-----------|
| Open/close capture          | `capture info`            | ✅ Done   |
| Capture metadata            | `capture info`            | ✅ Done   |
| List sections               | `capture info`            | ✅ Done   |
| Extract thumbnail           | `capture thumb`           | ✅ Done   |
| Convert capture             | `capture convert`         | ✅ Done   |
| List all actions            | `actions list`            | ✅ Done   |
| Action summary              | `actions summary`         | ✅ Done   |
| Find actions by name        | `actions find`            | ✅ Done   |
| Get single action           | `actions get`             | ✅ Done   |
| Filter draw calls only      | `actions list --draws-only` | ✅ Done |
| List textures               | `textures list`           | ✅ Done   |
| Get texture details         | `textures get`            | ✅ Done   |
| Save texture to file        | `textures save`           | ✅ Done   |
| Save render target outputs  | `textures save-outputs`   | ✅ Done   |
| Pick pixel value            | `textures pick`           | ✅ Done   |
| Pipeline state              | `pipeline state`          | ✅ Done   |
| Shader disassembly          | `pipeline disasm`         | ✅ Done   |
| Constant buffer contents    | `pipeline cbuffer`        | ✅ Done   |
| List resources              | `resources list`          | ✅ Done   |
| List buffers                | `resources buffers`       | ✅ Done   |
| Read buffer data            | `resources read-buffer`   | ✅ Done   |
| Vertex inputs               | `mesh inputs`             | ✅ Done   |
| Post-VS outputs             | `mesh outputs`            | ✅ Done   |
| GPU counters list           | `counters list`           | ✅ Done   |
| Fetch counter results       | `counters fetch`          | ✅ Done   |
| Remote capture              | —                         | ❌ Future |
| Shader debugging            | —                         | ❌ Future |
| Resource diff               | —                         | ❌ Future |
