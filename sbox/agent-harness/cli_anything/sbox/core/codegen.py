"""C# code generation following s&box engine conventions.

Generates component classes, GameResource classes, and editor menu classes
with proper s&box code style: Allman braces, tab indentation, spaces inside
parentheses, and correct attribute usage.
"""

from typing import Optional


def generate_component(
    class_name: str,
    properties: Optional[list[dict]] = None,
    lifecycle_methods: Optional[list[str]] = None,
    interfaces: Optional[list[str]] = None,
    is_networked: bool = False,
    namespace: Optional[str] = None,
    rpc_methods: Optional[list[dict]] = None,
) -> dict:
    """Generate a C# component class file.

    Args:
        class_name: PascalCase name, e.g. "PlayerController".
        properties: List of dicts with keys:
            name (str), type (str), default (str|None),
            category (str|None), range_min (float|None), range_max (float|None).
            Type examples: "float", "int", "string", "GameObject", "Vector3", "Model".
        lifecycle_methods: Method names to override, e.g. ["OnUpdate", "OnFixedUpdate", "OnStart"].
        interfaces: Interface list, e.g. ["Component.ITriggerListener", "Component.IDamageable"].
        is_networked: If True the class is partial (not sealed) and properties get [Sync].
        namespace: Optional namespace wrapper.
        rpc_methods: List of dicts with 'name' (str) and 'type' (str: 'Broadcast',
            'Host', or 'Owner'). Forces is_networked=True when provided.

    Returns:
        Dict with keys: filename, content, class_name.
    """
    properties = properties or []
    lifecycle_methods = lifecycle_methods or []
    interfaces = interfaces or []
    rpc_methods = rpc_methods or []

    # RPC methods require networking support
    if rpc_methods:
        is_networked = True

    lines: list[str] = []
    lines.append( "using Sandbox;" )
    lines.append( "" )

    # Namespace open
    if namespace:
        lines.append( f"namespace {namespace}" )
        lines.append( "{" )

    indent = "\t" if namespace else ""

    # Class declaration
    modifier = "partial" if is_networked else "sealed"
    base_parts = ["Component"] + interfaces
    base = ", ".join( base_parts )
    lines.append( f"{indent}public {modifier} class {class_name} : {base}" )
    lines.append( f"{indent}{{" )

    # Properties
    for prop in properties:
        prop_str = _format_property( prop, is_networked=is_networked )
        for pline in prop_str.split( "\n" ):
            lines.append( f"{indent}\t{pline}" )

    # Blank line between properties and methods
    if properties and lifecycle_methods:
        lines.append( "" )

    # Lifecycle methods
    for i, method_name in enumerate( lifecycle_methods ):
        body = ""
        if is_networked and method_name == "OnFixedUpdate":
            body = "if ( IsProxy ) return;"
        method_str = _format_method( method_name, body=body )
        for mline in method_str.split( "\n" ):
            lines.append( f"{indent}\t{mline}" )
        if i < len( lifecycle_methods ) - 1:
            lines.append( "" )

    # RPC method stubs
    if rpc_methods:
        if lifecycle_methods:
            lines.append( "" )
        for j, rpc in enumerate( rpc_methods ):
            rpc_str = _format_rpc_method( rpc )
            for rline in rpc_str.split( "\n" ):
                lines.append( f"{indent}\t{rline}" )
            if j < len( rpc_methods ) - 1:
                lines.append( "" )

    lines.append( f"{indent}}}" )

    # Namespace close
    if namespace:
        lines.append( "}" )

    lines.append( "" )
    content = "\r\n".join( lines )

    return {
        "filename": f"{class_name}.cs",
        "content": content,
        "class_name": class_name,
    }


def generate_gameresource(
    class_name: str,
    display_name: str,
    extension: str,
    description: str = "",
    properties: Optional[list[dict]] = None,
    namespace: Optional[str] = None,
) -> dict:
    """Generate a GameResource class.

    Args:
        class_name: PascalCase name, e.g. "TowerData".
        display_name: Human-readable name shown in editor, e.g. "Tower Data".
        extension: File extension for the resource, e.g. "tower".
        description: Short description of the resource.
        properties: List of property dicts (same format as generate_component).
        namespace: Optional namespace wrapper.

    Returns:
        Dict with keys: filename, content, class_name.
    """
    properties = properties or []

    lines: list[str] = []
    lines.append( "using Sandbox;" )
    lines.append( "" )

    if namespace:
        lines.append( f"namespace {namespace}" )
        lines.append( "{" )

    indent = "\t" if namespace else ""

    # GameResource attribute
    lines.append( f'{indent}[GameResource( "{display_name}", "{extension}", "{description}" )]' )
    lines.append( f"{indent}public class {class_name} : GameResource" )
    lines.append( f"{indent}{{" )

    for prop in properties:
        prop_str = _format_property( prop, is_networked=False )
        for pline in prop_str.split( "\n" ):
            lines.append( f"{indent}\t{pline}" )

    lines.append( f"{indent}}}" )

    if namespace:
        lines.append( "}" )

    lines.append( "" )
    content = "\r\n".join( lines )

    return {
        "filename": f"{class_name}.cs",
        "content": content,
        "class_name": class_name,
    }


