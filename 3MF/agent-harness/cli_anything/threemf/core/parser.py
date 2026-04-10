"""3MF file parsing and writing -- handles ZIP structure and XML mesh data.

A 3MF file is a standard ZIP archive that contains one or more XML files
describing 3D mesh objects.  The primary model is typically located at
``3D/3dmodel.model``.  This module provides lossless round-trip support:
non-model entries (thumbnails, slicer profiles, Bambu metadata, etc.) are
preserved byte-for-byte.
"""

from __future__ import annotations

import io
import os
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NS_CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_BAMBU = "http://schemas.bambulab.com/package/2021"

# Common namespace prefixes found in 3MF files -- we register them so that
# ElementTree preserves them when serialising instead of inventing ``ns0``
# etc.
_KNOWN_NS: dict[str, str] = {
    "": NS_CORE,
    "b": NS_BAMBU,
}

# Ensure ElementTree will use the prefixes above when writing.
for _prefix, _uri in _KNOWN_NS.items():
    ET.register_namespace(_prefix, _uri)


def _tag(local: str, ns: str = NS_CORE) -> str:
    """Return a fully-qualified ``{namespace}local`` tag string."""
    return f"{{{ns}}}{local}"


# ---------------------------------------------------------------------------
# Data classes (frozen / immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MeshData:
    """Immutable container for a single mesh object.

    Attributes:
        object_id: The ``id`` attribute of the ``<object>`` element.
        name:      The ``name`` attribute (may be empty).
        vertices:  (N, 3) float64 array of vertex coordinates.
        triangles: (M, 3) int32 array of triangle vertex-indices.
    """

    object_id: str
    name: str
    vertices: np.ndarray  # (N, 3) float64
    triangles: np.ndarray  # (M, 3) int32

    def __post_init__(self) -> None:
        # Validate shapes -- run only once at construction time.
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError(
                f"vertices must be (N, 3); got {self.vertices.shape}"
            )
        if self.triangles.ndim != 2 or self.triangles.shape[1] != 3:
            raise ValueError(
                f"triangles must be (M, 3); got {self.triangles.shape}"
            )


@dataclass(frozen=True)
class ThreeMFData:
    """Immutable container for a complete 3MF file.

    Attributes:
        meshes:      Tuple of :class:`MeshData` objects.
        unit:        Model unit string (``millimeter``, ``inch``, etc.).
        model_path:  ZIP-internal path of the model XML file.
        metadata:    ``{name: value}`` dict of ``<metadata>`` elements.
        raw_entries: ``{zip_path: bytes}`` of every non-model ZIP member,
                     kept for lossless round-trip.
        source_path: Filesystem path the data was loaded from.
    """

    meshes: tuple[MeshData, ...]
    unit: str
    model_path: str
    metadata: dict[str, str]
    raw_entries: dict[str, bytes]
    source_path: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _find_model_path(zf: zipfile.ZipFile) -> str:
    """Locate the primary model XML inside the ZIP archive.

    Checks in order:
    1. ``3D/3dmodel.model`` (standard location)
    2. First ``.model`` file found anywhere in the archive
    """
    standard = "3D/3dmodel.model"
    names = zf.namelist()
    if standard in names:
        return standard
    for name in names:
        if name.lower().endswith(".model"):
            return name
    raise FileNotFoundError(
        "No .model file found inside the 3MF archive"
    )


