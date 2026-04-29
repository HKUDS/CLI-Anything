"""Manages s&box .scene files - loading, saving, querying, and modifying scene GameObjects."""

import json
import os
import uuid
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Component presets - shortcuts for common s&box components
# ---------------------------------------------------------------------------

COMPONENT_PRESETS: Dict[str, Dict[str, Any]] = {
    "model": {
        "__type": "Sandbox.ModelRenderer",
        "Model": "models/dev/box.vmdl",
        "RenderType": "On",
        "Tint": "1,1,1,1",
    },
    "box_collider": {
        "__type": "Sandbox.BoxCollider",
        "Center": "0,0,0",
        "Scale": "50,50,50",
        "IsTrigger": False,
        "Static": False,
    },
    "sphere_collider": {
        "__type": "Sandbox.SphereCollider",
        "Center": "0,0,0",
        "Radius": 25,
        "IsTrigger": False,
    },
    "rigidbody": {
        "__type": "Sandbox.Rigidbody",
        "Gravity": True,
        "LinearDamping": 0,
        "AngularDamping": 0,
        "Locking": {},
        "MassOverride": 0,
        "MotionEnabled": True,
        "RigidbodyFlags": 0,
        "StartAsleep": False,
    },
    "camera": {
        "__type": "Sandbox.CameraComponent",
        "FieldOfView": 60,
        "ZNear": 10,
        "ZFar": 10000,
        "IsMainCamera": True,
        "BackgroundColor": "0.33333,0.46275,0.52157,1",
    },
    "light_directional": {
        "__type": "Sandbox.DirectionalLight",
        "LightColor": "0.94419,0.97767,1,1",
        "Shadows": True,
        "SkyColor": "0.2532,0.32006,0.35349,1",
    },
    "light_point": {
        "__type": "Sandbox.PointLight",
        "LightColor": "1,1,1,1",
        "Radius": 400,
    },
    "player_controller": {
        "__type": "Sandbox.PlayerController",
    },
    "spot_light": {
        "__type": "Sandbox.SpotLight",
        "LightColor": "1,1,1,1",
        "Radius": 500,
        "ConeInner": 15,
        "ConeOuter": 45,
        "Shadows": True,
    },
    "ambient_light": {
        "__type": "Sandbox.AmbientLight",
        "Color": "1,1,1,1",
        "Intensity": 1.0,
    },
    "capsule_collider": {
        "__type": "Sandbox.CapsuleCollider",
        "Start": "0,0,0",
        "End": "0,0,72",
        "Radius": 16,
        "IsTrigger": False,
    },
    "plane_collider": {
        "__type": "Sandbox.PlaneCollider",
        "Scale": "100,100",
        "IsTrigger": False,
        "Static": True,
    },
    "model_collider": {
        "__type": "Sandbox.ModelCollider",
        "Model": "models/dev/box.vmdl",
        "IsTrigger": False,
        "Static": False,
    },
    "sprite_renderer": {
        "__type": "Sandbox.SpriteRenderer",
        "Texture": "textures/dev/white.vtex",
        "Tint": "1,1,1,1",
        "Size": "64,64",
    },
    "skinned_model_renderer": {
        "__type": "Sandbox.SkinnedModelRenderer",
        "Model": "models/citizen/citizen.vmdl",
        "RenderType": "On",
        "Tint": "1,1,1,1",
    },
    "text_renderer": {
        "__type": "Sandbox.TextRenderer",
        "Text": "Hello World",
        "FontSize": 64,
        "Color": "1,1,1,1",
    },
    "line_renderer": {
        "__type": "Sandbox.LineRenderer",
        "Color": "1,1,1,1",
        "Opaque": True,
        "Width": 2,
    },
    "decal_renderer": {
        "__type": "Sandbox.DecalRenderer",
        "Material": "materials/default.vmat",
        "Size": "128,128,128",
    },
    "particle_effect": {
        "__type": "Sandbox.ParticleEffect",
        "PlayOnStart": True,
        "Loop": True,
    },
    "sound_point": {
        "__type": "Sandbox.SoundPointComponent",
        "PlayOnStart": False,
        "StopOnDestroy": True,
    },
    "nav_mesh_agent": {
        "__type": "Sandbox.NavMeshAgent",
        "MaxSpeed": 200,
        "MaxAcceleration": 800,
        "AgentRadius": 16,
        "AgentHeight": 72,
    },
    "screen_panel": {
        "__type": "Sandbox.ScreenPanel",
        "ZIndex": 100,
        "Opacity": 1.0,
    },
    "world_panel": {
        "__type": "Sandbox.WorldPanel",
        "PanelSize": "1024,768",
        "LookAtCamera": False,
        "RenderScale": 1.0,
    },
    "fixed_joint": {
        "__type": "Sandbox.FixedJoint",
    },
    "hinge_joint": {
        "__type": "Sandbox.HingeJoint",
        "MinAngle": -45,
        "MaxAngle": 45,
    },
    "spring_joint": {
        "__type": "Sandbox.SpringJoint",
        "Frequency": 5,
        "Damping": 0.5,
    },
    "ball_socket_joint": {
        "__type": "Sandbox.BallSocketJoint",
    },
    "trail_renderer": {
        "__type": "Sandbox.TrailRenderer",
        "Color": "1,1,1,1",
        "Width": 5,
        "Lifetime": 1.0,
    },
    "character_controller": {
        "__type": "Sandbox.CharacterController",
        "Height": 72,
        "Radius": 16,
        "UseCollisionRules": True,
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _new_guid() -> str:
    """Generate a new UUID v4 string."""
    return str(uuid.uuid4())


def _make_component(component_type: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a component dict from a type string and optional properties.

    If *component_type* matches a key in COMPONENT_PRESETS, the preset values
    are used as defaults and *properties* are merged on top.  Otherwise, a
    bare component with the given __type is created.
    """
    if component_type in COMPONENT_PRESETS:
        comp = dict(COMPONENT_PRESETS[component_type])
    else:
        comp = {"__type": component_type}

    comp["__guid"] = _new_guid()

    if properties:
        comp.update(properties)

    return comp


def _make_game_object(
    name: str,
    position: str = "0,0,0",
    rotation: str = "0,0,0,1",
    scale: str = "1,1,1",
    tags: str = "",
    components: Optional[List[Dict[str, Any]]] = None,
    children: Optional[List[Dict[str, Any]]] = None,
    flags: int = 0,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Build a GameObject dict."""
    obj: Dict[str, Any] = {
        "__guid": _new_guid(),
        "Flags": flags,
        "Name": name,
        "Enabled": enabled,
        "Position": position,
        "Rotation": rotation,
        "Scale": scale,
        "Tags": tags,
        "Components": components if components else [],
        "Children": children if children else [],
    }
    return obj


def _build_default_objects() -> List[Dict[str, Any]]:
    """Return the default set of GameObjects for a minimal scene.

    Includes: Sun (DirectionalLight), 2D Skybox (SkyBox2D + EnvmapProbe),
    Plane (ModelRenderer + BoxCollider), Camera (CameraComponent + post-processing).
    """
    sun = _make_game_object(
        name="Sun",
        position="0,0,0",
        rotation="-0.0591653,0.5160446,0.0340129,0.8537855",
        components=[
            _make_component("light_directional"),
        ],
    )

    skybox = _make_game_object(
        name="2D Skybox",
        tags="skybox",
        components=[
            {
                "__guid": _new_guid(),
                "__type": "Sandbox.SkyBox2D",
                "SkyMaterial": "materials/skybox/skybox_day_01.vmat",
                "Tint": "1,1,1,1",
            },
            {
                "__guid": _new_guid(),
                "__type": "Sandbox.EnvmapProbe",
                "Texture": "textures/cubemaps/default2.vtex",
                "Bounds": "512,512,512",
                "Feathering": 0.02,
            },
        ],
    )

    plane = _make_game_object(
        name="Plane",
        position="0,0,0",
        scale="5,5,5",
        components=[
            {
                "__guid": _new_guid(),
                "__type": "Sandbox.ModelRenderer",
                "Model": "models/dev/plane.vmdl",
                "RenderType": "On",
                "Tint": "0.39546,0.51320,0.27128,1",
                "MaterialOverride": "materials/default.vmat",
            },
            {
                "__guid": _new_guid(),
                "__type": "Sandbox.BoxCollider",
                "Center": "0,0,-5",
                "Scale": "100,100,10",
                "IsTrigger": False,
                "Static": True,
            },
        ],
    )

    camera = _make_game_object(
        name="Camera",
        position="0,-200,150",
        rotation="0.16307,0,0,0.98663",
        components=[
            _make_component("camera"),
            {
                "__guid": _new_guid(),
                "__type": "Sandbox.Bloom",
                "Threshold": 0.5,
                "ThresholdWidth": 0.5,
                "MaximumBloom": 0.5,
                "Mode": "Additive",
                "BlurWeight": 1,
            },
            {
                "__guid": _new_guid(),
                "__type": "Sandbox.Tonemapping",
                "Mode": "ACES",
                "ExposureCompensation": 0,
                "MinimumExposure": 1,
                "MaximumExposure": 2,
                "Rate": 1,
            },
            {
                "__guid": _new_guid(),
                "__type": "Sandbox.Sharpen",
                "Scale": 0.2,
            },
        ],
    )

    return [sun, skybox, plane, camera]


def _flatten_objects(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recursively flatten a hierarchy of GameObjects into a flat list."""
    result: List[Dict[str, Any]] = []
    for obj in objects:
        result.append(obj)
        children = obj.get("Children", [])
        if children:
            result.extend(_flatten_objects(children))
    return result


def _remove_from_list(
    objects: List[Dict[str, Any]],
    name: Optional[str] = None,
    guid: Optional[str] = None,
) -> bool:
    """Remove a GameObject from a list (including nested Children). Returns True if removed."""
    for i, obj in enumerate(objects):
        if (guid and obj.get("__guid") == guid) or (name and obj.get("Name") == name):
            objects.pop(i)
            return True
        children = obj.get("Children", [])
        if children and _remove_from_list(children, name=name, guid=guid):
            return True
    return False


def _write_json(path: str, data: Dict[str, Any]) -> None:
    """Write data as formatted JSON to path."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_scene(
    name: str = "minimal",
    output_path: Optional[str] = None,
    fixed_update_freq: int = 50,
    network_freq: int = 60,
    include_defaults: bool = True,
) -> Dict[str, Any]:
    """Create a new .scene file.

    If *include_defaults* is True, adds Sun, Skybox, Plane, and Camera
    GameObjects to the scene.

    Returns the scene data dict.
    """
    game_objects: List[Dict[str, Any]] = []
    if include_defaults:
        game_objects = _build_default_objects()

    scene: Dict[str, Any] = {
        "GameObjects": game_objects,
        "SceneProperties": {
            "FixedUpdateFrequency": fixed_update_freq,
            "MaxFixedUpdates": 5,
            "NetworkFrequency": network_freq,
            "NetworkInterpolation": True,
            "PhysicsSubSteps": 1,
            "ThreadedAnimation": True,
            "TimeScale": 1,
            "UseFixedUpdate": True,
        },
        "Title": name,
        "Description": "",
        "ResourceVersion": 1,
        "__references": [],
        "__version": 1,
    }

    if output_path:
        _write_json(output_path, scene)

    return scene


def load_scene(scene_path: str) -> Dict[str, Any]:
    """Load and return parsed scene JSON."""
    with open(scene_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_scene(scene_path: str, data: Dict[str, Any]) -> None:
    """Save scene JSON with proper formatting."""
    _write_json(scene_path, data)


def get_scene_info(scene_path: str) -> Dict[str, Any]:
    """Return dict with scene metadata and object summary."""
    data = load_scene(scene_path)
    props = data.get("SceneProperties", {})
    objects = data.get("GameObjects", [])
    flat = _flatten_objects(objects)

    # Gather unique component types
    component_types: set = set()
    for obj in flat:
        for comp in obj.get("Components", []):
            ctype = comp.get("__type", "")
            if ctype:
                component_types.add(ctype)

    return {
        "title": data.get("Title", ""),
        "description": data.get("Description", ""),
        "path": scene_path,
        "fixed_update_freq": props.get("FixedUpdateFrequency"),
        "network_freq": props.get("NetworkFrequency"),
        "object_count": len(flat),
        "top_level_objects": len(objects),
        "component_types": sorted(component_types),
    }


def list_objects(scene_path: str) -> List[Dict[str, Any]]:
    """Return list of dicts with each GameObject's guid, name, position, component types."""
    data = load_scene(scene_path)
    flat = _flatten_objects(data.get("GameObjects", []))
    result: List[Dict[str, Any]] = []
    for obj in flat:
        comp_types = [c.get("__type", "") for c in obj.get("Components", []) if c.get("__type")]
        result.append({
            "guid": obj.get("__guid", ""),
            "name": obj.get("Name", ""),
            "position": obj.get("Position", "0,0,0"),
            "component_types": comp_types,
        })
    return result


def find_object(
    scene_data: Dict[str, Any],
    name: Optional[str] = None,
    guid: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find a GameObject by name or guid in scene data. Returns the object dict or None."""
    objects = scene_data.get("GameObjects", [])
    flat = _flatten_objects(objects)
    for obj in flat:
        if guid and obj.get("__guid") == guid:
            return obj
        if name and obj.get("Name") == name:
            return obj
    return None


def add_object(
    scene_path: str,
    name: str,
    position: str = "0,0,0",
    rotation: str = "0,0,0,1",
    scale: str = "1,1,1",
    tags: str = "",
    components: Optional[List[Dict[str, Any]]] = None,
    parent_guid: Optional[str] = None,
) -> str:
    """Add a new GameObject to the scene.

    *components* is a list of component dicts. Each dict should have at least
    a ``__type`` key, or be a preset name string that will be resolved via
    COMPONENT_PRESETS.

    If *parent_guid* is specified, adds the object as a child of that parent.

    Returns the new object's guid.
    """
    data = load_scene(scene_path)

    # Resolve component specs
    resolved_components: List[Dict[str, Any]] = []
    if components:
        for comp in components:
            if isinstance(comp, str):
                resolved_components.append(_make_component(comp))
            elif isinstance(comp, dict):
                c = dict(comp)
                if "__guid" not in c:
                    c["__guid"] = _new_guid()
                resolved_components.append(c)

    obj = _make_game_object(
        name=name,
        position=position,
        rotation=rotation,
        scale=scale,
        tags=tags,
        components=resolved_components,
    )
    new_guid = obj["__guid"]

    if parent_guid:
        parent = find_object(data, guid=parent_guid)
        if parent is None:
            raise ValueError(f"Parent object with guid '{parent_guid}' not found")
        parent.setdefault("Children", []).append(obj)
    else:
        data.setdefault("GameObjects", []).append(obj)

    save_scene(scene_path, data)
    return new_guid


def remove_object(
    scene_path: str,
    name: Optional[str] = None,
    guid: Optional[str] = None,
) -> bool:
    """Remove a GameObject by name or guid. Returns True if removed."""
    if not name and not guid:
        raise ValueError("Must specify either name or guid")

    data = load_scene(scene_path)
    objects = data.get("GameObjects", [])
    removed = _remove_from_list(objects, name=name, guid=guid)
    if removed:
        save_scene(scene_path, data)
    return removed


def add_component(
    scene_path: str,
    object_guid: str,
    component_type: str,
    properties: Optional[Dict[str, Any]] = None,
) -> str:
    """Add a component to a GameObject.

    *component_type* is either a preset name (e.g. ``"rigidbody"``) or a
    fully qualified type (e.g. ``"Sandbox.Rigidbody"``).

    *properties* is a dict of component properties to set/override.

    Returns the new component's guid.
    """
    data = load_scene(scene_path)
    obj = find_object(data, guid=object_guid)
    if obj is None:
        raise ValueError(f"GameObject with guid '{object_guid}' not found")

    comp = _make_component(component_type, properties)
    comp_guid = comp["__guid"]
    obj.setdefault("Components", []).append(comp)

    save_scene(scene_path, data)
    return comp_guid


def remove_component(
    scene_path: str,
    object_guid: str,
    component_guid: Optional[str] = None,
    component_type: Optional[str] = None,
) -> bool:
    """Remove a component from a GameObject by guid or type.

    Returns True if a component was removed.
    """
    if not component_guid and not component_type:
        raise ValueError("Must specify either component_guid or component_type")

    data = load_scene(scene_path)
    obj = find_object(data, guid=object_guid)
    if obj is None:
        raise ValueError(f"GameObject with guid '{object_guid}' not found")

    components = obj.get("Components", [])
    for i, comp in enumerate(components):
        if component_guid and comp.get("__guid") == component_guid:
            components.pop(i)
            save_scene(scene_path, data)
            return True
        if component_type and comp.get("__type") == component_type:
            components.pop(i)
            save_scene(scene_path, data)
            return True

    return False


def modify_object(
    scene_path: str,
    guid: Optional[str] = None,
    name_match: Optional[str] = None,
    new_name: Optional[str] = None,
    position: Optional[str] = None,
    rotation: Optional[str] = None,
    scale: Optional[str] = None,
    tags: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Modify properties of an existing GameObject in a scene.

    Finds the object by guid or name_match, then updates only the fields
    that are explicitly provided (non-None).

    Returns dict with guid, name, and list of modified_fields.
    Raises ValueError if object not found or no identifier given.
    """
    if guid is None and name_match is None:
        raise ValueError( "Must provide either guid or name_match to identify the object" )

    data = load_scene( scene_path )
    obj = find_object( data, name=name_match, guid=guid )
    if obj is None:
        identifier = guid or name_match
        raise ValueError( f"Object '{identifier}' not found in scene" )

    modified_fields = []

    if new_name is not None:
        obj["Name"] = new_name
        modified_fields.append( "Name" )
    if position is not None:
        obj["Position"] = position
        modified_fields.append( "Position" )
    if rotation is not None:
        obj["Rotation"] = rotation
        modified_fields.append( "Rotation" )
    if scale is not None:
        obj["Scale"] = scale
        modified_fields.append( "Scale" )
    if tags is not None:
        obj["Tags"] = tags
        modified_fields.append( "Tags" )
    if enabled is not None:
        obj["Enabled"] = enabled
        modified_fields.append( "Enabled" )

    save_scene( scene_path, data )

    return {
        "guid": obj["__guid"],
        "name": obj["Name"],
        "modified_fields": modified_fields,
    }


# Mapping from snake_case kwargs to SceneProperties JSON keys
_SCENE_PROPERTY_MAP: Dict[str, str] = {
    "fixed_update_freq": "FixedUpdateFrequency",
    "max_fixed_updates": "MaxFixedUpdates",
    "network_freq": "NetworkFrequency",
    "network_interpolation": "NetworkInterpolation",
    "physics_sub_steps": "PhysicsSubSteps",
    "threaded_animation": "ThreadedAnimation",
    "timescale": "TimeScale",
    "use_fixed_update": "UseFixedUpdate",
}


def set_scene_properties(
    scene_path: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Modify SceneProperties of a scene file.

    Accepts keyword arguments matching the keys in _SCENE_PROPERTY_MAP.
    Only updates properties that are explicitly provided.

    Returns the updated SceneProperties dict.
    """
    data = load_scene( scene_path )
    props = data.get( "SceneProperties", {} )

    updated = []
    for kwarg_key, value in kwargs.items():
        json_key = _SCENE_PROPERTY_MAP.get( kwarg_key )
        if json_key is None:
            raise ValueError( f"Unknown scene property: '{kwarg_key}'" )
        props[json_key] = value
        updated.append( json_key )

    data["SceneProperties"] = props
    save_scene( scene_path, data )

    return props


_NAVMESH_PROPERTY_MAP: Dict[str, str] = {
    "navmesh_enabled": "Enabled",
    "navmesh_include_static": "IncludeStaticBodies",
    "navmesh_include_keyframed": "IncludeKeyframedBodies",
    "navmesh_agent_height": "AgentHeight",
    "navmesh_agent_radius": "AgentRadius",
    "navmesh_agent_step_size": "AgentStepSize",
    "navmesh_agent_max_slope": "AgentMaxSlope",
}


def set_navmesh_properties(
    scene_path: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Modify NavMesh properties of a scene file.

    Accepts keyword arguments matching _NAVMESH_PROPERTY_MAP keys.
    Returns the updated NavMesh properties dict.
    """
    data = load_scene( scene_path )
    props = data.get( "SceneProperties", {} )
    navmesh = props.get( "NavMesh", {} )

    for kwarg_key, value in kwargs.items():
        json_key = _NAVMESH_PROPERTY_MAP.get( kwarg_key )
        if json_key is None:
            raise ValueError( f"Unknown navmesh property: '{kwarg_key}'" )
        navmesh[json_key] = value

    props["NavMesh"] = navmesh
    data["SceneProperties"] = props
    save_scene( scene_path, data )

    return navmesh


def modify_component(
    scene_path: str,
    object_guid: str,
    component_guid: Optional[str] = None,
    component_type: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Modify properties of an existing component on a GameObject.

    Finds the component by component_guid or component_type, then merges
    the provided properties onto it (only updates keys present in properties).

    Returns dict with object_guid, component_guid, component_type, and updated keys.
    Raises ValueError if object or component not found.
    """
    if component_guid is None and component_type is None:
        raise ValueError( "Must provide either component_guid or component_type" )
    if properties is None or len( properties ) == 0:
        raise ValueError( "No properties specified to modify" )

    data = load_scene( scene_path )
    obj = find_object( data, guid=object_guid )
    if obj is None:
        raise ValueError( f"Object '{object_guid}' not found in scene" )

    target_comp = None
    for comp in obj.get( "Components", [] ):
        if component_guid and comp.get( "__guid" ) == component_guid:
            target_comp = comp
            break
        if component_type and comp.get( "__type" ) == component_type:
            target_comp = comp
            break

    if target_comp is None:
        identifier = component_guid or component_type
        raise ValueError( f"Component '{identifier}' not found on object '{object_guid}'" )

    updated_keys = []
    for key, value in properties.items():
        target_comp[key] = value
        updated_keys.append( key )

    save_scene( scene_path, data )

    return {
        "object_guid": object_guid,
        "component_guid": target_comp.get( "__guid", "" ),
        "component_type": target_comp.get( "__type", "" ),
        "updated_keys": updated_keys,
    }


def clone_object(
    scene_path: str,
    guid: Optional[str] = None,
    name: Optional[str] = None,
    new_name: Optional[str] = None,
    position: Optional[str] = None,
) -> Dict[str, Any]:
    """Clone (duplicate) a GameObject in a scene.

    Finds the original by guid or name, deep-copies it with new GUIDs,
    optionally renames and repositions the clone.

    Returns dict with the new object's guid and name.
    """
    import copy

    data = load_scene( scene_path )
    original = find_object( data, name=name, guid=guid )
    if original is None:
        identifier = guid or name
        raise ValueError( f"Object '{identifier}' not found in scene" )

    clone = copy.deepcopy( original )

    # Regenerate all GUIDs in the clone
    _regenerate_guids( clone )

    if new_name is not None:
        clone["Name"] = new_name
    else:
        clone["Name"] = original["Name"] + " (Clone)"

    if position is not None:
        clone["Position"] = position

    # Add clone as top-level object
    data["GameObjects"].append( clone )
    save_scene( scene_path, data )

    return {
        "guid": clone["__guid"],
        "name": clone["Name"],
        "original_guid": original["__guid"],
        "original_name": original["Name"],
    }


def _regenerate_guids( obj: Dict[str, Any] ) -> None:
    """Recursively regenerate all __guid fields in an object and its children/components."""
    if "__guid" in obj:
        obj["__guid"] = _new_guid()
    for comp in obj.get( "Components", [] ):
        if "__guid" in comp:
            comp["__guid"] = _new_guid()
    for child in obj.get( "Children", [] ):
        _regenerate_guids( child )


def get_object(
    scene_path: str,
    guid: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get full details of a single GameObject.

    Returns dict with guid, name, position, rotation, scale, tags, enabled,
    components (list of type + properties), and children count.
    Raises ValueError if not found.
    """
    data = load_scene( scene_path )
    obj = find_object( data, name=name, guid=guid )
    if obj is None:
        identifier = guid or name
        raise ValueError( f"Object '{identifier}' not found in scene" )

    components = []
    for comp in obj.get( "Components", [] ):
        c = {"guid": comp.get( "__guid", "" ), "type": comp.get( "__type", "" )}
        # Include all non-internal properties
        for k, v in comp.items():
            if not k.startswith( "__" ):
                c[k] = v
        components.append( c )

    return {
        "guid": obj.get( "__guid", "" ),
        "name": obj.get( "Name", "" ),
        "position": obj.get( "Position", "0,0,0" ),
        "rotation": obj.get( "Rotation", "0,0,0,1" ),
        "scale": obj.get( "Scale", "1,1,1" ),
        "tags": obj.get( "Tags", "" ),
        "enabled": obj.get( "Enabled", True ),
        "components": components,
        "children_count": len( obj.get( "Children", [] ) ),
    }


# ---------------------------------------------------------------------------
# Query, asset-ref extraction, and bulk operations
# ---------------------------------------------------------------------------


def _resolve_component_type( component: str ) -> str:
    """Resolve a component preset name to its full Sandbox type, or pass through.

    Args:
        component: Either a preset key (e.g. "rigidbody") or a fully qualified
                   type (e.g. "Sandbox.Rigidbody" or "MyGame.MyComponent").

    Returns:
        The fully qualified type string.
    """
    if component in COMPONENT_PRESETS:
        return COMPONENT_PRESETS[component]["__type"]
    return component


def _object_has_component( obj: Dict[str, Any], component_type: str ) -> bool:
    """Check whether obj has any component matching component_type (exact match)."""
    for comp in obj.get( "Components", [] ):
        if comp.get( "__type" ) == component_type:
            return True
    return False


def _object_has_tag( obj: Dict[str, Any], tag: str ) -> bool:
    """Check whether the object's Tags string contains *tag* as a token."""
    raw = obj.get( "Tags", "" )
    if not raw:
        return False
    tokens = [t.strip() for t in raw.split( "," )]
    return tag in tokens


def _parse_position_bounds( bounds: str ) -> "tuple[tuple[float,float,float], tuple[float,float,float]]":
    """Parse a bounds string ``"x_min,y_min,z_min,x_max,y_max,z_max"`` into two tuples."""
    parts = [p.strip() for p in bounds.split( "," )]
    if len( parts ) != 6:
        raise ValueError( "bounds must be 6 comma-separated numbers: x_min,y_min,z_min,x_max,y_max,z_max" )
    nums = tuple( float( p ) for p in parts )
    return nums[:3], nums[3:]


def _object_in_bounds( obj: Dict[str, Any], bounds: str ) -> bool:
    """Check whether obj.Position lies inside the given AABB bounds string."""
    pos_str = obj.get( "Position", "0,0,0" )
    try:
        pos = tuple( float( p.strip() ) for p in pos_str.split( "," ) )
    except (ValueError, AttributeError):
        return False
    if len( pos ) != 3:
        return False
    lo, hi = _parse_position_bounds( bounds )
    return all( lo[i] <= pos[i] <= hi[i] for i in range( 3 ) )


def query_objects(
    scene_path: str,
    has_component: Optional[str] = None,
    has_tag: Optional[str] = None,
    name_match: Optional[str] = None,
    name_regex: Optional[str] = None,
    in_bounds: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Find GameObjects matching the given criteria.

    All provided filters are AND-combined. Searches all objects (top-level and
    nested children).  Component filter accepts either a preset key (e.g.
    ``"rigidbody"``) or a fully qualified type (e.g. ``"Sandbox.Rigidbody"``).

    Args:
        scene_path: Path to the .scene file.
        has_component: Match objects that have at least one component of this type.
        has_tag: Match objects whose Tags include this tag.
        name_match: Substring match on Name.
        name_regex: Regex pattern match on Name.
        in_bounds: AABB filter "x_min,y_min,z_min,x_max,y_max,z_max" on Position.
        enabled: If set, match only objects with this Enabled value.

    Returns:
        List of dicts with guid, name, position, tags, component_types.
    """
    import re

    data = load_scene( scene_path )
    flat = _flatten_objects( data.get( "GameObjects", [] ) )

    resolved_component = _resolve_component_type( has_component ) if has_component else None
    compiled_regex = re.compile( name_regex ) if name_regex else None

    results: List[Dict[str, Any]] = []
    for obj in flat:
        if resolved_component and not _object_has_component( obj, resolved_component ):
            continue
        if has_tag and not _object_has_tag( obj, has_tag ):
            continue
        if name_match and name_match not in obj.get( "Name", "" ):
            continue
        if compiled_regex and not compiled_regex.search( obj.get( "Name", "" ) ):
            continue
        if in_bounds and not _object_in_bounds( obj, in_bounds ):
            continue
        if enabled is not None and obj.get( "Enabled", True ) != enabled:
            continue

        comp_types = [c.get( "__type", "" ) for c in obj.get( "Components", [] ) if c.get( "__type" )]
        results.append( {
            "guid": obj.get( "__guid", "" ),
            "name": obj.get( "Name", "" ),
            "position": obj.get( "Position", "0,0,0" ),
            "tags": obj.get( "Tags", "" ),
            "component_types": comp_types,
        } )

    return results


# Asset-reference detection ----------------------------------------------------

# Engine asset extensions found in scene/prefab JSON string values.
ASSET_REF_EXTENSIONS = (
    ".vmdl",
    ".vmat",
    ".vsnd",
    ".sound",
    ".vtex",
    ".vpcf",
    ".prefab",
    ".scene",
    ".vanmgrph",
    ".animgraph",
    ".shader",
)

# Field names in component dicts whose string values are asset paths even if
# they don't end with a known extension (e.g. "models/dev/box" without .vmdl).
_ASSET_PATH_FIELDS = {
    "Model",
    "Material",
    "MaterialOverride",
    "SkyMaterial",
    "Texture",
    "Sound",
    "Prefab",
    "PrefabSource",
    "TargetPrefab",
}


def _is_asset_ref( value: str ) -> bool:
    """Return True if *value* looks like an asset path."""
    if not isinstance( value, str ) or not value:
        return False
    lower = value.lower()
    return any( lower.endswith( ext ) for ext in ASSET_REF_EXTENSIONS )


def _walk_for_refs( node: Any, refs: Dict[str, List[str]], path_stack: List[str] ) -> None:
    """Recursively walk a JSON tree, recording asset references by category.

    Each detected reference is stored under its asset-extension key, with the
    JSON breadcrumb path indicating where it was found.
    """
    if isinstance( node, dict ):
        for key, value in node.items():
            new_stack = path_stack + [str( key )]
            if isinstance( value, str ):
                hit = None
                if _is_asset_ref( value ):
                    hit = value
                elif key in _ASSET_PATH_FIELDS and value.strip():
                    hit = value
                if hit:
                    # Categorize by extension if present, else by field
                    category = _category_for_ref( hit, key )
                    refs.setdefault( category, [] ).append( hit )
            else:
                _walk_for_refs( value, refs, new_stack )
    elif isinstance( node, list ):
        for i, item in enumerate( node ):
            _walk_for_refs( item, refs, path_stack + [f"[{i}]"] )


def _category_for_ref( ref: str, field: str = "" ) -> str:
    """Map an asset reference to a category bucket."""
    lower = ref.lower()
    if lower.endswith( ".vmdl" ):
        return "models"
    if lower.endswith( ".vmat" ):
        return "materials"
    if lower.endswith( ".vsnd" ) or lower.endswith( ".sound" ):
        return "sounds"
    if lower.endswith( ".vtex" ):
        return "textures"
    if lower.endswith( ".vpcf" ):
        return "particles"
    if lower.endswith( ".prefab" ):
        return "prefabs"
    if lower.endswith( ".scene" ):
        return "scenes"
    if lower.endswith( ".animgraph" ) or lower.endswith( ".vanmgrph" ):
        return "animgraphs"
    if lower.endswith( ".shader" ):
        return "shaders"
    if field == "Model":
        return "models"
    if field in ( "Material", "MaterialOverride", "SkyMaterial" ):
        return "materials"
    if field == "Texture":
        return "textures"
    if field == "Sound":
        return "sounds"
    if field in ( "Prefab", "PrefabSource", "TargetPrefab" ):
        return "prefabs"
    return "other"


def extract_asset_refs( scene_path: str ) -> Dict[str, List[str]]:
    """Extract every asset reference from a scene file.

    Returns:
        Dict mapping category ("models", "materials", "sounds", "textures",
        "particles", "prefabs", "scenes", "animgraphs", "shaders", "other")
        to a sorted, deduplicated list of asset paths.
    """
    data = load_scene( scene_path )
    refs: Dict[str, List[str]] = {}
    _walk_for_refs( data.get( "GameObjects", [] ), refs, ["GameObjects"] )
    # Also walk SceneProperties (e.g. NavMesh references)
    if "SceneProperties" in data:
        _walk_for_refs( data["SceneProperties"], refs, ["SceneProperties"] )
    # Deduplicate and sort each category
    return {cat: sorted( set( paths ) ) for cat, paths in refs.items()}


def _object_summary( obj: Dict[str, Any] ) -> Dict[str, Any]:
    """Compress a GameObject dict to its comparable surface for diffing."""
    comps_by_type: Dict[str, Dict[str, Any]] = {}
    for comp in obj.get( "Components", [] ):
        ctype = comp.get( "__type", "" )
        if not ctype:
            continue
        # Strip internal keys, keep public properties
        stripped = {k: v for k, v in comp.items() if not k.startswith( "__" )}
        comps_by_type[ctype] = stripped

    return {
        "name": obj.get( "Name", "" ),
        "position": obj.get( "Position", "0,0,0" ),
        "rotation": obj.get( "Rotation", "0,0,0,1" ),
        "scale": obj.get( "Scale", "1,1,1" ),
        "tags": obj.get( "Tags", "" ),
        "enabled": obj.get( "Enabled", True ),
        "components": comps_by_type,
        "child_count": len( obj.get( "Children", [] ) ),
    }


def _diff_two_objects( name: str, a: Dict[str, Any], b: Dict[str, Any] ) -> Optional[Dict[str, Any]]:
    """Compare two object summaries and return the differences, or None if identical."""
    diffs: Dict[str, Any] = {}

    for field in ( "position", "rotation", "scale", "tags", "enabled", "child_count" ):
        if a.get( field ) != b.get( field ):
            diffs[field] = {"from": a.get( field ), "to": b.get( field )}

    a_comps = a.get( "components", {} )
    b_comps = b.get( "components", {} )
    a_types = set( a_comps.keys() )
    b_types = set( b_comps.keys() )

    added_comps = sorted( b_types - a_types )
    removed_comps = sorted( a_types - b_types )
    modified_comps: Dict[str, Dict[str, Any]] = {}

    for ctype in a_types & b_types:
        if a_comps[ctype] != b_comps[ctype]:
            keys_a = set( a_comps[ctype].keys() )
            keys_b = set( b_comps[ctype].keys() )
            field_changes: Dict[str, Any] = {}
            for k in (keys_a | keys_b):
                va, vb = a_comps[ctype].get( k ), b_comps[ctype].get( k )
                if va != vb:
                    field_changes[k] = {"from": va, "to": vb}
            if field_changes:
                modified_comps[ctype] = field_changes

    if added_comps:
        diffs["components_added"] = added_comps
    if removed_comps:
        diffs["components_removed"] = removed_comps
    if modified_comps:
        diffs["components_modified"] = modified_comps

    if not diffs:
        return None
    return {"name": name, "changes": diffs}


def diff_scenes( scene_a_path: str, scene_b_path: str ) -> Dict[str, Any]:
    """Structural diff between two scene files.

    Compares by GameObject Name (not GUID, since GUIDs differ across branches).
    Reports objects added in B, removed from B (that were in A), and objects
    whose summary or components differ.

    Returns:
        Dict with 'added' (list of names), 'removed' (list of names),
        'modified' (list of {name, changes}), 'identical' (bool), and
        'scene_property_changes' (dict of changed SceneProperties keys).
    """
    data_a = load_scene( scene_a_path )
    data_b = load_scene( scene_b_path )

    flat_a = _flatten_objects( data_a.get( "GameObjects", [] ) )
    flat_b = _flatten_objects( data_b.get( "GameObjects", [] ) )

    summary_a = {obj.get( "Name", f"<unnamed:{i}>" ): _object_summary( obj ) for i, obj in enumerate( flat_a )}
    summary_b = {obj.get( "Name", f"<unnamed:{i}>" ): _object_summary( obj ) for i, obj in enumerate( flat_b )}

    names_a = set( summary_a.keys() )
    names_b = set( summary_b.keys() )

    added = sorted( names_b - names_a )
    removed = sorted( names_a - names_b )
    modified: List[Dict[str, Any]] = []
    for name in sorted( names_a & names_b ):
        d = _diff_two_objects( name, summary_a[name], summary_b[name] )
        if d:
            modified.append( d )

    # Scene properties diff
    props_a = data_a.get( "SceneProperties", {} ) or {}
    props_b = data_b.get( "SceneProperties", {} ) or {}
    sp_changes: Dict[str, Any] = {}
    for k in set( props_a.keys() ) | set( props_b.keys() ):
        if props_a.get( k ) != props_b.get( k ):
            sp_changes[k] = {"from": props_a.get( k ), "to": props_b.get( k )}

    identical = not (added or removed or modified or sp_changes)
    return {
        "scene_a": scene_a_path,
        "scene_b": scene_b_path,
        "added": added,
        "removed": removed,
        "modified": modified,
        "scene_property_changes": sp_changes,
        "identical": identical,
    }


def instantiate_prefab(
    scene_path: str,
    prefab_path: str,
    name: Optional[str] = None,
    position: str = "0,0,0",
    rotation: str = "0,0,0,1",
    scale: str = "1,1,1",
    parent_guid: Optional[str] = None,
) -> str:
    """Insert a prefab reference into a scene as a new GameObject.

    Reads the prefab to derive a default name (from RootObject.Name) and
    creates a GameObject in the scene with a PrefabSource reference, fresh
    GUIDs, and the given transform.  The prefab is referenced (not deep-copied
    or "exploded").

    Args:
        scene_path: Path to the .scene file to mutate.
        prefab_path: Path to the .prefab file to instantiate. Stored as a
                     relative-to-Assets reference if it lives under Assets/.
        name: Optional override for the new GameObject's Name. Defaults to
              the prefab RootObject's Name.
        position, rotation, scale: Transform of the new object.
        parent_guid: Optional parent GameObject guid (otherwise added at root).

    Returns:
        The new GameObject's guid.
    """
    # Load the prefab to extract its name
    with open( prefab_path, "r", encoding="utf-8" ) as f:
        prefab_data = json.load( f )

    root = prefab_data.get( "RootObject", {} )
    default_name = root.get( "Name", os.path.splitext( os.path.basename( prefab_path ) )[0] )
    obj_name = name if name is not None else default_name

    # Compute a project-relative reference for PrefabSource
    abs_prefab = os.path.abspath( prefab_path )
    prefab_ref = abs_prefab.replace( "\\", "/" )
    norm_lower = prefab_ref.lower()
    if "/assets/" in norm_lower:
        idx = norm_lower.rindex( "/assets/" )
        prefab_ref = prefab_ref[idx + len( "/assets/" ):]

    data = load_scene( scene_path )

    # Build the GameObject with a PrefabSource pointer
    new_obj: Dict[str, Any] = {
        "__guid": _new_guid(),
        "Flags": 0,
        "Name": obj_name,
        "Enabled": True,
        "Position": position,
        "Rotation": rotation,
        "Scale": scale,
        "Tags": "",
        "PrefabSource": prefab_ref,
        "Components": [],
        "Children": [],
    }

    if parent_guid:
        parent = find_object( data, guid=parent_guid )
        if parent is None:
            raise ValueError( f"Parent object with guid '{parent_guid}' not found" )
        parent.setdefault( "Children", [] ).append( new_obj )
    else:
        data.setdefault( "GameObjects", [] ).append( new_obj )

    save_scene( scene_path, data )
    return new_obj["__guid"]


def bulk_modify_objects(
    scene_path: str,
    has_component: Optional[str] = None,
    has_tag: Optional[str] = None,
    name_match: Optional[str] = None,
    name_regex: Optional[str] = None,
    in_bounds: Optional[str] = None,
    enabled_filter: Optional[bool] = None,
    new_position: Optional[str] = None,
    new_rotation: Optional[str] = None,
    new_scale: Optional[str] = None,
    new_tags: Optional[str] = None,
    new_enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Apply the same modification to every GameObject matching the filters.

    Reads the scene once, runs the query, mutates each match in place, and
    writes the scene back. At least one ``new_*`` value must be provided.

    Returns:
        Dict with ``modified_count``, ``modified_fields``, and ``modified_guids``.
    """
    update_fields = {
        "Position": new_position,
        "Rotation": new_rotation,
        "Scale": new_scale,
        "Tags": new_tags,
        "Enabled": new_enabled,
    }
    active_updates = {k: v for k, v in update_fields.items() if v is not None}
    if not active_updates:
        raise ValueError( "Must provide at least one modification (new_position, new_rotation, etc.)" )

    matches = query_objects(
        scene_path,
        has_component=has_component,
        has_tag=has_tag,
        name_match=name_match,
        name_regex=name_regex,
        in_bounds=in_bounds,
        enabled=enabled_filter,
    )

    if not matches:
        return {
            "modified_count": 0,
            "modified_fields": list( active_updates.keys() ),
            "modified_guids": [],
        }

    data = load_scene( scene_path )
    flat = _flatten_objects( data.get( "GameObjects", [] ) )
    by_guid = {obj.get( "__guid" ): obj for obj in flat}

    modified_guids: List[str] = []
    for match in matches:
        guid = match["guid"]
        obj = by_guid.get( guid )
        if obj is None:
            continue
        for key, value in active_updates.items():
            obj[key] = value
        modified_guids.append( guid )

    save_scene( scene_path, data )

    return {
        "modified_count": len( modified_guids ),
        "modified_fields": list( active_updates.keys() ),
        "modified_guids": modified_guids,
    }
