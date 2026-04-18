---
name: cli-hub-matrix-3d-cad
description: >-
  Capability-based multi-tool matrix for 3D modeling, CAD, point clouds, rendering,
  GPU debugging, and fabrication. Covers mesh/parametric/photogrammetry and the
  path from idea to printed part or game-ready asset.
---

# 3D & CAD Matrix (S3 — v2 capability-based)

Scenario **S3**. Strongest technical scenario in the matrix by depth — Blender + FreeCAD + CloudCompare + RenderDoc is rare coverage. Structural gaps: **texturing** and **fabrication slicing**.

Schema: [`docs/cli-matrix/matrix_registry.schema.md`](../../docs/cli-matrix/matrix_registry.schema.md). Matrix plan: [`docs/cli-matrix/cli-matrix-plan.md`](../../docs/cli-matrix/cli-matrix-plan.md).

## Install

```bash
cli-hub matrix install 3d-cad
cli-hub matrix info    3d-cad
```

---

## Decision rubric

1. **Available & adequate** — ranked by quality then inverse cost.
2. **Free-to-install** — Python libs / native binaries without credentials.
3. **Harness / public CLI install** — when warranted.
4. **Paid API escalation** — only when lower tiers can't meet the bar, env holds the key, or the user consents.

Offline context? Most of this matrix is offline-first; rendering and photogrammetry are the exceptions.

---

## Preflight

```bash
cli-hub list --json
python - <<'PY'
import importlib.util
for m in ("trimesh","pymeshlab","open3d","cadquery","build123d","solid",
          "pygltflib","laspy","pyvista","bpy","rawpy","pycam"):
    print(m, importlib.util.find_spec(m) is not None)
PY
for b in blender freecad meshroom colmap openmvg openmvs prusaslicer slic3r \
         cura CuraEngine apitrace vulkaninfo renderdoc OpenSCAD; do
  command -v "$b" >/dev/null && echo "$b: yes" || echo "$b: no"
done
for e in POLYCAM_API_KEY LUMA_API_KEY ONSHAPE_ACCESS_KEY FUSION360_TOKEN \
         OCTANE_TOKEN; do
  [ -n "${!e}" ] && echo "$e: set" || echo "$e: unset"
done
```

---

## Suggest-to-user template

```
To enable <capability> via <provider>, please set <ENV_VAR>.
  Cost: <cost notes>
  Quality: <quality tier>
Reply 'skip' to fall back to <next provider>.
```

Example: *To enable cloud photogrammetry via Luma AI, please set `LUMA_API_KEY`. Cost: metered per-scan. Quality: sota. Reply 'skip' to fall back to local `Meshroom` (slower, free).*

---

## Capabilities

### `model.mesh` — mesh modeling / editing

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-blender` | harness-cli | Blender installed | free | sota | yes |
| `trimesh` | python | pkg | free | high | yes |
| `pymeshlab` | python | pkg | free | high | yes |
| `open3d` | python | pkg | free | high | yes |
| `pygalmesh` | python | pkg + CGAL | free | high | yes |

### `model.parametric` — parametric CAD

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-freecad` | harness-cli | FreeCAD installed | free | sota | yes |
| `cadquery` | python | pkg | free | high | yes |
| `build123d` | python | pkg | free | high | yes |
| `OpenSCAD` | native | binary | free | high | yes |
| `SolidPython` | python | pkg + OpenSCAD | free | good | yes |
| Onshape API | api | `ONSHAPE_ACCESS_KEY` | paid | sota | no |
| Fusion 360 API | api | `FUSION360_TOKEN` | paid | sota | no |

### `model.sculpt` — digital sculpting

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-blender` (sculpt mode, scripted) | harness-cli | Blender | free | good | yes |
| ZBrush / Nomad | — | — | — | — | — |

Known gap — agent-driven sculpting is impractical beyond Blender scripts.

### `pointcloud.process` — point cloud ingest / clean / register

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-cloudcompare` | harness-cli | CloudCompare | free | sota | yes |
| `cli-anything-cloudanalyzer` | harness-cli | harness installed | free | high | yes |
| `open3d` | python | pkg | free | high | yes |
| `laspy` | python | pkg | free | high | yes |
| `pdal` | native | binary | free | sota | yes |
| `pyvista` | python | pkg | free | high | yes |

### `photogrammetry.reconstruct` — images → 3D mesh

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `Meshroom` | native | binary | free | high | yes |
| `colmap` | native | binary | free | high | yes |
| `OpenMVG` + `OpenMVS` | native | binaries | free | high | yes |
| RealityCapture | native | commercial license | paid | sota | yes |
| Polycam API | api | `POLYCAM_API_KEY` | metered | sota | no |
| Luma AI | api | `LUMA_API_KEY` | metered | sota | no |

