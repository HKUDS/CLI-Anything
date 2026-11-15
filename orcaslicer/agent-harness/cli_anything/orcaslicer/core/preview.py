"""OrcaSlicer CLI - preview bundles (preview-bundle/v1).

Producer side only. Artifacts are produced by the real OrcaSlicer: the isometric / top-down
plate thumbnails it renders and embeds into a sliced 3MF, plus its own statistics JSON.
No Python rendering and no GUI scraping. Note the thumbnails depict the *model on the plate*
(post-transform, pre-toolpath); toolpath-level facts come from the statistics JSON.

Consume bundles with:  cli-hub previews inspect|html|watch|open <bundle_dir>
"""

from __future__ import annotations

import os
import shutil
import struct
import zipfile
from typing import Any, Dict, List, Optional

from cli_anything import orcaslicer as _pkg
from cli_anything.orcaslicer.core import project as proj_mod
from cli_anything.orcaslicer.core import slicer
from cli_anything.orcaslicer.utils import orcaslicer_backend as backend
from cli_anything.orcaslicer.utils import preview_bundle as pb

SOFTWARE = "orcaslicer"

RECIPES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "description": "Slice, then publish OrcaSlicer's isometric + top plate renders and a metrics summary.",
        "artifacts": ["hero.png (isometric render)", "top.png (plate top view)", "metrics in summary.json"],
        "thumbnails": [("hero", "plate_{n}.png", "Isometric plate render"),
                       ("top", "top_{n}.png", "Top-down plate render")],
        "extras": [],
    },
    "full": {
        "description": "quick + OrcaSlicer statistics JSON (per feature / layer / object) and 3MF project.",
        "artifacts": ["hero.png", "top.png", "statistics.json", "project.3mf"],
        "thumbnails": [("hero", "plate_{n}.png", "Isometric plate render"),
                       ("top", "top_{n}.png", "Top-down plate render"),
                       ("plain", "plate_no_light_{n}.png", "Unlit plate render")],
        "extras": ["statistics", "project"],
    },
}


def list_recipes() -> List[Dict[str, Any]]:
    return [{"name": k, **{kk: vv for kk, vv in v.items() if kk in ("description", "artifacts")}}
            for k, v in RECIPES.items()]


def _png_size(path: str) -> Optional[Dict[str, int]]:
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            w, h = struct.unpack(">II", head[16:24])
            return {"width": w, "height": h}
    except OSError:
        pass
    return None


def _generator(project_path: Optional[str], recipe: str, command: Optional[str]) -> Dict[str, Any]:
    return {
        "entry_point": "cli-anything-orcaslicer",
        "harness_version": _pkg.__version__,
        "command": command or f"cli-anything-orcaslicer preview capture --recipe {recipe}",
        "backend": "OrcaSlicer " + backend.get_version(),
    }


