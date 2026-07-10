# SBOX.md - s&box CLI Harness SOP

## Software Overview

**s&box** is a C#-based game engine by Facepunch Studios, built on Valve's Source 2.
It uses a Scene -> GameObject -> Component architecture with built-in multiplayer,
hot-reload, and Razor UI. Games are published to sbox.game.

- **Engine:** Source 2 (.NET 10.0 / C# 14)
- **Editor:** `sbox-dev.exe` (GUI)
- **Server:** `sbox-server.exe` (headless, CLI-capable)
- **Standalone:** `sbox-standalone.exe`
- **Asset tools:** `resourcecompiler.exe`, `fbx2dmx.exe`, `obj2dmx.exe`

## File Formats

| Format | Type | Description |
|--------|------|-------------|
| `.sbproj` | JSON | Project manifest (title, type, metadata, packages) |
| `.scene` | JSON | Scene files (GameObjects, Components, SceneProperties) |
| `.prefab` | JSON | Prefab templates (same structure as scenes, single RootObject) |
| `Input.config` | JSON | Input action bindings (keyboard + gamepad) |
| `Collision.config` | JSON | Collision layers and pair rules |
| `.cs` | C# | Component source code |
| `.vmat` | Text | Material definitions |
| `.sound` | JSON | Sound event definitions |
| `.razor` | Razor | UI component files |

## Backend Integration

The CLI manipulates JSON project files directly and invokes s&box executables:

1. **Data layer:** Direct JSON manipulation of .sbproj, .scene, .prefab, configs
2. **Code generation:** Generate C# files following s&box component patterns
3. **Server backend:** `sbox-server.exe` for headless game server operations
4. **Editor launch:** `sbox-dev.exe` to open projects in the editor
5. **Asset compilation:** `resourcecompiler.exe` for asset pipeline

### Server CLI Commands (sbox-server.exe)

```
game <gameident>              - load a game
game <gameident> <mapident>   - load a game with a map
find <text>                   - find a concommand or convar
kick <id>                     - kick a player by name or steam id
status                        - current game status
quit                          - quit
```

## CLI Command Groups

```
cli-anything-sbox
├── project         # .sbproj management
│   ├── new         # Create new s&box project
│   ├── info        # Show project metadata
│   ├── config      # Modify project settings
│   ├── add-package # Add a package reference
│   ├── remove-package # Remove a package reference
│   └── validate    # Lint: broken refs, duplicate GUIDs, malformed inputs
├── scene           # .scene file manipulation
│   ├── new         # Create new scene
│   ├── info        # Show scene contents
│   ├── list        # List GameObjects in scene
│   ├── add-object  # Add a GameObject
│   ├── remove-object # Remove a GameObject
│   ├── add-component # Add component to object
│   ├── remove-component # Remove component from object
│   ├── modify-object # Rename, move, scale, retag objects
│   ├── modify-component # Modify a component's properties on an object
│   ├── clone-object # Duplicate a GameObject
│   ├── get-object  # Inspect one GameObject in detail
│   ├── set-property  # Modify SceneProperties (tick rate, navmesh, etc.)
│   ├── set-navmesh # Configure NavMesh properties
│   ├── list-presets # List built-in component preset names
│   ├── query       # Find objects by component / tag / name / bounds / enabled
│   ├── refs        # Extract every asset reference (grouped by category)
│   ├── bulk-modify # Apply same modification to all matching objects
│   ├── diff        # Structural diff between two scenes (Name-keyed)
│   └── instantiate-prefab # Insert a prefab as a new GameObject (PrefabSource ref)
├── prefab          # .prefab management
│   ├── new         # Create new prefab
│   ├── info        # Show prefab contents
│   ├── from-scene  # Extract object from scene to prefab
│   ├── add-component # Add component to prefab root
│   ├── remove-component # Remove component from prefab
│   ├── list        # List prefabs in project
│   ├── refs        # Extract asset references from a prefab
│   ├── modify-component # Modify a component's properties in a prefab
│   └── diff        # Structural diff between two prefabs (root + children)
├── codegen         # C# code generation
│   ├── component   # Generate component class (+ RPC stubs)
│   ├── gameresource # Generate GameResource class
│   ├── editor-menu # Generate editor menu class
│   ├── razor       # Generate Razor UI component + SCSS
│   ├── class       # Generate plain C# class
│   └── panel-component # Scaffold PanelComponent + sibling ScreenPanel pattern
├── input           # Input.config management
│   ├── list        # List all input actions
│   ├── add         # Add input action
│   ├── remove      # Remove input action
│   └── set         # Modify existing action
├── collision       # Collision.config management
│   ├── list        # List layers and rules
│   ├── add-layer   # Add collision layer
│   ├── add-rule    # Add/modify collision rule
│   ├── remove-rule # Remove collision pair rule
│   └── remove-layer # Remove a collision layer
├── material        # .vmat material management
│   ├── new         # Create PBR material
│   ├── info        # Parse material properties
│   ├── list        # List project materials
│   └── set         # Update material properties
├── sound           # .sound event management
│   ├── new         # Create sound event
│   ├── info        # Show sound event details
│   ├── list        # List project sound events
│   └── set         # Update sound event properties
├── localization    # Translation file management
│   ├── new         # Create translation file
│   ├── list        # List translation keys
│   ├── set         # Set key-value pair
│   ├── get         # Get value by key
│   ├── remove      # Remove translation key
│   └── bulk-set    # Set multiple keys from a JSON object
├── server          # Dedicated server management
│   ├── start       # Launch sbox-server.exe
│   └── info        # Show server executable path/version
├── asset           # Asset listing, inspection, reference graph
│   ├── list        # List project assets by type
│   ├── info        # Show asset file details
│   ├── compile     # Compile asset via resourcecompiler.exe
│   ├── find-refs   # Reverse lookup: scenes/prefabs that reference an asset
│   ├── find-unused # Project assets unreferenced by any scene/prefab
│   ├── rename      # Rename an asset and update every scene/prefab reference
│   └── move        # Move an asset to a new path and update every reference
├── test            # Map generation regression tests
│   ├── setup       # Verify paths, create test scene
│   └── run         # Run map generation tests across strategy/size/seed
├── launch          # Open project in s&box editor
└── session         # State management
    ├── status      # Current session state
    ├── undo        # Undo last operation
    └── redo        # Redo undone operation
```

## State Model

Session state (JSON file) tracks:
- Current project path (.sbproj)
- Open scene path
- Operation history (undo/redo stack)
- Modified flag

## Project Structure Created by CLI

```
<project_name>/
├── <project_name>.sbproj
├── .editorconfig
├── Assets/
│   └── scenes/
│       └── minimal.scene
├── Code/
│   ├── Assembly.cs
│   └── MyComponent.cs
├── Editor/
│   └── Assembly.cs
├── Libraries/
├── Localization/
└── ProjectSettings/
    ├── Input.config
    └── Collision.config
```

## Key Architectural Decisions

1. **JSON-first:** All s&box project files are JSON - no binary format manipulation needed
2. **GUID generation:** Every GameObject and Component needs a unique GUID (UUID v4)
3. **No runtime dependency on s&box editor** for file manipulation - the CLI reads/writes
   JSON directly. Only `server` and `launch` commands need the actual s&box installation.
4. **Code generation follows s&box conventions:** `sealed class` for non-networked,
   `partial class` for networked, `[Property]` attributes, Allman braces, tab indentation.
5. **Scene format stability:** Scene JSON format is well-defined with __guid, __type patterns.
