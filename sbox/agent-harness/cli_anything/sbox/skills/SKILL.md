---
name: "cli-anything-sbox"
description: >-
  Agent-native CLI for the s&box game engine (Facepunch Studios, Source 2):
  project management, scene/prefab editing, material/sound/localization configs,
  C# code generation, asset graph queries, project validation, and editor launch.
---

# s&box CLI

Agent-native CLI for the s&box game engine (Facepunch Studios, Source 2). 79+ commands across 14 groups. Manipulate `.scene`, `.prefab`, `.vmat`, `.sound`, `Input.config`, `Collision.config` JSON files directly, generate idiomatic C# components, and run a real-time asset graph over the project.

## Installation

```bash
pip install git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=sbox/agent-harness
```

## Requirements

- Python 3.10+
- s&box installed via Steam - auto-detected, or set `SBOX_PATH` to a custom installation directory.
- Most commands work entirely on the project's JSON files - s&box does not need to be running.

## Global Options

```
--json          Machine-readable JSON output (always pass for agent use)
--project PATH  Project directory (auto-detects from cwd .sbproj if omitted)
```

## Command Groups

### project - Manage s&box projects

```bash
cli-anything-sbox project new --name MyGame --output-dir ./MyGame
cli-anything-sbox --json project info
cli-anything-sbox project config --max-players 32 --tick-rate 64
cli-anything-sbox --json --project ./MyGame project add-package facepunch.libsdf
cli-anything-sbox --json --project ./MyGame project remove-package facepunch.libsdf
# Lint: broken asset refs, duplicate GUIDs, malformed Input.config
cli-anything-sbox --json --project ./MyGame project validate
cli-anything-sbox --project ./MyGame project validate --no-inputs --no-guids
```

### scene - Manipulate `.scene` files

```bash
cli-anything-sbox scene new --name gameplay -o ./Assets/scenes/gameplay.scene
cli-anything-sbox --json scene info ./scene.scene
cli-anything-sbox --json scene list ./scene.scene
cli-anything-sbox scene add-object ./scene.scene Enemy --position "100,0,0" --components "model,box_collider,rigidbody" --tags "enemy"
cli-anything-sbox scene remove-object ./scene.scene --name Enemy
cli-anything-sbox scene add-component ./scene.scene <object-guid> Sandbox.PointLight
cli-anything-sbox scene remove-component ./scene.scene <object-guid> --component-type Sandbox.Rigidbody
cli-anything-sbox --json scene modify-object ./scene.scene --guid <guid> --name NewName --position "200,0,0"
cli-anything-sbox --json scene clone-object ./scene.scene --name Enemy --new-name EnemyCopy --position "300,0,0"
cli-anything-sbox --json scene get-object ./scene.scene --name Sun
cli-anything-sbox scene set-property ./scene.scene --fixed-update-freq 64 --timescale 0.5
cli-anything-sbox scene set-navmesh ./scene.scene --enabled --agent-height 72 --agent-radius 16
cli-anything-sbox --json scene list-presets
cli-anything-sbox --json scene modify-component ./scene.scene <object-guid> <component-guid> --properties '{"Damage":50}'

# Find objects matching one or more filters (AND-combined)
cli-anything-sbox --json scene query ./scene.scene --has-component rigidbody --has-tag tower
cli-anything-sbox --json scene query ./scene.scene --name-regex "^Tower\d$" --in-bounds "0,-500,-50,1000,500,50"

# Extract every asset reference (.vmdl, .vmat, .vsnd, .vtex, .vpcf, .prefab) from a scene
cli-anything-sbox --json scene refs ./scene.scene

# Apply the same modification to every object that matches a query
cli-anything-sbox --json scene bulk-modify ./scene.scene --has-tag tower --position "0,0,100" --enable

# Structural diff between two scenes (added/removed/modified GameObjects + SceneProperties)
cli-anything-sbox --json scene diff ./old.scene ./new.scene

# Insert a prefab as a GameObject in a scene
cli-anything-sbox --json scene instantiate-prefab ./level.scene ./Assets/prefabs/bullet.prefab --position "10,0,0"
```

### prefab - Manage `.prefab` files

```bash
cli-anything-sbox prefab new --name Bullet -o ./Assets/prefabs/bullet.prefab --components "model,sphere_collider,rigidbody"
cli-anything-sbox --json prefab info ./Assets/prefabs/bullet.prefab
cli-anything-sbox prefab from-scene ./scene.scene <object-guid> -o ./Assets/prefabs/extracted.prefab
cli-anything-sbox --json prefab add-component ./prefab.prefab rigidbody
cli-anything-sbox prefab remove-component ./prefab.prefab --component-type Sandbox.Rigidbody
cli-anything-sbox --json prefab list

# Asset references inside a prefab
cli-anything-sbox --json prefab refs ./prefab.prefab

# Modify component properties on a prefab (by component type or component GUID)
cli-anything-sbox --json prefab modify-component ./prefab.prefab --component-type Sandbox.Rigidbody --properties '{"Gravity":false,"MassOverride":50}'

# Structural diff between two prefabs (root + named children)
cli-anything-sbox --json prefab diff ./old.prefab ./new.prefab
```