def generate_editor_menu(
    class_name: str,
    menu_path: str,
    method_name: str = "OpenMenu",
    dialog_title: str = "",
    dialog_message: str = "",
) -> dict:
    """Generate an editor menu class.

    Args:
        class_name: PascalCase name, e.g. "MyEditorTool".
        menu_path: Menu path string, e.g. "Tools/My Tool".
        method_name: Name of the static method, default "OpenMenu".
        dialog_title: Title for the editor dialog (optional).
        dialog_message: Message for the editor dialog (optional).

    Returns:
        Dict with keys: filename, content, class_name.
    """
    lines: list[str] = []
    lines.append( "using Editor;" )
    lines.append( "using Sandbox;" )
    lines.append( "" )

    lines.append( f"public static class {class_name}" )
    lines.append( "{" )

    lines.append( f'\t[Menu( "Editor", "{menu_path}" )]' )
    lines.append( f"\tpublic static void {method_name}()" )
    lines.append( "\t{" )

    if dialog_title or dialog_message:
        title = dialog_title or class_name
        message = dialog_message or ""
        lines.append( f'\t\tEditorUtility.DisplayDialog( "{title}", "{message}" );' )
    else:
        lines.append( f'\t\tLog.Info( "{class_name}.{method_name} invoked" );' )

    lines.append( "\t}" )
    lines.append( "}" )
    lines.append( "" )
    content = "\r\n".join( lines )

    return {
        "filename": f"{class_name}.cs",
        "content": content,
        "class_name": class_name,
    }


def generate_razor(
    class_name: str,
    inherits: str = "PanelComponent",
    properties: Optional[list[dict]] = None,
    root_class: Optional[str] = None,
    namespace: Optional[str] = None,
) -> dict:
    """Generate a Razor UI component (.razor) and its stylesheet (.razor.scss).

    Args:
        class_name: PascalCase name, e.g. "HudPanel".
        inherits: Base class - "PanelComponent", "Panel", etc.
        properties: List of property dicts with 'name' and 'type' keys.
        root_class: CSS class for root element. Defaults to kebab-case of class_name.
        namespace: Optional namespace.

    Returns:
        Dict with filename, content, class_name, scss_filename, scss_content.
    """
    if properties is None:
        properties = []
    if root_class is None:
        # Convert PascalCase to kebab-case
        import re
        root_class = re.sub( r"(?<!^)(?=[A-Z])", "-", class_name ).lower()

    # Build .razor content
    lines = []
    lines.append( "@using Sandbox;" )
    lines.append( "@using Sandbox.UI;" )
    if namespace:
        lines.append( f"@namespace {namespace}" )
    lines.append( f"@inherits {inherits}" )
    lines.append( "" )
    lines.append( f'<root class="{root_class}">' )
    lines.append( '\t<div class="content">' )
    lines.append( "\t</div>" )
    lines.append( "</root>" )
    lines.append( "" )
    lines.append( "@code" )
    lines.append( "{" )

    # Properties
    for prop in properties:
        pname = prop.get( "name", "MyProperty" )
        ptype = prop.get( "type", "string" )
        pdefault = prop.get( "default", None )
        default_str = f" = {pdefault};" if pdefault is not None else ";"
        lines.append( f"\t[Property] public {ptype} {pname} {{ get; set; }}{default_str}" )

    if properties:
        lines.append( "" )

    # BuildHash
    if properties:
        prop_names = [p.get( "name", "MyProperty" ) for p in properties]
        # System.HashCode.Combine supports up to 8 args
        if len( prop_names ) <= 8:
            hash_args = ", ".join( prop_names )
            lines.append( f"\tprotected override int BuildHash() => System.HashCode.Combine( {hash_args} );" )
        else:
            # Chain for more than 8
            lines.append( "\tprotected override int BuildHash()" )
            lines.append( "\t{" )
            lines.append( "\t\tvar hash = new System.HashCode();" )
            for pname in prop_names:
                lines.append( f"\t\thash.Add( {pname} );" )
            lines.append( "\t\treturn hash.ToHashCode();" )
            lines.append( "\t}" )

    lines.append( "}" )
    lines.append( "" )

    content = "\r\n".join( lines )

    # Build .razor.scss content
    scss_lines = []
    scss_lines.append( f".{root_class}" )
    scss_lines.append( "{" )
    scss_lines.append( "\tposition: absolute;" )
    scss_lines.append( "\twidth: 100%;" )
    scss_lines.append( "\theight: 100%;" )
    scss_lines.append( "\tpointer-events: none;" )
    scss_lines.append( "" )
    scss_lines.append( "\t> .content" )
    scss_lines.append( "\t{" )
    scss_lines.append( "\t\tflex-direction: column;" )
    scss_lines.append( "\t}" )
    scss_lines.append( "}" )
    scss_lines.append( "" )

    scss_content = "\r\n".join( scss_lines )

    razor_filename = f"{class_name}.razor"
    scss_filename = f"{class_name}.razor.scss"

    return {
        "filename": razor_filename,
        "content": content,
        "class_name": class_name,
        "scss_filename": scss_filename,
        "scss_content": scss_content,
    }


