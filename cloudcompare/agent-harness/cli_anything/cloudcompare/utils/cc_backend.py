"""CloudCompare backend — invokes the real CloudCompare executable.

CloudCompare ships with a full command-line mode via the -SILENT flag.
This module wraps that CLI and handles Flatpak/native detection.

Usage pattern:
    CloudCompare -SILENT -O input.las -SS SPATIAL 0.05 -SAVE_CLOUDS

Reference: https://www.cloudcompare.org/doc/wiki/index.php/Command_line_mode
"""

import glob
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


# Supported input/output file extensions
CLOUD_FORMATS = {
    "bin": "BIN",
    "las": "LAS",
    "laz": "LAS",
    "ply": "PLY",
    "pcd": "PCD",
    "xyz": "ASC",
    "txt": "ASC",
    "asc": "ASC",
    "csv": "ASC",
    "e57": "E57",
    "dp": "DP",
}

MESH_FORMATS = {
    "obj": "OBJ",
    "stl": "STL",
    "ply": "PLY",
    "bin": "BIN",
}


def find_cloudcompare() -> list[str]:
    """Locate the CloudCompare executable.

    Returns a command prefix list (e.g., ['CloudCompare'] or
    ['flatpak', 'run', 'org.cloudcompare.CloudCompare']).

    Raises RuntimeError with install instructions if not found.
    """
    # 1. Try native binary first
    native = shutil.which("CloudCompare") or shutil.which("cloudcompare")
    if native:
        return [native]

    # 2. Try Flatpak
    flatpak = shutil.which("flatpak")
    if flatpak:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True,
            text=True,
        )
        if "org.cloudcompare.CloudCompare" in result.stdout:
            return ["flatpak", "run", "org.cloudcompare.CloudCompare"]

    # 3. Try snap
    snap_path = "/snap/bin/cloudcompare"
    if os.path.exists(snap_path):
        return [snap_path]

    raise RuntimeError(
        "CloudCompare is not installed or not found.\n"
        "Install it with one of:\n"
        "  flatpak install flathub org.cloudcompare.CloudCompare  # Flatpak\n"
        "  sudo apt install cloudcompare                          # Debian/Ubuntu\n"
        "  brew install --cask cloudcompare                       # macOS\n"
        "  https://cloudcompare.org/release/index.html            # Windows installer"
    )


def run_cloudcompare(args: list[str], cwd: Optional[str] = None) -> dict:
    """Run CloudCompare with the given arguments in silent mode.

    Args:
        args: List of CC arguments (without the executable itself).
              The -SILENT flag is prepended automatically.
        cwd: Working directory for the subprocess.

    Returns:
        dict with keys: returncode, stdout, stderr, command
    """
    cmd_prefix = find_cloudcompare()
    full_cmd = cmd_prefix + ["-SILENT"] + args

    result = subprocess.run(
        full_cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": " ".join(full_cmd),
    }