def _parse_mesh_element(
    obj_elem: ET.Element,
    ns: str,
) -> MeshData | None:
    """Extract mesh arrays from an ``<object>`` element.

    Returns ``None`` when the element has no ``<mesh>`` child (e.g.
    component-only objects).
    """
    mesh_elem = obj_elem.find(_tag("mesh", ns))
    if mesh_elem is None:
        return None

    object_id = obj_elem.get("id", "")
    name = obj_elem.get("name", "")

    # -- vertices ----------------------------------------------------------
    verts_elem = mesh_elem.find(_tag("vertices", ns))
    if verts_elem is None:
        return None

    vert_list: list[tuple[float, float, float]] = []
    for v in verts_elem.iterfind(_tag("vertex", ns)):
        x = float(v.get("x", "0"))
        y = float(v.get("y", "0"))
        z = float(v.get("z", "0"))
        vert_list.append((x, y, z))

    if not vert_list:
        return None

    vertices = np.array(vert_list, dtype=np.float64)

    # -- triangles ---------------------------------------------------------
    tris_elem = mesh_elem.find(_tag("triangles", ns))
    if tris_elem is None:
        return None

    tri_list: list[tuple[int, int, int]] = []
    for t in tris_elem.iterfind(_tag("triangle", ns)):
        v1 = int(t.get("v1", "0"))
        v2 = int(t.get("v2", "0"))
        v3 = int(t.get("v3", "0"))
        tri_list.append((v1, v2, v3))

    if not tri_list:
        return None

    triangles = np.array(tri_list, dtype=np.int32)

    return MeshData(
        object_id=object_id,
        name=name,
        vertices=vertices,
        triangles=triangles,
    )


def _detect_namespace(root: ET.Element) -> str:
    """Extract the primary namespace from the root ``<model>`` element.

    Falls back to :data:`NS_CORE` when no namespace is present.
    """
    tag = root.tag
    if tag.startswith("{"):
        return tag[1 : tag.index("}")]
    return NS_CORE


def parse_3mf(path: str) -> ThreeMFData:
    """Parse a 3MF file into an immutable :class:`ThreeMFData` structure.

    Steps
    -----
    1. Open the file as a :class:`zipfile.ZipFile`.
    2. Locate the primary model XML (usually ``3D/3dmodel.model``).
    3. Parse the XML; detect the 3MF core namespace.
    4. Extract ``<object>`` elements with ``<mesh>`` children.
    5. Collect ``<metadata>`` key/value pairs.
    6. Store every *non-model* ZIP member as raw bytes so that a subsequent
       :func:`write_3mf` call can preserve slicer settings, thumbnails,
       and other auxiliary data.

    Parameters
    ----------
    path:
        Filesystem path to a ``.3mf`` file.

    Returns
    -------
    ThreeMFData
        Frozen dataclass with all parsed data.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist or the archive contains no model XML.
    zipfile.BadZipFile
        If the file is not a valid ZIP archive.
    """
    path = os.path.abspath(path)

    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    with zipfile.ZipFile(path, "r") as zf:
        model_path = _find_model_path(zf)

        # -- raw entries (everything except the model XML) -----------------
        raw_entries: dict[str, bytes] = {}
        for entry in zf.namelist():
            if entry != model_path:
                raw_entries[entry] = zf.read(entry)

        # -- parse model XML -----------------------------------------------
        model_bytes = zf.read(model_path)

    root = ET.fromstring(model_bytes)
    ns = _detect_namespace(root)

    # Unit
    unit = root.get("unit", "millimeter")

    # Metadata
    metadata: dict[str, str] = {}
    for meta in root.iterfind(_tag("metadata", ns)):
        meta_name = meta.get("name", "")
        meta_value = meta.text or ""
        if meta_name:
            metadata[meta_name] = meta_value

    # Meshes
    meshes: list[MeshData] = []
    resources = root.find(_tag("resources", ns))
    if resources is not None:
        for obj in resources.iterfind(_tag("object", ns)):
            mesh_data = _parse_mesh_element(obj, ns)
            if mesh_data is not None:
                meshes.append(mesh_data)

    return ThreeMFData(
        meshes=tuple(meshes),
        unit=unit,
        model_path=model_path,
        metadata=dict(metadata),
        raw_entries=dict(raw_entries),
        source_path=path,
    )


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _rebuild_model_xml(data: ThreeMFData) -> bytes:
    """Rebuild the model XML from *data*, preserving non-mesh elements.

    The strategy is:
    1. Re-parse the original XML from ``raw_entries`` or regenerate from
       scratch.
    2. For each ``<object>`` whose id matches one of our :class:`MeshData`
       objects, replace its ``<mesh>`` sub-tree with the (possibly modified)
       vertex/triangle arrays.
    3. Leave every other element untouched.

    When no original XML is available (e.g. the caller built
    :class:`ThreeMFData` programmatically), a minimal valid model is
    generated.
    """

    # -- attempt to load the original XML for preservation -----------------
    original_bytes: bytes | None = None

    # If the caller kept raw bytes for the model path (unlikely but
    # possible), use them; otherwise we need the original file.
    if data.source_path and os.path.isfile(data.source_path):
        try:
            with zipfile.ZipFile(data.source_path, "r") as zf:
                original_bytes = zf.read(data.model_path)
        except Exception:
            original_bytes = None

    mesh_lookup: dict[str, MeshData] = {m.object_id: m for m in data.meshes}

    if original_bytes is not None:
        root = ET.fromstring(original_bytes)
        ns = _detect_namespace(root)

        resources = root.find(_tag("resources", ns))
        if resources is not None:
            for obj in resources.iterfind(_tag("object", ns)):
                oid = obj.get("id", "")
                if oid not in mesh_lookup:
                    continue
                md = mesh_lookup[oid]

                # Remove old mesh element
                old_mesh = obj.find(_tag("mesh", ns))
                if old_mesh is not None:
                    obj.remove(old_mesh)

                # Build new mesh element
                new_mesh = _build_mesh_element(md, ns)
                obj.append(new_mesh)
    else:
        # Build from scratch
        root = _build_model_from_scratch(data)

    # Serialise
    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(
        buf,
        xml_declaration=True,
        encoding="UTF-8",
    )
    return buf.getvalue()