def _format_property( prop: dict, is_networked: bool = False ) -> str:
    """Format a single C# property with attributes.

    Args:
        prop: Dict with keys: name, type, and optionally default, category,
              range_min, range_max.
        is_networked: If True, adds [Sync] attribute before [Property].

    Returns:
        Multi-line string (no leading/trailing blank lines) with the
        attribute(s) and auto-property declaration.
    """
    name: str = prop["name"]
    prop_type: str = prop["type"]
    default = prop.get( "default" )
    category = prop.get( "category" )
    range_min = prop.get( "range_min" )
    range_max = prop.get( "range_max" )

    lines: list[str] = []

    # Sync attribute for networked properties (always on its own line)
    # NetList and NetDictionary are self-syncing - skip [Sync] for them
    if is_networked and not prop_type.startswith( "NetList<" ) and not prop_type.startswith( "NetDictionary<" ):
        lines.append( "[Sync]" )

    # Property attribute with optional modifiers
    attr_inner_parts: list[str] = []
    if category:
        attr_inner_parts.append( f'Category = "{category}"' )
    if range_min is not None and range_max is not None:
        attr_inner_parts.append( f"MinMax( {range_min}, {range_max} )" )

    has_extra_attrs = bool( attr_inner_parts )

    if has_extra_attrs:
        attr_inner = ", ".join( attr_inner_parts )
        prop_attr = f"[Property( {attr_inner} )]"
    else:
        prop_attr = "[Property]"

    # Build the property declaration
    default_str = ""
    if default is not None:
        default_str = f" = {default};"

    decl = f"public {prop_type} {name} {{ get; set; }}{default_str}"

    # Simple properties: attribute and declaration on one line
    # Complex properties (extra attrs or networked): attribute on separate line
    if is_networked or has_extra_attrs:
        lines.append( prop_attr )
        lines.append( decl )
    else:
        lines.append( f"{prop_attr} {decl}" )

    return "\n".join( lines )


def _format_method(
    name: str,
    body: str = "",
    params: str = "",
    return_type: str = "void",
    is_override: bool = True,
) -> str:
    """Format a C# method with proper s&box style.

    Args:
        name: Method name, e.g. "OnUpdate".
        body: Method body lines (newline-separated). Empty string for empty body.
        params: Parameter list string, e.g. "float delta, int count".
        return_type: Return type, default "void".
        is_override: If True, uses "protected override" modifier.

    Returns:
        Multi-line string with the full method definition using Allman braces.
    """
    modifier = "protected override" if is_override else "public"
    signature = f"{modifier} {return_type} {name}( {params} )" if params else f"{modifier} {return_type} {name}()"

    lines: list[str] = []
    lines.append( signature )
    lines.append( "{" )

    if body:
        for bline in body.split( "\n" ):
            lines.append( f"\t{bline}" )

    lines.append( "}" )

    return "\n".join( lines )


def _format_rpc_method( rpc: dict ) -> str:
    """Format an RPC method stub with the appropriate attribute.

    Args:
        rpc: Dict with 'name' (str) and 'type' (str: 'Broadcast', 'Host', or 'Owner').
    """
    rpc_type = rpc.get( "type", "Broadcast" )
    name = rpc.get( "name", "RpcMethod" )

    attr = f"[Rpc.{rpc_type}]"
    lines = []
    lines.append( f"{attr}" )
    lines.append( f"public void {name}()" )
    lines.append( "{" )
    lines.append( "}" )
    return "\n".join( lines )