def capture(project: Dict[str, Any], project_path: Optional[str] = None, recipe: str = "quick",
            force: bool = False, root_dir: Optional[str] = None, plate: int = 1,
            command: Optional[str] = None) -> Dict[str, Any]:
    """Slice with the real OrcaSlicer and publish a capture bundle (cached by project fingerprint)."""
    if recipe not in RECIPES:
        raise ValueError(f"Unknown preview recipe '{recipe}'. Use one of: {', '.join(RECIPES)}.")
    spec = RECIPES[recipe]
    fp = proj_mod.fingerprint(project)
    options = {"plate": plate}
    prep = pb.prepare_bundle(SOFTWARE, recipe, "capture", fp, options=options,
                             harness_version=_pkg.__version__, project_path=project_path,
                             root_dir=root_dir, force=force)
    if prep["cached"]:
        manifest = prep["manifest"]
        manifest["cached"] = True
        return manifest

    bundle_dir, art_dir = prep["bundle_dir"], prep["artifacts_dir"]
    work = os.path.join(bundle_dir, "_work")
    threemf = os.path.join(work, "project.3mf")
    try:
        result = slicer.slice_project(project, project_path=project_path, outdir=work,
                                      export_3mf=threemf, plate=0, record=False)
        plate_info = next((p for p in result["plates"] if p["plate"] == plate), None)
        if plate_info is None:
            raise IndexError(f"Plate {plate} was not produced (plates: {[p['plate'] for p in result['plates']]}).")

        artifacts: List[Dict[str, Any]] = []
        with zipfile.ZipFile(threemf) as zf:
            for art_id, member_tpl, label in spec["thumbnails"]:
                member = "Metadata/" + member_tpl.format(n=plate)
                if member not in zf.namelist():
                    continue
                target = os.path.join(art_dir, f"{art_id}.png")
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                artifacts.append(pb.artifact_record(
                    bundle_dir, target, art_id, "hero" if art_id == "hero" else "gallery",
                    "image", label, "image/png", **(_png_size(target) or {})))
        if not artifacts:
            raise RuntimeError("OrcaSlicer's 3MF contained no plate thumbnails.")

        if "statistics" in spec["extras"] and plate_info.get("statistics"):
            target = os.path.join(art_dir, "statistics.json")
            shutil.copyfile(plate_info["statistics"], target)
            artifacts.append(pb.artifact_record(bundle_dir, target, "statistics", "inspection", "json",
                                                "OrcaSlicer slicing statistics", "application/json"))
        if "project" in spec["extras"]:
            target = os.path.join(art_dir, "project.3mf")
            shutil.copyfile(threemf, target)
            artifacts.append(pb.artifact_record(
                bundle_dir, target, "project", "project", "model", "Sliced OrcaSlicer 3MF project",
                "model/3mf"))

        metrics = {
            "layers": plate_info.get("layers"),
            "print_time_s": plate_info.get("print_time_s"),
            "filament_g": plate_info.get("filament_g"),
            "filament_mm": plate_info.get("filament_mm"),
            "max_z_mm": plate_info.get("max_z"),
            "gcode_bytes": plate_info.get("bytes"),
            "models": len(project["models"]),
        }
        summary = {
            "headline": (f"Sliced {len(project['models'])} model(s): {plate_info.get('layers')} layers, "
                         f"{plate_info.get('print_time')}, {plate_info.get('filament_g')} g filament"),
            "facts": {**metrics, "recipe": recipe, "plate": plate,
                      "machine": project["profiles"]["machine"],
                      "process": project["profiles"]["process"],
                      "filaments": project["profiles"]["filaments"],
                      "overrides": {f"{k}.{key}": v for k in project["overrides"]
                                    for key, v in sorted(project["overrides"][k].items())},
                      "transforms": [proj_mod.describe_transform(t) for t in project["transforms"]]},
            "warnings": result["warnings"],
            "next_actions": [
                "Inspect hero.png / top.png to confirm orientation and placement",
                "Check print time and filament use, then run 'slice run' for the final G-code",
            ],
        }
        manifest = pb.finalize_bundle(
            bundle_dir, prep["bundle_id"], "capture", SOFTWARE, recipe,
            source={"project_path": os.path.abspath(project_path) if project_path else None,
                    "project_fingerprint": fp,
                    "models": [m["path"] for m in project["models"]]},
            artifacts=artifacts, summary=summary, cache_key=prep["cache_key"],
            generator=_generator(project_path, recipe, command),
            warnings=result["warnings"], metrics=metrics,
            context={"plate": plate, "orcaslicer_version": result["orcaslicer_version"],
                     "preview_scope": "model-on-plate renders (not toolpaths); toolpath facts are in metrics"},
            labels=["slicer", "fdm"])
    except Exception:
        shutil.rmtree(bundle_dir, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
    manifest["cached"] = False
    return manifest


def latest(project_path: Optional[str] = None, recipe: Optional[str] = None,
           root_dir: Optional[str] = None, bundle_kind: Optional[str] = None) -> Dict[str, Any]:
    """Return the newest existing bundle. Never renders."""
    manifest = pb.find_latest_manifest(SOFTWARE, recipe=recipe, bundle_kind=bundle_kind,
                                       project_path=project_path, root_dir=root_dir)
    if not manifest:
        raise FileNotFoundError(
            "No preview bundle found" + (f" for recipe '{recipe}'" if recipe else "") +
            ". Run 'preview capture' first.")
    return manifest


_DIFF_FIELDS = ("layers", "print_time_s", "filament_g", "filament_mm", "max_z_mm", "gcode_bytes")


def diff(project: Dict[str, Any], project_path: Optional[str] = None, recipe: str = "quick",
         base_bundle_dir: Optional[str] = None, root_dir: Optional[str] = None,
         command: Optional[str] = None) -> Dict[str, Any]:
    """Capture the current project and publish a comparison bundle against a baseline bundle."""
    if base_bundle_dir:
        mpath = os.path.join(os.path.abspath(base_bundle_dir), "manifest.json")
        if not os.path.isfile(mpath):
            raise FileNotFoundError(f"No manifest.json in {base_bundle_dir}")
        import json
        with open(mpath, "r", encoding="utf-8") as fh:
            base = json.load(fh)
        base["_bundle_dir"] = os.path.abspath(base_bundle_dir)
    else:
        base = latest(project_path, recipe=recipe, root_dir=root_dir, bundle_kind="capture")
    head = capture(project, project_path=project_path, recipe=recipe, root_dir=root_dir)

    deltas: Dict[str, Any] = {}
    for field in _DIFF_FIELDS:
        b, h = base.get("metrics", {}).get(field), head.get("metrics", {}).get(field)
        if isinstance(b, (int, float)) and isinstance(h, (int, float)):
            deltas[field] = {"before": b, "after": h, "delta": round(h - b, 4),
                             "pct": round((h - b) / b * 100, 2) if b else None}
    changed = {k: v for k, v in deltas.items() if v["delta"] != 0}

    fp = proj_mod.fingerprint(project)
    prep = pb.prepare_bundle(SOFTWARE, "diff", "diff", fp + base["bundle_id"] + head["bundle_id"],
                             options={"recipe": recipe}, harness_version=_pkg.__version__,
                             project_path=project_path, root_dir=root_dir, force=True)
    bundle_dir, art_dir = prep["bundle_dir"], prep["artifacts_dir"]
    artifacts = []
    diff_json = pb.write_json(os.path.join(art_dir, "diff.json"),
                              {"base_bundle": base["bundle_id"], "head_bundle": head["bundle_id"],
                               "deltas": deltas, "changed": sorted(changed)})
    artifacts.append(pb.artifact_record(bundle_dir, diff_json, "diff", "inspection", "json",
                                        "Metric deltas (before -> after)", "application/json"))
    for tag, man in (("before", base), ("after", head)):
        for art in man.get("artifacts", []):
            if art.get("artifact_id") == "hero":
                src = os.path.join(man["_bundle_dir"], art["path"])
                if os.path.isfile(src):
                    target = os.path.join(art_dir, f"{tag}_hero.png")
                    shutil.copyfile(src, target)
                    artifacts.append(pb.artifact_record(
                        bundle_dir, target, f"{tag}_hero", "gallery", "image",
                        f"{tag.title()} isometric render", "image/png", **(_png_size(target) or {})))
    headline = ("No measurable change vs baseline" if not changed else
                "Changed: " + ", ".join(f"{k} {v['before']}→{v['after']}" for k, v in changed.items()))
    summary = {"headline": headline, "facts": {"changed_fields": sorted(changed)},
               "warnings": [], "next_actions": ["Review diff.json and before/after renders"]}
    manifest = pb.finalize_bundle(
        bundle_dir, prep["bundle_id"], "diff", SOFTWARE, "diff",
        source={"project_path": os.path.abspath(project_path) if project_path else None,
                "project_fingerprint": fp},
        artifacts=artifacts, summary=summary, cache_key=prep["cache_key"],
        generator=_generator(project_path, "diff", command),
        metrics={"changed_fields": len(changed)},
        source_bundles=[{"bundle_id": base["bundle_id"], "bundle_dir": base["_bundle_dir"], "role": "before"},
                        {"bundle_id": head["bundle_id"], "bundle_dir": head["_bundle_dir"], "role": "after"}],
        labels=["slicer", "diff"])
    manifest["deltas"] = deltas
    return manifest