def _build_mesh_element(md: MeshData, ns: str) -> ET.Element:
    """Create a ``<mesh>`` XML element from vertex/triangle arrays."""
    mesh_el = ET.Element(_tag("mesh", ns))

    # Vertices
    verts_el = ET.SubElement(mesh_el, _tag("vertices", ns))
    for row in md.vertices:
        ET.SubElement(
            verts_el,
            _tag("vertex", ns),
            x=f"{row[0]:.6g}",
            y=f"{row[1]:.6g}",
            z=f"{row[2]:.6g}",
        )

    # Triangles
    tris_el = ET.SubElement(mesh_el, _tag("triangles", ns))
    for row in md.triangles:
        ET.SubElement(
            tris_el,
            _tag("triangle", ns),
            v1=str(row[0]),
            v2=str(row[1]),
            v3=str(row[2]),
        )

    return mesh_el


def _build_model_from_scratch(data: ThreeMFData) -> ET.Element:
    """Generate a minimal ``<model>`` tree when no original XML exists."""
    root = ET.Element(
        _tag("model", NS_CORE),
        unit=data.unit,
    )

    # Metadata
    for name, value in data.metadata.items():
        meta = ET.SubElement(root, _tag("metadata", NS_CORE), name=name)
        meta.text = value

    # Resources
    resources = ET.SubElement(root, _tag("resources", NS_CORE))
    build = ET.SubElement(root, _tag("build", NS_CORE))

    for md in data.meshes:
        obj = ET.SubElement(
            resources,
            _tag("object", NS_CORE),
            id=md.object_id,
            type="model",
        )
        if md.name:
            obj.set("name", md.name)

        mesh_el = _build_mesh_element(md, NS_CORE)
        obj.append(mesh_el)

        ET.SubElement(build, _tag("item", NS_CORE), objectid=md.object_id)

    return root


def write_3mf(data: ThreeMFData, output_path: str) -> None:
    """Write a :class:`ThreeMFData` structure to a 3MF (ZIP) file.

    Steps
    -----
    1. Rebuild the model XML from the in-memory vertex/triangle data while
       preserving every non-mesh element (metadata, build items, extension
       namespaces, slicer settings embedded as attributes, etc.).
    2. Copy all ``raw_entries`` (thumbnails, Bambu profiles, OPC
       relationships, ...) into the new ZIP archive.
    3. Write the rebuilt model XML at its original ``model_path``.

    Parameters
    ----------
    data:
        The model data to write.
    output_path:
        Destination filesystem path.  Parent directories are created if
        they do not exist.
    """
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    model_xml_bytes = _rebuild_model_xml(data)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write raw (non-model) entries first
        for entry_path, entry_bytes in data.raw_entries.items():
            zf.writestr(entry_path, entry_bytes)

        # Write the model XML
        zf.writestr(data.model_path, model_xml_bytes)