### codegen - Generate C# code

```bash
# Plain Component
cli-anything-sbox codegen component --name PlayerController --methods OnUpdate,OnFixedUpdate -o ./Code/PlayerController.cs

# Component with [Property] fields
cli-anything-sbox --json codegen component --name Tower --properties '[{"name":"Damage","type":"float","default":"25f"},{"name":"Range","type":"float","default":"500f"}]'

# Networked component (partial class) with RPC method stubs
cli-anything-sbox codegen component --name NetPlayer --networked --methods OnUpdate,OnFixedUpdate --rpc-methods "Fire:Broadcast,TakeDamage:Host" -o ./Code/NetPlayer.cs

# GameResource
cli-anything-sbox codegen gameresource --name TowerData --display-name "Tower Data" --extension tower -o ./Code/TowerData.cs

# Editor menu (Editor/ assembly)
cli-anything-sbox codegen editor-menu --name MyTools --menu-path "Editor/My Tools/Open" -o ./Editor/MyTools.cs

# Plain Razor UI component (.razor + .razor.scss)
cli-anything-sbox codegen razor --name HudPanel --properties '[{"name":"Score","type":"int","default":"0"}]' -o ./UI/HudPanel.razor

# Static or base-derived class
cli-anything-sbox codegen class --name Math2 --static -o ./Code/Math2.cs

# PanelComponent + sibling ScreenPanel scaffold (handles the s&box quirk where
# PanelComponent input only works when both are on the same GameObject).
# Emits .razor + .razor.scss + a paste-ready GameObject snippet, or appends
# directly to a scene with --scene.
cli-anything-sbox --json codegen panel-component --name HudBar -o ./UI/HudBar.razor
cli-anything-sbox codegen panel-component --name Crosshair -o ./UI/Crosshair.razor --scene ./Assets/scenes/game.scene
```

### input - Manage `Input.config`

```bash
cli-anything-sbox --json input list
cli-anything-sbox input add --name PlaceTower --group Gameplay --keyboard mouse1 --gamepad RightTrigger
cli-anything-sbox input remove --name PlaceTower
cli-anything-sbox input set --name Attack1 --keyboard mouse1
```

### collision - Manage `Collision.config`

```bash
cli-anything-sbox --json collision list
cli-anything-sbox collision add-layer --name projectile --default Collide
cli-anything-sbox collision add-rule --layer-a projectile --layer-b solid --result Collide
cli-anything-sbox collision remove-rule --layer-a projectile --layer-b solid
cli-anything-sbox collision remove-layer --name projectile
```

### material - Manage `.vmat` materials

```bash
cli-anything-sbox --json material new --name floor --shader complex --color-texture "textures/floor.tga" --metalness 0.3 -o ./Assets/materials/floor.vmat
cli-anything-sbox --json material info ./Assets/materials/floor.vmat
cli-anything-sbox --json material list
cli-anything-sbox --json material set ./Assets/materials/floor.vmat --metalness 0.8
```

### sound - Manage `.sound` events

```bash
cli-anything-sbox --json sound new --name gunshot --sounds "sounds/gun1.vsnd,sounds/gun2.vsnd" --volume 0.8 -o ./Assets/sounds/gunshot.sound
cli-anything-sbox --json sound info ./Assets/sounds/gunshot.sound
cli-anything-sbox --json sound list
cli-anything-sbox --json sound set ./Assets/sounds/gunshot.sound --volume 0.5
```

### localization - Manage translations

```bash
cli-anything-sbox localization new --lang en -o ./Localization/en.json
cli-anything-sbox localization set ./Localization/en.json --key "game.title" --value "My Game"
cli-anything-sbox --json localization list ./Localization/en.json
cli-anything-sbox localization get ./Localization/en.json --key "game.title"
cli-anything-sbox localization remove ./Localization/en.json --key "game.title"
cli-anything-sbox localization bulk-set ./Localization/en.json --keys '{"ui.start":"Start","ui.quit":"Quit"}'
```

### server - Dedicated server

```bash
cli-anything-sbox server info
cli-anything-sbox server start --game my_game --map facepunch.flatgrass
```

### asset - Asset management & reverse lookups