def generate_panel_component(
    class_name: str,
    properties: Optional[list[dict]] = None,
    namespace: Optional[str] = None,
    z_index: int = 100,
    opacity: float = 1.0,
    root_class: Optional[str] = None,
) -> dict:
    """Scaffold a Razor PanelComponent intended to live on the same GameObject
    as a ScreenPanel.

    s&box quirk (see project CLAUDE.md): ``PanelComponent`` input only works
    when both ``ScreenPanel`` and the ``PanelComponent`` are on the same
    ``GameObject``. This generator emits the .razor + .razor.scss pair *and*
    a ready-to-paste partial scene snippet that wires both components onto the
    same GameObject with the correct GUIDs.

    Args:
        class_name: PascalCase name, e.g. "HudPanel".
        properties: Optional list of [Property] dicts (same shape as generate_razor).
        namespace: Optional namespace for the .razor.
        z_index: ScreenPanel ZIndex value (defaults to 100).
        opacity: ScreenPanel Opacity (defaults to 1.0).
        root_class: CSS class for root element (defaults to kebab-case).

    Returns:
        Dict with: filename, content, scss_filename, scss_content,
        scene_snippet (str - ready-to-paste GameObject JSON), class_name.
    """
    import json as _json
    import uuid as _uuid

    razor = generate_razor(
        class_name=class_name,
        inherits="PanelComponent",
        properties=properties,
        root_class=root_class,
        namespace=namespace,
    )

    screen_panel_guid = str( _uuid.uuid4() )
    panel_comp_guid = str( _uuid.uuid4() )
    object_guid = str( _uuid.uuid4() )
    type_name = f"{namespace}.{class_name}" if namespace else class_name

    snippet_obj = {
        "__guid": object_guid,
        "Flags": 0,
        "Name": class_name,
        "Enabled": True,
        "Position": "0,0,0",
        "Rotation": "0,0,0,1",
        "Scale": "1,1,1",
        "Tags": "",
        "Components": [
            {
                "__guid": screen_panel_guid,
                "__type": "Sandbox.ScreenPanel",
                "ZIndex": z_index,
                "Opacity": opacity,
            },
            {
                "__guid": panel_comp_guid,
                "__type": type_name,
            },
        ],
        "Children": [],
    }
    scene_snippet = _json.dumps( snippet_obj, indent=2 )

    return {
        "filename": razor["filename"],
        "content": razor["content"],
        "scss_filename": razor["scss_filename"],
        "scss_content": razor["scss_content"],
        "scene_snippet": scene_snippet,
        "class_name": class_name,
        "screen_panel_guid": screen_panel_guid,
        "panel_component_guid": panel_comp_guid,
        "object_guid": object_guid,
    }


def generate_class(
    class_name: str,
    base_class: Optional[str] = None,
    is_static: bool = False,
    properties: Optional[list[dict]] = None,
    methods: Optional[list[dict]] = None,
    namespace: Optional[str] = None,
) -> dict:
    """Generate a plain C# class (not a Component subclass).

    Args:
        class_name: PascalCase name.
        base_class: Optional base class to inherit from.
        is_static: If True, generates a static class (no instantiation).
        properties: List of dicts with name, type, default keys.
        methods: List of dicts with name, return_type, params, body, is_static keys.
        namespace: Optional namespace wrapper.

    Returns:
        Dict with filename, content, class_name.
    """
    if properties is None:
        properties = []
    if methods is None:
        methods = []

    lines = []
    lines.append( "using Sandbox;" )
    lines.append( "" )

    indent = ""
    if namespace:
        lines.append( f"namespace {namespace}" )
        lines.append( "{" )
        indent = "\t"

    # Class declaration
    static_kw = "static " if is_static else ""
    if base_class:
        lines.append( f"{indent}public {static_kw}class {class_name} : {base_class}" )
    else:
        lines.append( f"{indent}public {static_kw}class {class_name}" )
    lines.append( f"{indent}{{" )

    # Properties
    for prop in properties:
        pname = prop.get( "name", "MyProperty" )
        ptype = prop.get( "type", "string" )
        pdefault = prop.get( "default", None )
        static_prop = "static " if is_static else ""
        if pdefault is not None:
            lines.append( f"{indent}\tpublic {static_prop}{ptype} {pname} {{ get; set; }} = {pdefault};" )
        else:
            lines.append( f"{indent}\tpublic {static_prop}{ptype} {pname} {{ get; set; }}" )

    if properties and methods:
        lines.append( "" )

    # Methods
    for method in methods:
        mname = method.get( "name", "DoSomething" )
        mreturn = method.get( "return_type", "void" )
        mparams = method.get( "params", "" )
        mbody = method.get( "body", "" )
        mstatic = "static " if method.get( "is_static", is_static ) else ""
        lines.append( f"{indent}\tpublic {mstatic}{mreturn} {mname}( {mparams} )" )
        lines.append( f"{indent}\t{{" )
        if mbody:
            for bline in mbody.split( "\n" ):
                lines.append( f"{indent}\t\t{bline}" )
        lines.append( f"{indent}\t}}" )

    lines.append( f"{indent}}}" )

    if namespace:
        lines.append( "}" )

    lines.append( "" )

    content = "\r\n".join( lines )

    return {
        "filename": f"{class_name}.cs",
        "content": content,
        "class_name": class_name,
    }
