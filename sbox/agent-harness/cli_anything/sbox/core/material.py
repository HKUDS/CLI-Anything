"""Manages s&box .vmat material files - creation, parsing, and listing."""

import os
from typing import Any, Dict, List, Optional


SHADER_MAP: Dict[str, str] = {
    "complex": "shaders/complex.vfx",
    "simple": "shaders/simple.vfx",
    "unlit": "shaders/unlit.vfx",
    "blendable": "shaders/blendable.vfx",
    "glass": "shaders/glass.vfx",
}


def create_material(
    name: str,
    shader: str = "complex",
    color_texture: Optional[str] = None,
    normal_texture: Optional[str] = None,
    roughness_texture: Optional[str] = None,
    metalness: float = 0.0,
    tint: str = "1 1 1 0",
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a .vmat material file.

    Args:
        name: Material name (used for filename if output_path not given).
        shader: Shader name - key from SHADER_MAP or full path.
        color_texture: Path to color/albedo texture.
        normal_texture: Path to normal map texture.
        roughness_texture: Path to roughness texture.
        metalness: Metalness value (0.0 to 1.0).
        tint: Color tint as "r g b a" (space-separated).
        output_path: Output file path. If None, returns content only.

    Returns:
        Dict with name, path, shader, content.
    """
    shader_path = SHADER_MAP.get(shader, shader)

    lines = []
    lines.append("// THIS FILE IS AUTO-GENERATED")
    lines.append("")
    lines.append("Layer0")
    lines.append("{")
    lines.append(f'\tshader "{shader_path}"')
    lines.append("")
    lines.append("\t//---- PBR ----")

    if color_texture:
        lines.append(f'\tTextureColor "{color_texture}"')
    if normal_texture:
        lines.append(f'\tTextureNormal "{normal_texture}"')
    if roughness_texture:
        lines.append(f'\tTextureRoughness "{roughness_texture}"')

    lines.append(f'\tg_flMetalness "{metalness}"')
    lines.append(f'\tg_vColorTint "[{tint}]"')
    lines.append("}")
    lines.append("")

    content = "\n".join(lines)

    result = {
        "name": name,
        "shader": shader_path,
        "content": content,
    }

    if output_path:
        if not output_path.endswith(".vmat"):
            output_path += ".vmat"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        result["path"] = os.path.abspath(output_path)

    return result


def parse_material(material_path: str) -> Dict[str, Any]:
    """Parse a .vmat material file and return its properties.

    Returns dict with name, path, shader, and properties dict.
    """
    with open(material_path, "r", encoding="utf-8") as f:
        text = f.read()

    properties = {}
    shader = None

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line in ("{", "}", "Layer0"):
            continue

        # Parse key "value" format
        parts = line.split('"', 2)
        if len(parts) >= 3:
            key = parts[0].strip()
            value = parts[1]
            if key == "shader":
                shader = value
            else:
                properties[key] = value

    name = os.path.splitext(os.path.basename(material_path))[0]

    return {
        "name": name,
        "path": os.path.abspath(material_path),
        "shader": shader,
        "properties": properties,
    }


def update_material(
    material_path: str,
    shader: Optional[str] = None,
    color_texture: Optional[str] = None,
    normal_texture: Optional[str] = None,
    roughness_texture: Optional[str] = None,
    metalness: Optional[float] = None,
    tint: Optional[str] = None,
) -> Dict[str, Any]:
    """Update properties of an existing .vmat material file.

    Only modifies properties that are explicitly provided (non-None).
    Returns the updated material info dict.
    """
    info = parse_material( material_path )
    old_shader = info["shader"]
    old_props = info["properties"]

    new_shader = SHADER_MAP.get( shader, shader ) if shader is not None else old_shader

    ct = color_texture if color_texture is not None else old_props.get( "TextureColor" )
    nt = normal_texture if normal_texture is not None else old_props.get( "TextureNormal" )
    rt = roughness_texture if roughness_texture is not None else old_props.get( "TextureRoughness" )
    mt = str( metalness ) if metalness is not None else old_props.get( "g_flMetalness", "0.0" )
    ti = tint if tint is not None else old_props.get( "g_vColorTint", "[1 1 1 0]" ).strip( "[]" )

    lines = []
    lines.append( "// THIS FILE IS AUTO-GENERATED" )
    lines.append( "" )
    lines.append( "Layer0" )
    lines.append( "{" )
    lines.append( f'\tshader "{new_shader}"' )
    lines.append( "" )
    lines.append( "\t//---- PBR ----" )
    if ct:
        lines.append( f'\tTextureColor "{ct}"' )
    if nt:
        lines.append( f'\tTextureNormal "{nt}"' )
    if rt:
        lines.append( f'\tTextureRoughness "{rt}"' )
    lines.append( f'\tg_flMetalness "{mt}"' )
    lines.append( f'\tg_vColorTint "[{ti}]"' )
    lines.append( "}" )
    lines.append( "" )

    with open( material_path, "w", encoding="utf-8" ) as f:
        f.write( "\n".join( lines ) )

    return parse_material( material_path )


def list_materials(project_dir: str) -> List[Dict[str, Any]]:
    """List all .vmat files in a project's Assets/ directory.

    Returns list of dicts with name, path, size_bytes.
    """
    assets_dir = os.path.join(project_dir, "Assets")
    if not os.path.isdir(assets_dir):
        assets_dir = project_dir

    materials = []
    for root, _dirs, files in os.walk(assets_dir):
        for fname in sorted(files):
            if fname.endswith(".vmat"):
                full_path = os.path.join(root, fname)
                materials.append({
                    "name": os.path.splitext(fname)[0],
                    "path": os.path.abspath(full_path),
                    "size_bytes": os.path.getsize(full_path),
                })

    return materials
