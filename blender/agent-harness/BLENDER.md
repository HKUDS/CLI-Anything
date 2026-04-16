# Blender: Project-Specific Analysis & SOP

## Architecture Summary

Blender is a 3D creation suite supporting modeling, animation, rendering,
compositing, and video editing. Its native `.blend` format is a custom binary
format. The CLI uses a JSON scene description that can generate Blender Python
(`bpy`) scripts for actual rendering.

```
┌──────────────────────────────────────────┐
│              Blender GUI                 │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐  │
│  │ 3D View  │ │ Timeline │ │ Props   │  │
│  └────┬─────┘ └────┬─────┘ └────┬────┘  │
│       │             │            │        │
│  ┌────┴─────────────┴────────────┴─────┐ │
│  │       bpy (Blender Python API)      │ │
│  │  Full scripting access to all       │ │
│  │  objects, materials, modifiers      │ │
│  └─────────────────┬───────────────────┘ │
│                    │                      │
│  ┌─────────────────┴───────────────────┐ │
│  │     Render Engines                  │ │
│  │  Cycles | EEVEE | Workbench         │ │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

## CLI Strategy: JSON Scene + bpy Script Generation

Since `.blend` is binary, we maintain scene state in JSON and generate
complete `bpy` Python scripts that Blender can execute:

```bash
blender --background --python generated_script.py
```

### Core Domains

| Domain | Module | Key Operations |
|--------|--------|----------------|
| Scene | `scene.py` | Create, open, save, profiles, info |
| Objects | `objects.py` | Add primitives, transform, duplicate, remove |
| Materials | `materials.py` | Principled BSDF, color, metallic, roughness |
| Modifiers | `modifiers.py` | Subdivision, mirror, array, bevel, boolean |
| Lighting | `lighting.py` | Cameras (perspective/ortho), lights (point/sun/spot/area) |
| Animation | `animation.py` | Keyframes, frame range, FPS, interpolation |
| Render | `render.py` | Cycles/EEVEE settings, resolution, samples, output |
| Session | `session.py` | Undo/redo with deep-copy snapshots |

### Modifier Registry

8 modifiers with full parameter validation:
- `subdivision_surface`: levels, render_levels
- `mirror`: axis_x/y/z, use_bisect
- `array`: count, offset
- `bevel`: width, segments
- `solidify`: thickness, offset
- `decimate`: ratio, type
- `boolean`: operation (union/intersect/difference), object
- `smooth`: factor, iterations

### Render Presets

7 presets covering Cycles, EEVEE, and Workbench:
- `cycles_default`: 128 samples, denoising
- `cycles_high`: 4096 samples, denoising, transparent film
- `cycles_preview`: 32 samples, fast preview
- `eevee_default`: 64 samples
- `eevee_high`: 256 samples, bloom, AO, SSR
- `eevee_preview`: 16 samples
- `workbench`: Flat/studio lighting preview

### Rendering Gap: Low Risk

Blender's Python API (`bpy`) provides complete access to all functionality.
The generated scripts create the exact scene described in JSON, then render.
No translation gap — bpy is the native API.

## Export: bpy Script Generation

The `render execute` command generates a complete Python script:
1. Creates all objects with correct mesh types and transforms
2. Creates and assigns materials with all Principled BSDF properties
3. Adds and configures modifiers
4. Sets up cameras and lights
5. Configures animation keyframes
6. Sets render engine and settings
7. Renders to output file

Generated scripts are validated as syntactically correct Python in tests.
