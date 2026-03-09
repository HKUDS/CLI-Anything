# Blender CLI Harness - Test Documentation

## Test Inventory

| File | Test Classes | Test Count | Focus |
|------|-------------|------------|-------|
| `test_core.py` | 8 | 156 | Unit tests for scene, objects, materials, modifiers, lighting, animation, render, session |
| `test_full_e2e.py` | 5 | 44 | E2E workflows: BPY script generation, scene lifecycle, CLI subprocess |
| **Total** | **13** | **200** | |

## Unit Tests (`test_core.py`)

All unit tests use synthetic/in-memory data only. No Blender installation required.

### TestScene (16 tests)
- Create scene with defaults and custom settings (name, render engine, fps)
- Reject invalid render engine and invalid fps
- Save and open scene roundtrip
- Open nonexistent file raises error
- Get scene info with object/material/animation counts
- List available render engines
- Set scene properties: name, frame range, fps
- Reject invalid frame ranges (end before start)
- Scene metadata includes creation timestamp

### TestObjects (30 tests)
- Add all mesh primitive types: cube, sphere, cylinder, cone, plane, torus, monkey, empty, camera, light
- Add object with custom name, location, rotation, scale
- Reject invalid object type
- Remove object by index; reject invalid index
- Duplicate object creates independent copy
- Set object properties: name, location, rotation, scale, visible, locked
- Reject invalid property names
- Get single object; list all objects
- Unique IDs for all objects
- Parent/unparent objects
- Parent to nonexistent object raises error
- Set object dimensions directly

### TestMaterials (16 tests)
- Create material with defaults and custom color
- Reject invalid color format
- Assign material to object; reject invalid object index
- Remove material
- Set material properties: color, metallic, roughness, specular, emission
- Reject out-of-range metallic/roughness values
- Duplicate material
- List materials; get material by index
- Material names auto-deduplicate

### TestModifiers (20 tests)
- Add all modifier types: subdivision, mirror, array, solidify, bevel, boolean, decimate, smooth, wireframe
- Reject invalid modifier type
- Add modifier with custom params
- Reject invalid/out-of-range params
- Remove modifier; reject invalid modifier index
- Set modifier param after creation
- List modifiers on an object
- Move modifier up/down in stack
- All modifier types have valid param definitions

### TestLighting (24 tests)
- Add all light types: point, sun, spot, area
- Reject invalid light type
- Set light properties: color, energy/power, size, shadow enabled
- Reject out-of-range energy and size
- Set spot-specific properties: spot_size, spot_blend
- Reject spot properties on non-spot lights
- Add camera with default and custom settings
- Set camera properties: focal_length, sensor_size, clip_start, clip_end, type
- Reject invalid camera type and out-of-range focal length
- Set active camera
- List all lights; list all cameras

### TestAnimation (19 tests)
- Set frame range; reject invalid range
- Add keyframe to object at frame
- Reject keyframe on invalid object/property
- Remove keyframe
- List keyframes for object
- Set interpolation type on keyframe; reject invalid type
- Add keyframe for all animatable properties (location, rotation, scale, visible)
- Set animation fps
- Get animation info (frame range, keyframe counts)
- Clear all keyframes on object

### TestRender (16 tests)
- Set render resolution; reject invalid resolution
- Set render engine; reject invalid engine
- Set output format; reject invalid format
- Set output path
- Set samples; reject non-positive samples
- Set film transparent flag
- Get full render settings
- List available output formats
- List available render engines
- Set render region (crop)
- Set percentage scale for resolution

### TestSession (15 tests)
- Create session; set/get project; get project when none set raises error
- Undo/redo cycle; undo empty; redo empty
- Snapshot clears redo stack
- Session status reports depth
- Save session to file
- List history entries
- Max undo limit enforced
- Undo reverses object addition
- Undo reverses material assignment

## End-to-End Tests (`test_full_e2e.py`)

E2E tests validate BPY (Blender Python) script generation, scene roundtrips, and CLI subprocess invocation. No Blender binary required.

### TestSceneLifecycle (6 tests)
- Create, save, open roundtrip preserves all fields
- Scene with objects roundtrip maintains object data
- Scene with materials roundtrip preserves material assignments
- Scene with modifiers roundtrip preserves modifier stacks
- Scene with animation roundtrip preserves keyframes
- Complex scene roundtrip with objects, materials, modifiers, lights, cameras, animation

### TestBPYScriptGeneration (27 tests)
- Empty scene generates valid Python script with imports
- Script includes object creation calls for each mesh primitive
- Script includes material creation and assignment
- Script includes modifier addition with correct params
- Script includes light and camera setup
- Script includes animation keyframe insertion
- Script includes render settings configuration
- Script includes frame range and fps settings
- Script handles multiple objects, materials, modifiers in sequence
- Script escapes special characters in names
- Complex scene produces script with all elements combined
- Script is syntactically valid Python (compile check)

### TestWorkflows (6 tests)
- Product render workflow: model with materials, lighting, camera, render settings
- Animation workflow: object with keyframes, frame range, output as video
- Architectural visualization: multiple objects, materials, sun light, camera
- Modifier stack workflow: object with chained subdivision + mirror + bevel
- Multi-object scene: several primitives with transforms and materials
- Scene organization: parent/child hierarchy, visibility toggles

### TestCLISubprocess (8 tests)
- `--help` prints usage
- `scene new` creates scene
- `scene new --json` outputs valid JSON
- `object types` lists all primitive types
- `material new` creates material
- `modifier types` lists modifier types
- `render engines` lists render engines
- Full workflow via JSON CLI

### TestScriptValidity (3 tests)
- Generated script compiles without SyntaxError
- Generated script contains no undefined references to scene data
- Complex workflow script maintains valid Python throughout

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.11, pytest-9.0.2, pluggy-1.5.0
rootdir: ./CLI-Anything
plugins: langsmith-0.5.1, anyio-4.12.0
collected 200 items

test_core.py   156 passed
test_full_e2e.py   44 passed

============================= 200 passed in 1.51s ==============================
```