def open_and_save(
    input_path: str,
    output_path: str,
    extra_args: Optional[list[str]] = None,
) -> dict:
    """Load a point cloud, optionally process it, and save.

    Args:
        input_path: Path to input file.
        output_path: Path to output file.
        extra_args: Additional CC command-line arguments between load and save.

    Returns:
        dict with result info.
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)
    out_dir = os.path.dirname(output_path)
    out_name = os.path.splitext(os.path.basename(output_path))[0]
    out_ext = os.path.splitext(output_path)[1].lstrip(".")

    fmt = CLOUD_FORMATS.get(out_ext.lower(), "ASC")

    args = ["-O", input_path]
    if extra_args:
        args.extend(extra_args)

    args += [
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_CLOUDS", "FILE", output_path,
    ]

    result = run_cloudcompare(args, cwd=out_dir)
    result["output"] = output_path
    result["exists"] = os.path.exists(output_path)
    if result["exists"]:
        result["file_size"] = os.path.getsize(output_path)
    return result


def subsample(
    input_path: str,
    output_path: str,
    method: str = "SPATIAL",
    parameter: float = 0.05,
) -> dict:
    """Subsample a point cloud.

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file.
        method: RANDOM (count), SPATIAL (min dist), or OCTREE (level).
        parameter: For RANDOM: point count. For SPATIAL: min distance.
                   For OCTREE: octree level (1-10).
    """
    method = method.upper()
    if method not in ("RANDOM", "SPATIAL", "OCTREE"):
        raise ValueError(f"method must be RANDOM, SPATIAL, or OCTREE, got {method!r}")

    if method == "OCTREE":
        param_str = str(int(parameter))
    elif method == "RANDOM":
        count = int(parameter)
        if count <= 0:
            raise ValueError(
                f"RANDOM subsampling parameter must be a positive integer point count, got {parameter!r}"
            )
        param_str = str(count)
    else:
        param_str = str(parameter)

    return open_and_save(input_path, output_path, ["-SS", method, param_str])


def compute_roughness(
    input_path: str,
    output_path: str,
    radius: float = 0.1,
) -> dict:
    """Compute roughness scalar field for a point cloud.

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file (with roughness SF).
        radius: Sphere radius for roughness computation.
    """
    return open_and_save(input_path, output_path, ["-ROUGH", str(radius)])


def compute_density(
    input_path: str,
    output_path: str,
    sphere_radius: float = 0.1,
    density_type: str = "KNN",
) -> dict:
    """Compute point density scalar field.

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file.
        sphere_radius: Sphere radius for density computation.
        density_type: KNN, SURFACE, or VOLUME.
    """
    density_type = density_type.upper()
    extra = ["-DENSITY", str(sphere_radius), "-TYPE", density_type]
    return open_and_save(input_path, output_path, extra)


def compute_curvature(
    input_path: str,
    output_path: str,
    curvature_type: str = "MEAN",
    radius: float = 0.1,
) -> dict:
    """Compute curvature scalar field.

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file.
        curvature_type: MEAN or GAUSS.
        radius: Kernel radius.
    """
    curvature_type = curvature_type.upper()
    return open_and_save(input_path, output_path, ["-CURV", curvature_type, str(radius)])


def sor_filter(
    input_path: str,
    output_path: str,
    nb_points: int = 6,
    std_ratio: float = 1.0,
) -> dict:
    """Statistical Outlier Removal (SOR) filter.

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file.
        nb_points: Number of nearest neighbors.
        std_ratio: Standard deviation multiplier threshold.
    """
    return open_and_save(input_path, output_path, ["-SOR", str(nb_points), str(std_ratio)])


def crop_cloud(
    input_path: str,
    output_path: str,
    xmin: float,
    ymin: float,
    zmin: float,
    xmax: float,
    ymax: float,
    zmax: float,
    outside: bool = False,
) -> dict:
    """Crop a point cloud to a bounding box.

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file.
        xmin/ymin/zmin: Minimum corner.
        xmax/ymax/zmax: Maximum corner.
        outside: If True, keep points outside the box.
    """
    extra = ["-CROP", f"{xmin}:{ymin}:{zmin}:{xmax}:{ymax}:{zmax}"]
    if outside:
        extra.append("-OUTSIDE")
    return open_and_save(input_path, output_path, extra)


def merge_clouds(
    input_paths: list[str],
    output_path: str,
) -> dict:
    """Merge multiple point clouds into one.

    Args:
        input_paths: List of input cloud files.
        output_path: Output merged cloud file.
    """
    if len(input_paths) < 2:
        raise ValueError("Need at least 2 clouds to merge")

    output_path = os.path.abspath(output_path)
    out_ext = os.path.splitext(output_path)[1].lstrip(".")
    fmt = CLOUD_FORMATS.get(out_ext.lower(), "ASC")

    args = []
    for p in input_paths:
        args += ["-O", os.path.abspath(p)]

    args += [
        "-MERGE_CLOUDS",
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_CLOUDS", "FILE", output_path,
    ]

    result = run_cloudcompare(args)
    result["output"] = output_path
    result["exists"] = os.path.exists(output_path)
    if result["exists"]:
        result["file_size"] = os.path.getsize(output_path)
    return result


def compute_c2c_distances(
    compare_path: str,
    reference_path: str,
    output_path: str,
    split_xyz: bool = False,
    octree_level: int = 10,
) -> dict:
    """Compute cloud-to-cloud distances.

    Args:
        compare_path: 'Compared' cloud (gets the distance SF).
        reference_path: 'Reference' cloud.
        output_path: Output cloud file with distance SF.
        split_xyz: If True, also compute X/Y/Z components separately.
        octree_level: Octree level for the computation.
    """
    args = [
        "-O", os.path.abspath(reference_path),
        "-O", os.path.abspath(compare_path),
        "-C2C_DIST",
        "-OCTREE_LEVEL", str(octree_level),
    ]
    if split_xyz:
        args.append("-SPLIT_XYZ")

    output_path = os.path.abspath(output_path)
    out_ext = os.path.splitext(output_path)[1].lstrip(".")
    fmt = CLOUD_FORMATS.get(out_ext.lower(), "ASC")

    args += [
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_CLOUDS", "FILE", output_path,
    ]

    result = run_cloudcompare(args)
    result["output"] = output_path
    result["exists"] = os.path.exists(output_path)
    if result["exists"]:
        result["file_size"] = os.path.getsize(output_path)
    return result


def compute_c2m_distances(
    cloud_path: str,
    mesh_path: str,
    output_path: str,
    flip_normals: bool = False,
    unsigned: bool = False,
) -> dict:
    """Compute cloud-to-mesh distances.

    Args:
        cloud_path: Input point cloud.
        mesh_path: Reference mesh.
        output_path: Output cloud with distance SF.
        flip_normals: Flip mesh normals before computing.
        unsigned: Compute unsigned distances.
    """
    args = [
        "-O", os.path.abspath(mesh_path),
        "-O", os.path.abspath(cloud_path),
        "-C2M_DIST",
    ]
    if flip_normals:
        args.append("-FLIP_NORMS")
    if unsigned:
        args.append("-UNSIGNED")

    output_path = os.path.abspath(output_path)
    out_ext = os.path.splitext(output_path)[1].lstrip(".")
    fmt = CLOUD_FORMATS.get(out_ext.lower(), "ASC")

    args += [
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_CLOUDS", "FILE", output_path,
    ]

    result = run_cloudcompare(args)
    result["output"] = output_path
    result["exists"] = os.path.exists(output_path)
    if result["exists"]:
        result["file_size"] = os.path.getsize(output_path)
    return result


def run_icp(
    aligned_path: str,
    reference_path: str,
    output_path: str,
    max_iterations: int = 100,
    min_error_diff: float = 1e-6,
    overlap: float = 100.0,
) -> dict:
    """Run ICP (Iterative Closest Point) registration.

    Args:
        aligned_path: Cloud to align.
        reference_path: Reference cloud.
        output_path: Aligned output cloud.
        max_iterations: Maximum ICP iterations.
        min_error_diff: Stop when improvement is below this.
        overlap: Percentage of overlap (0-100).
    """
    args = [
        "-O", os.path.abspath(reference_path),
        "-O", os.path.abspath(aligned_path),
        "-ICP",
        "-ITER", str(max_iterations),
        "-MIN_ERROR_DIFF", str(min_error_diff),
        "-OVERLAP", str(overlap),
    ]

    output_path = os.path.abspath(output_path)
    out_ext = os.path.splitext(output_path)[1].lstrip(".")
    fmt = CLOUD_FORMATS.get(out_ext.lower(), "ASC")

    args += [
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_CLOUDS", "FILE", output_path,
    ]

    result = run_cloudcompare(args)
    result["output"] = output_path
    result["exists"] = os.path.exists(output_path)
    if result["exists"]:
        result["file_size"] = os.path.getsize(output_path)
    return result


def coord_to_sf(
    input_path: str,
    output_path: str,
    dimension: str = "Z",
    sf_index: int = 0,
) -> dict:
    """Convert a coordinate axis (X/Y/Z) to a scalar field.

    This is the standard way to create a height (elevation) scalar field
    from the Z coordinate, which can then be used for filtering or analysis.

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file (with the new scalar field).
        dimension: Axis to convert: X, Y, or Z. Default Z (height).
        sf_index: Index to set as active SF after creation. Default 0.
    """
    dim = dimension.upper()
    if dim not in ("X", "Y", "Z"):
        raise ValueError(f"dimension must be X, Y, or Z, got {dim!r}")
    extra = ["-COORD_TO_SF", dim, "-SET_ACTIVE_SF", str(sf_index)]
    return open_and_save(input_path, output_path, extra)


def filter_sf_by_value(
    input_path: str,
    output_path: str,
    min_val: float,
    max_val: float,
    sf_index: Optional[int] = None,
) -> dict:
    """Filter a cloud to points whose active scalar field value falls in [min_val, max_val].

    Typical usage: after coord_to_sf(dim="Z"), filter to a height range.

    Args:
        input_path: Input cloud file (must have an active scalar field).
        output_path: Output cloud file (filtered).
        min_val: Minimum SF value to keep.
        max_val: Maximum SF value to keep.
        sf_index: If given, sets this SF index as active before filtering.
                  Use when the cloud has multiple SFs and you need to pick one.
    """
    extra = []
    if sf_index is not None:
        extra += ["-SET_ACTIVE_SF", str(sf_index)]
    extra += ["-FILTER_SF", str(min_val), str(max_val)]
    return open_and_save(input_path, output_path, extra)


def coord_to_sf_and_filter(
    input_path: str,
    output_path: str,
    dimension: str = "Z",
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> dict:
    """Convert a coordinate to SF and optionally filter by value range in one pass.

    Combines -COORD_TO_SF and -FILTER_SF in a single CloudCompare invocation.
    Useful for height-based slice extraction (e.g., keep points between z=10 and z=20).

    Args:
        input_path: Input cloud file.
        output_path: Output cloud file.
        dimension: X, Y, or Z. Default Z.
        min_val: Minimum value to keep. None = no lower bound (uses 'MIN').
        max_val: Maximum value to keep. None = no upper bound (uses 'MAX').
    """
    dim = dimension.upper()
    if dim not in ("X", "Y", "Z"):
        raise ValueError(f"dimension must be X, Y, or Z, got {dim!r}")

    extra = ["-COORD_TO_SF", dim, "-SET_ACTIVE_SF", "0"]

    if min_val is not None or max_val is not None:
        lo = str(min_val) if min_val is not None else "MIN"
        hi = str(max_val) if max_val is not None else "MAX"
        extra += ["-FILTER_SF", lo, hi]

    return open_and_save(input_path, output_path, extra)


def convert_format(
    input_path: str,
    output_path: str,
) -> dict:
    """Convert a point cloud from one format to another.

    Args:
        input_path: Input cloud (any supported format).
        output_path: Output cloud (format determined by extension).
    """
    return open_and_save(input_path, output_path)


def compute_normals(
    input_path: str,
    output_path: str,
    octree_level: int = 10,
    orientation: str = "PLUS_Z",
) -> dict:
    """Compute normals via octree.

    Args:
        input_path: Input cloud.
        output_path: Output cloud with normals.
        octree_level: Octree level for normal computation.
        orientation: Normal orientation hint: PLUS_X/Y/Z or MINUS_X/Y/Z.
    """
    extra = ["-OCTREE_NORMALS", str(octree_level)]
    if orientation:
        extra += ["-ORIENT", orientation]
    return open_and_save(input_path, output_path, extra)


def csf_filter(
    input_path: str,
    ground_output: str,
    offground_output: Optional[str] = None,
    scene: str = "RELIEF",
    cloth_resolution: float = 2.0,
    class_threshold: float = 0.5,
    max_iteration: int = 500,
    proc_slope: bool = False,
) -> dict:
    """Ground filtering using the Cloth Simulation Filter (CSF) algorithm.

    CSF simulates a cloth draped over an inverted point cloud to separate
    ground points from off-ground points (vegetation, buildings, etc.).

    Reference: Zhang et al. (2016) Remote Sensing 8(6):501.

    Args:
        input_path: Input cloud file (LiDAR scan).
        ground_output: Output path for the ground point cloud.
        offground_output: Output path for the off-ground cloud (optional).
                          If None, off-ground points are not exported.
        scene: Scene type affecting cloth rigidness:
               - SLOPE  (rigidness=1): steep terrain with slopes
               - RELIEF (rigidness=2): general terrain (default)
               - FLAT   (rigidness=3): flat or urban terrain
        cloth_resolution: Grid resolution of the cloth (metres). Smaller =
                          finer ground detail but slower. Default 2.0.
        class_threshold: Max distance (metres) from cloth to classify a point
                         as ground. Default 0.5.
        max_iteration: Maximum cloth simulation iterations. Default 500.
        proc_slope: Enable post-processing to smooth slope artifacts. Default False.

    Returns:
        dict with keys: returncode, ground, ground_exists, ground_size,
        and optionally offground, offground_exists, offground_size.
    """
    scene = scene.upper()
    if scene not in ("SLOPE", "RELIEF", "FLAT"):
        raise ValueError(f"scene must be SLOPE, RELIEF, or FLAT, got {scene!r}")

    input_path = os.path.abspath(input_path)
    ground_output = os.path.abspath(ground_output)
    in_dir = os.path.dirname(input_path)
    in_stem = os.path.splitext(os.path.basename(input_path))[0]

    # Determine export format from requested output extension
    out_ext = os.path.splitext(ground_output)[1].lstrip(".").lower()
    fmt = CLOUD_FORMATS.get(out_ext, "LAS")

    # Build the CC command.
    # IMPORTANT: -C_EXPORT_FMT must come BEFORE -CSF so the format is set
    # before CSF calls exportEntity() internally for -EXPORT_GROUND/OFFGROUND.
    args = [
        "-O", input_path,
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-CSF",
        "-SCENES", scene,
        "-CLOTH_RESOLUTION", str(cloth_resolution),
        "-CLASS_THRESHOLD", str(class_threshold),
        "-MAX_ITERATION", str(max_iteration),
    ]
    if proc_slope:
        args.append("-PROC_SLOPE")
    args.append("-EXPORT_GROUND")
    if offground_output is not None:
        args.append("-EXPORT_OFFGROUND")

    result = run_cloudcompare(args, cwd=in_dir)

    # CC auto-generates output filenames: {stem}_ground_points.{ext}
    # Use glob to find them robustly (extension may vary by fmt)
    def _find_and_move(pattern: str, dest: str) -> bool:
        candidates = glob.glob(pattern)
        if not candidates:
            return False
        src = candidates[0]
        if src != dest:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            os.replace(src, dest)
        return os.path.exists(dest)

    ground_exists = _find_and_move(
        os.path.join(in_dir, f"{in_stem}_ground_points.*"),
        ground_output,
    )

    result["ground"] = ground_output
    result["ground_exists"] = ground_exists
    result["ground_size"] = os.path.getsize(ground_output) if ground_exists else 0

    if offground_output is not None:
        offground_output = os.path.abspath(offground_output)
        offground_exists = _find_and_move(
            os.path.join(in_dir, f"{in_stem}_offground_points.*"),
            offground_output,
        )
        result["offground"] = offground_output
        result["offground_exists"] = offground_exists
        result["offground_size"] = os.path.getsize(offground_output) if offground_exists else 0

    return result


def sf_to_rgb(
    input_path: str,
    output_path: str,
) -> dict:
    """Convert the active scalar field to RGB colours.

    CloudCompare maps each SF value through the current colour ramp and stores
    the result as per-point RGB.  Useful before applying colour-based filters
    or exporting a coloured cloud.

    Args:
        input_path: Input cloud (must have an active scalar field).
        output_path: Output cloud with RGB colours.
    """
    return open_and_save(input_path, output_path, ["-SF_CONVERT_TO_RGB", "TRUE"])


def rgb_to_sf(
    input_path: str,
    output_path: str,
) -> dict:
    """Convert RGB colours to a scalar field (intensity/greyscale).

    The resulting SF stores the luminance of each point's RGB triplet.

    Args:
        input_path: Input cloud with RGB colours.
        output_path: Output cloud with the new scalar field.
    """
    return open_and_save(input_path, output_path, ["-RGB_CONVERT_TO_SF"])


def noise_filter(
    input_path: str,
    output_path: str,
    knn: int = 6,
    noisiness: float = 1.0,
    use_radius: bool = False,
    radius: float = 0.1,
    absolute: bool = False,
) -> dict:
    """Apply the PCL noise filter to remove noisy points.

    Uses CloudCompare's ``-NOISE`` command (backed by the PCL wrapper plugin).
    Noisy points are identified by comparing each point's deviation from its
    local neighbourhood to a noise threshold.

    Note: CC's CLI does not provide Gaussian/Bilateral spatial smoothing.
    This PCL noise filter is the closest available spatial noise-removal
    operation via the command line.

    Args:
        input_path:   Input cloud.
        output_path:  Filtered output cloud (noisy points removed).
        knn:          Number of nearest neighbours used when ``use_radius``
                      is False (default 6).
        noisiness:    Noise threshold multiplier.  Points whose deviation
                      exceeds this multiple of the local noise estimate are
                      removed (default 1.0).
        use_radius:   If True, use a fixed search radius instead of KNN.
        radius:       Search radius when ``use_radius`` is True.
        absolute:     If True, interpret ``noisiness`` as an absolute
                      distance threshold (ABS) rather than relative (REL).

    Returns:
        dict with output, exists, file_size, returncode.
    """
    mode = "RADIUS" if use_radius else "KNN"
    mode_val = str(radius) if use_radius else str(knn)
    threshold_mode = "ABS" if absolute else "REL"

    extra = ["-NOISE", mode, mode_val, threshold_mode, str(noisiness)]
    return open_and_save(input_path, output_path, extra)


def invert_normals(
    input_path: str,
    output_path: str,
) -> dict:
    """Invert (flip) all normals in a point cloud.

    Args:
        input_path:  Input cloud with normals.
        output_path: Output cloud with flipped normals.
    """
    return open_and_save(input_path, output_path, ["-INVERT_NORMALS"])


def apply_transform(
    input_path: str,
    output_path: str,
    matrix_file: str,
    inverse: bool = False,
) -> dict:
    """Apply a rigid-body (or affine) transformation to a point cloud.

    The transformation is read from a plain-text file containing a 4×4 matrix
    (one row per line, values space-separated).

    Args:
        input_path:   Input cloud or mesh.
        output_path:  Transformed output cloud.
        matrix_file:  Path to the 4×4 transformation matrix text file.
        inverse:      If True, apply the inverse of the matrix.

    Example matrix file (identity)::

        1 0 0 0
        0 1 0 0
        0 0 1 0
        0 0 0 1
    """
    matrix_file = os.path.abspath(matrix_file)
    extra = ["-APPLY_TRANS"]
    if inverse:
        extra.append("-INVERSE")
    extra.append(matrix_file)
    return open_and_save(input_path, output_path, extra)


def delaunay_mesh(
    input_path: str,
    output_path: str,
    axis_aligned: bool = True,
    max_edge_length: float = 0.0,
) -> dict:
    """Create a 2.5-D Delaunay triangulation mesh from a point cloud.

    Projects the cloud onto a plane (axis-aligned XY or best-fit) and
    triangulates the projected points.  Suitable for terrain-like surfaces.

    Args:
        input_path:      Input cloud.
        output_path:     Output mesh file (extension determines format).
        axis_aligned:    If True, project onto the XY plane (-AA).
                         If False, use the best-fit plane (-BEST_FIT).
        max_edge_length: Remove triangles whose longest edge exceeds this
                         value (0 = no limit).

    Returns:
        dict with output, exists, file_size, returncode.
    """
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)
    out_dir = os.path.dirname(output_path) or "."
    out_ext = Path(output_path).suffix.lstrip(".")
    fmt = MESH_FORMATS.get(out_ext.lower(), "OBJ")

    args = ["-O", input_path, "-DELAUNAY"]
    if axis_aligned:
        args.append("-AA")
    else:
        args.append("-BEST_FIT")
    if max_edge_length > 0:
        args += ["-MAX_EDGE_LENGTH", str(max_edge_length)]
    args += [
        "-M_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_MESHES", "FILE", output_path,
    ]

    result = run_cloudcompare(args, cwd=out_dir)
    result["output"] = output_path
    result["exists"] = os.path.exists(output_path)
    if result["exists"]:
        result["file_size"] = os.path.getsize(output_path)
    return result


def sample_mesh(
    mesh_path: str,
    output_path: str,
    count: int = 10000,
) -> dict:
    """Sample a point cloud from a mesh surface.

    Randomly places ``count`` points on the mesh triangles, proportional to
    triangle area.

    Args:
        mesh_path:   Input mesh file.
        output_path: Output sampled point cloud.
        count:       Number of points to sample.
    """
    mesh_path = os.path.abspath(mesh_path)
    output_path = os.path.abspath(output_path)
    out_dir = os.path.dirname(output_path) or "."
    out_ext = Path(output_path).suffix.lstrip(".")
    fmt = CLOUD_FORMATS.get(out_ext.lower(), "ASC")

    args = [
        "-O", mesh_path,
        "-SAMPLE_MESH", "DENSITY", str(count),
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-SAVE_CLOUDS", "FILE", output_path,
    ]

    result = run_cloudcompare(args, cwd=out_dir)
    result["output"] = output_path
    result["exists"] = os.path.exists(output_path)
    if result["exists"]:
        result["file_size"] = os.path.getsize(output_path)
    return result


def extract_connected_components(
    input_path: str,
    output_dir: str,
    octree_level: int = 8,
    min_points: int = 100,
    output_fmt: str = "xyz",
) -> dict:
    """Segment a cloud into connected components (clusters).

    Uses CloudCompare's ``-EXTRACT_CC`` command which labels connected regions
    at a given octree resolution and exports each component as a separate file.

    Args:
        input_path:   Input cloud.
        output_dir:   Directory where component clouds will be saved.
        octree_level: Octree level controlling neighbourhood radius
                      (1-10; higher = finer, more components).
        min_points:   Discard components with fewer than this many points.
        output_fmt:   Output file extension / format (default ``"xyz"``).

    Returns:
        dict with output_dir, components (list of paths), component_count,
        returncode.
    """
    input_path = os.path.abspath(input_path)
    output_dir = os.path.abspath(output_dir)
    in_dir = os.path.dirname(input_path)
    input_stem = os.path.splitext(os.path.basename(input_path))[0]
    fmt = CLOUD_FORMATS.get(output_fmt.lower(), "ASC")

    args = [
        "-O", input_path,
        "-C_EXPORT_FMT", fmt,
        "-NO_TIMESTAMP",
        "-EXTRACT_CC", str(octree_level), str(min_points),
        "-SAVE_CLOUDS",
    ]

    # CC saves component files to the input file's directory, not cwd.
    # Files are named: {input_stem}_COMPONENT_{n}.{actual_ext}
    # The actual extension depends on the CC format name, not the input extension
    # (e.g., output_fmt="xyz" → CC format "ASC" → files saved as ".asc").
    _fmt_to_ext = {
        "ASC": "asc", "PLY": "ply", "LAS": "las",
        "PCD": "pcd", "BIN": "bin", "E57": "e57",
    }
    actual_ext = _fmt_to_ext.get(fmt, output_fmt.lower())

    result = run_cloudcompare(args, cwd=in_dir)

    # Restrict matching to the current input stem to avoid picking up leftovers.
    components = sorted(
        glob.glob(os.path.join(in_dir, f"{input_stem}_COMPONENT_*.{actual_ext}"))
    )

    # Move components to output_dir if it differs from in_dir.
    if os.path.abspath(output_dir) != os.path.abspath(in_dir):
        os.makedirs(output_dir, exist_ok=True)
        moved = []
        for c in components:
            dest = os.path.join(output_dir, os.path.basename(c))
            shutil.move(c, dest)
            moved.append(dest)
        components = sorted(moved)

    result["output_dir"] = output_dir
    result["components"] = components
    result["component_count"] = len(components)
    return result


def is_available() -> bool:
    """Check if CloudCompare is available."""
    try:
        find_cloudcompare()
        return True
    except RuntimeError:
        return False


def get_version() -> Optional[str]:
    """Try to retrieve CloudCompare version string.

    CloudCompare does not support a --version flag. For Flatpak installations,
    version is read from `flatpak info`. For native installations, returns None.
    """
    try:
        cmd = find_cloudcompare()
        # Flatpak: extract version from `flatpak info`
        if "flatpak" in cmd:
            app_id = next(
                (c for c in cmd if c.startswith("org.cloudcompare")),
                "org.cloudcompare.CloudCompare",
            )
            result = subprocess.run(
                ["flatpak", "info", app_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.splitlines():
                if line.strip().startswith("Version:"):
                    return line.split(":", 1)[1].strip()
        return None
    except Exception:
        return None
