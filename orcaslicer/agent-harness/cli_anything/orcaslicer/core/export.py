"""OrcaSlicer CLI - export pipeline (3MF project, effective settings, STL, G-code).

Every export is produced by the real OrcaSlicer binary and then verified.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import tempfile
import zipfile
from typing import Any, Dict, List, Optional

from cli_anything.orcaslicer.core import slicer
from cli_anything.orcaslicer.core import transforms as tf
from cli_anything.orcaslicer.utils import orcaslicer_backend as backend


def _backend_args(project: Dict[str, Any], settings: Dict[str, Any], *extra: str) -> List[str]:
    args = ["--load-settings", f"{settings['machine']};{settings['process']}",
            "--load-filaments", ";".join(settings["filaments"])]
    if tf.repetitions_need_plate(project["transforms"], project["models"]):
        raise ValueError("Copies on a .3mf model can only be exported together with slicing "
                         "(use 'slice run --export-3mf' or 'export 3mf' without --no-slice).")
    args += tf.build_args(project["transforms"], project["models"])
    if slicer.needs_ensure_on_bed(project):
        args.append("--ensure-on-bed")
    args += list(extra)
    args += [m["path"] for m in project["models"]]
    return args


def _guard(path: str, overwrite: bool) -> str:
    path = os.path.abspath(path)
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"{path} already exists. Use --overwrite to replace it.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def verify_3mf(path: str, expect_gcode: bool = False) -> Dict[str, Any]:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{path} is not a valid 3MF (ZIP) archive.")
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        bad = zf.testzip()
    if bad:
        raise ValueError(f"3MF archive is corrupt (bad member: {bad}).")
    required = ["[Content_Types].xml", "3D/3dmodel.model", "Metadata/project_settings.config"]
    missing = [r for r in required if r not in names]
    if missing:
        raise ValueError(f"3MF is missing required parts: {', '.join(missing)}")
    gcodes = [n for n in names if n.startswith("Metadata/plate_") and n.endswith(".gcode")]
    if expect_gcode and not gcodes:
        raise ValueError("3MF contains no sliced G-code (expected Metadata/plate_N.gcode).")
    return {"path": os.path.abspath(path), "bytes": os.path.getsize(path),
            "members": len(names), "gcode_plates": len(gcodes),
            "thumbnails": sorted(n for n in names if n.endswith(".png"))}


def _need_models(project: Dict[str, Any]) -> None:
    slicer._check_models(project)


def export_3mf(project: Dict[str, Any], path: str, project_path: Optional[str] = None,
               with_slice: bool = True, overwrite: bool = False, timeout: int = 900) -> Dict[str, Any]:
    """Export an OrcaSlicer .3mf project (sliced by default, embedding G-code + thumbnails)."""
    _need_models(project)
    target = _guard(path, overwrite)
    if with_slice:
        # Intermediate G-code/settings go to a scratch dir: the caller asked for a 3MF only.
        # (Use 'slice run --export-3mf' to keep the G-code as well.)
        with tempfile.TemporaryDirectory(prefix="orca3mf_slice_") as scratch:
            res = slicer.slice_project(project, project_path=project_path, outdir=scratch,
                                       export_3mf=target, timeout=timeout, record=False)
        info = verify_3mf(target, expect_gcode=True)
        info.update(sliced=True, print_time=res["plates"][0].get("print_time"),
                    layers=res["plates"][0].get("layers"))
        return info
    with tempfile.TemporaryDirectory(prefix="orca3mf_") as tmp:
        settings = slicer.prepare_settings(project, os.path.join(tmp, "settings"))
        name = "project.3mf"
        args = _backend_args(project, settings, "--outputdir", tmp, "--export-3mf", name)
        backend.run(args, cwd=tmp, timeout=timeout, check=True)
        produced = os.path.join(tmp, name)
        if not os.path.isfile(produced):
            raise RuntimeError("OrcaSlicer did not produce a 3MF file.")
        shutil.move(produced, target)
    info = verify_3mf(target)
    info["sliced"] = False
    return info


def export_settings(project: Dict[str, Any], path: str, overwrite: bool = False,
                    timeout: int = 120) -> Dict[str, Any]:
    """Dump the full effective configuration as resolved by OrcaSlicer itself."""
    _need_models(project)
    target = _guard(path, overwrite)
    with tempfile.TemporaryDirectory(prefix="orcaset_") as tmp:
        settings = slicer.prepare_settings(project, os.path.join(tmp, "settings"))
        args = _backend_args(project, settings, "--export-settings", target)
        backend.run(args, cwd=tmp, timeout=timeout, check=True)
    if not os.path.isfile(target):
        raise RuntimeError("OrcaSlicer did not write the settings file.")
    with open(target, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {"path": target, "bytes": os.path.getsize(target), "keys": len(data)}


def export_stl(project: Dict[str, Any], dest_dir: str, overwrite: bool = False,
               timeout: int = 300) -> Dict[str, Any]:
    """Export the (transformed) objects as STL files — one per object — into dest_dir."""
    _need_models(project)
    dest = os.path.abspath(dest_dir)
    os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="orcastl_") as tmp:
        settings = slicer.prepare_settings(project, os.path.join(tmp, "settings"))
        args = _backend_args(project, settings, "--outputdir", tmp, "--export-stl")
        backend.run(args, cwd=tmp, timeout=timeout, check=True)
        produced = sorted(glob.glob(os.path.join(tmp, "stl", "*.stl")))
        if not produced:
            raise RuntimeError("OrcaSlicer did not produce any STL files.")
        files = []
        for src in produced:
            target = os.path.join(dest, os.path.basename(src))
            if os.path.exists(target) and not overwrite:
                raise FileExistsError(f"{target} already exists. Use --overwrite to replace it.")
            shutil.copyfile(src, target)
            if os.path.getsize(target) < 84:
                raise ValueError(f"Exported STL is too small to be valid: {target}")
            files.append({"path": target, "bytes": os.path.getsize(target)})
    return {"dest": dest, "files": files}


def export_gcode(project: Dict[str, Any], dest: str, plate: int = 1,
                 overwrite: bool = False) -> Dict[str, Any]:
    """Copy the G-code of the last slice to ``dest`` (file path). Run 'slice run' first."""
    entry = slicer.last_slice(project)
    for p in entry["plates"]:
        if p["plate"] == plate:
            src = p["path"]
            if not os.path.isfile(src):
                raise FileNotFoundError(f"Sliced G-code no longer exists: {src}. Re-run 'slice run'.")
            target = _guard(dest, overwrite)
            shutil.copyfile(src, target)
            info = slicer.gcode_info(target)
            return {"path": target, "bytes": info["bytes"], "layers": info["layers"],
                    "print_time": info["print_time"]}
    raise IndexError(f"Plate {plate} not in the last slice "
                     f"(plates: {[p['plate'] for p in entry['plates']]}).")