```bash
cli-anything-sbox --json asset list --type scene
cli-anything-sbox --json asset info ./Assets/scenes/minimal.scene
cli-anything-sbox asset compile ./Assets/materials/floor.vmat

# Which scenes/prefabs reference this asset?
cli-anything-sbox --json --project ./MyGame asset find-refs models/myteam/widget.vmdl

# Find unreferenced assets (per type, or across all referenceable types)
cli-anything-sbox --json --project ./MyGame asset find-unused
cli-anything-sbox --json --project ./MyGame asset find-unused --type model --type material

# Rename an asset and update every scene/prefab reference (extension preserved if omitted)
cli-anything-sbox --json --project ./MyGame asset rename models/team/widget.vmdl gizmo
cli-anything-sbox --project ./MyGame asset rename models/team/widget.vmdl gizmo --dry-run

# Move an asset across directories and update every reference
cli-anything-sbox --json --project ./MyGame asset move models/team/widget.vmdl models/shared/widget.vmdl
```

### session - State management

```bash
cli-anything-sbox session status
cli-anything-sbox session undo
cli-anything-sbox session redo
```

### test - Automated map/scene generation harness

```bash
cli-anything-sbox test setup
cli-anything-sbox --json test run
```

### launch - Open project in s&box editor

```bash
cli-anything-sbox launch
```

## Component Presets

29 short names usable with `--components` on `scene add-object`, `prefab new`, etc. Each maps to a `Sandbox.*` component type.

| Preset | Component Type |
|--------|---------------|
| `model` | `Sandbox.ModelRenderer` |
| `box_collider` | `Sandbox.BoxCollider` |
| `sphere_collider` | `Sandbox.SphereCollider` |
| `capsule_collider` | `Sandbox.CapsuleCollider` |
| `plane_collider` | `Sandbox.PlaneCollider` |
| `model_collider` | `Sandbox.ModelCollider` |
| `rigidbody` | `Sandbox.Rigidbody` |
| `character_controller` | `Sandbox.CharacterController` |
| `player_controller` | `Sandbox.PlayerController` |
| `camera` | `Sandbox.CameraComponent` |
| `light_directional` | `Sandbox.DirectionalLight` |
| `light_point` | `Sandbox.PointLight` |
| `spot_light` | `Sandbox.SpotLight` |
| `ambient_light` | `Sandbox.AmbientLight` |
| `sprite_renderer` | `Sandbox.SpriteRenderer` |
| `skinned_model_renderer` | `Sandbox.SkinnedModelRenderer` |
| `text_renderer` | `Sandbox.TextRenderer` |
| `line_renderer` | `Sandbox.LineRenderer` |
| `decal_renderer` | `Sandbox.DecalRenderer` |
| `trail_renderer` | `Sandbox.TrailRenderer` |
| `particle_effect` | `Sandbox.ParticleEffect` |
| `sound_point` | `Sandbox.SoundPointComponent` |
| `nav_mesh_agent` | `Sandbox.NavMeshAgent` |
| `screen_panel` | `Sandbox.ScreenPanel` |
| `world_panel` | `Sandbox.WorldPanel` |
| `fixed_joint` | `Sandbox.FixedJoint` |
| `hinge_joint` | `Sandbox.HingeJoint` |
| `spring_joint` | `Sandbox.SpringJoint` |
| `ball_socket_joint` | `Sandbox.BallSocketJoint` |

`scene list-presets` returns the live preset registry as JSON.

## Agent Usage Pattern

Pass `--json` for every agent-driven invocation. Pipe through `jq` to thread GUIDs and paths between commands:

```bash
# Bootstrap a project
sbproj=$(cli-anything-sbox --json project new --name MyGame --output-dir /tmp/MyGame | jq -r '.sbproj')
cd /tmp/MyGame

# Add a tower with a specific component layout, capture its GUID
guid=$(cli-anything-sbox --json scene add-object ./Assets/scenes/main.scene Tower \
    --components "model,box_collider,rigidbody" --tags "tower" \
    | jq -r '.guid')

# Generate the corresponding C# component, networked
cli-anything-sbox --json codegen component --name Tower --networked \
    --rpc-methods "Fire:Host" --properties '[{"name":"Damage","type":"float","default":"25f"}]' \
    -o ./Code/Tower.cs

# Bulk-tweak every tower in the scene
cli-anything-sbox --json scene bulk-modify ./Assets/scenes/main.scene \
    --has-tag tower --enable --position-y-add 50

# Validate before committing
cli-anything-sbox --json project validate
```

## REPL Mode

`cli-anything-sbox` with no arguments enters an interactive REPL with a styled prompt:

```
$ cli-anything-sbox
cli-anything-sbox> project info
cli-anything-sbox> scene list ./Assets/scenes/main.scene
cli-anything-sbox> codegen component --name Foo -o ./Code/Foo.cs
cli-anything-sbox> quit
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SBOX_PATH` | s&box installation directory | Auto-detected from Steam library folders |
| `CLI_ANYTHING_SKILL_REPO` | Override the repo `repl_skin` reads SKILL.md from | `HKUDS/CLI-Anything` |