### `material.texture` — PBR texturing

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-blender` (shader nodes, scripted) | harness-cli | Blender | free | good | yes |
| `bpy` PBR synthesis | python | pkg | free | good | yes |
| `Pillow` procedural maps | python | pkg | free | basic | yes |
| Substance 3D / Polycam Materials / Adobe Sampler | — | — | — | — | — |

**Known gap** — no agent-native path approaches Substance quality.

### `render.preview` — fast viewport renders

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-blender` (Eevee) | harness-cli | Blender | free | high | yes |
| `cli-anything-godot` (viewport screenshot) | harness-cli | Godot | free | good | yes |

### `render.offline` — path-traced / final renders

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-blender` (Cycles) | harness-cli | Blender + GPU | free | sota | yes |
| `bpy` + Cycles | python | pkg + GPU | free | sota | yes |
| Octane Cloud | api | `OCTANE_TOKEN` | paid | sota | no |
| RenderMan on offline farm | — | license + farm | paid | sota | depends |

### `gpu.debug` — capture / inspect GPU frames

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-renderdoc` | harness-cli | RenderDoc installed | free | sota | yes |
| `apitrace` | native | binary | free | high | yes |
| `vulkan-tools` | native | binary | free | good | yes |

### `fabricate.slice` — 3D print slicer (mesh → gcode)

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `PrusaSlicer` CLI | native | binary | free | sota | yes |
| `CuraEngine` | native | binary | free | high | yes |
| `slic3r` | native | binary | free | good | yes |
| Bambu Studio / OrcaSlicer (API-driven) | — | — | — | — | — |

**Known gap** — no agent-native harness, though the natives are scriptable.

### `fabricate.cam` — CAM / CNC toolpaths

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-freecad` (Path workbench, scripted) | harness-cli | FreeCAD | free | good | yes |
| `pycam` | python | pkg | free | good | yes |
| `kiri:moto` | native | binary | free | good | yes |
| Fusion 360 CAM / Onshape CAM | api | tokens | paid | sota | no |

### `export.engine` — handoff to game / viz engine

| Provider | Kind | Requires | Cost | Quality | Offline |
|---|---|---|---|---|---|
| `cli-anything-godot` | harness-cli | Godot | free | high | yes |
| `cli-anything-blender` (glTF/FBX export) | harness-cli | Blender | free | sota | yes |
| `pygltflib` | python | pkg | free | high | yes |
| `trimesh` glTF writer | python | pkg | free | good | yes |
| Unity Asset Pipeline / Unreal Datasmith | — | — | — | — | — |

---

## Recipes

- **`printable-part`** — parametric CAD → mesh → slice → gcode.
  Uses: `model.parametric`, `model.mesh`, `fabricate.slice`.

- **`game-asset`** — model → texture → export to engine.
  Uses: `model.mesh`, `material.texture`, `export.engine`, (optional `render.preview`).

- **`reality-scan`** — photos → photogrammetry → clean mesh → export.
  Uses: `photogrammetry.reconstruct`, `pointcloud.process`, `model.mesh`, `export.engine`.

- **`cnc-part`** — parametric part → CAM toolpath → gcode.
  Uses: `model.parametric`, `fabricate.cam`.

- **`product-viz-still`** — CAD → import → scene → offline render.
  Uses: `model.parametric`, `model.mesh`, `material.texture`, `render.offline`.

- **`gpu-bug-repro`** — capture frame → analyze → patch shader.
  Uses: `gpu.debug`, `render.preview`.

---

## Known gaps

- **`material.texture`** — no open equivalent to Substance; Blender shader nodes are the current ceiling.
- **`fabricate.slice`** — PrusaSlicer/Cura natives work but want a harness-level wrapper.
- **`model.sculpt`** — impractical for agents today.
- **Unity / Unreal export** — only Godot covered on the harness side.

---

## Agent guidance

- **Parametric first, mesh later.** Start in `model.parametric` when the object has dimensions; `model.mesh` when it's organic.
- **Always bake before export.** When handing off to `export.engine`, apply modifiers and bake materials — runtime engines don't read Blender shader graphs.
- **Check manifold before slicing.** `fabricate.slice` fails silently on non-manifold meshes; use `trimesh.Trimesh.is_volume` or pymeshlab's manifold check first.
- **Offline by default.** This matrix is the most offline-capable — API escalation is rarely needed except for photogrammetry-at-scale.
- **Workspace discipline.** Keep `.FCStd` / `.blend` / `.ply` / `.stl` / `.gcode` in one project folder so the chain of transformations is reproducible.
