"""Preview bundle generation for the Openscreen harness."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.preview_bundle import (
    append_live_trajectory,
    artifact_record,
    bundle_root,
    finalize_bundle,
    find_latest_manifest,
    fingerprint_data,
    fingerprint_file,
    prepare_bundle,
)
from . import export as export_mod
from . import media as media_mod
from .session import Session

HARNESS_VERSION = "1.0.0"

RECIPES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "description": "Render a review clip and extract sampled frames",
        "thumbnail_times": [0.0, 0.25, 0.5, 0.75, 0.95],
    },
}


def list_recipes() -> List[Dict[str, Any]]:
    """Return available preview recipes."""
    return [
        {
            "name": name,
            "description": config["description"],
            "bundle_kind": "capture",
            "artifacts": ["preview-clip", "hero", "gallery"],
        }
        for name, config in RECIPES.items()
    ]


def _project_fingerprint(session: Session) -> str:
    if not session.is_open:
        raise RuntimeError("No project is open")
    media = session.data.get("media", {})
    source_video = media.get("screenVideoPath") or session.data.get("videoPath")
    payload: Dict[str, Any] = {
        "project_path": session.project_path,
        "session_id": session.session_id,
        "project_data": session.data,
    }
    if source_video and os.path.isfile(source_video):
        payload["source_video"] = {
            "path": os.path.abspath(source_video),
            "fingerprint": fingerprint_file(source_video),
        }
    return fingerprint_data(payload)


def _metrics(session: Session) -> Dict[str, Any]:
    editor = session.editor
    return {
        "zoom_region_count": len(editor.get("zoomRegions", [])),
        "speed_region_count": len(editor.get("speedRegions", [])),
        "trim_region_count": len(editor.get("trimRegions", [])),
        "annotation_count": len(editor.get("annotationRegions", [])),
        "aspect_ratio": editor.get("aspectRatio", "16:9"),
        "padding": editor.get("padding", 50),
        "background": editor.get("wallpaper", "gradient_dark"),
    }


def _trajectory_dir(session: Session, recipe: str, root_dir: Optional[str] = None) -> str:
    return str(
        bundle_root(
            "openscreen",
            recipe,
            project_path=session.project_path,
            root_dir=root_dir,
        ).resolve()
    )


def _attach_trajectory_ref(manifest: Dict[str, Any]) -> Dict[str, Any]:
    bundle_dir = manifest.get("_bundle_dir")
    context = manifest.get("context") or {}
    trajectory_ref = context.get("trajectory_path")
    if bundle_dir and trajectory_ref:
        trajectory_path = (Path(str(bundle_dir)) / str(trajectory_ref)).resolve()
        if trajectory_path.is_file():
            manifest["_trajectory_path"] = str(trajectory_path)
    return manifest


def capture(
    session: Session,
    recipe: str = "quick",
    *,
    root_dir: Optional[str] = None,
    force: bool = False,
    command: Optional[str] = None,
) -> Dict[str, Any]:
    """Render a preview bundle for the active Openscreen project."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    if recipe not in RECIPES:
        raise ValueError(
            f"Unknown preview recipe: {recipe!r}. Available: {', '.join(sorted(RECIPES))}"
        )

    config = RECIPES[recipe]
    source_fingerprint = _project_fingerprint(session)
    prepared = prepare_bundle(
        software="openscreen",
        recipe=recipe,
        bundle_kind="capture",
        source_fingerprint=source_fingerprint,
        options=config,
        harness_version=HARNESS_VERSION,
        project_path=session.project_path,
        root_dir=root_dir,
        force=force,
    )
    if prepared["cached"]:
        manifest = dict(prepared["manifest"])
        manifest["cached"] = True
        return _attach_trajectory_ref(manifest)

    bundle_dir = prepared["bundle_dir"]
    artifacts_dir = prepared["artifacts_dir"]
    trajectory_dir = _trajectory_dir(session, recipe, root_dir=root_dir)
    trajectory_rel = os.path.relpath(Path(trajectory_dir) / "trajectory.json", Path(bundle_dir))
    preview_clip = os.path.join(artifacts_dir, "preview.mp4")

    render_result = export_mod.render(session, preview_clip)
    clip_meta = media_mod.probe(preview_clip)
    duration_s = float(clip_meta.get("duration", render_result.get("duration", 0.0)) or 0.0)
    width = int(clip_meta.get("width", render_result.get("width", 0)) or 0)
    height = int(clip_meta.get("height", render_result.get("height", 0)) or 0)

    warnings: List[str] = []
    artifacts = [
        artifact_record(
            bundle_dir,
            preview_clip,
            artifact_id="clip",
            role="preview-clip",
            kind="clip",
            label="Rendered preview clip",
            width=width or None,
            height=height or None,
            duration_s=round(duration_s, 3),
            segments_rendered=render_result.get("segments_rendered"),
        )
    ]

    for index, ratio in enumerate(config["thumbnail_times"]):
        capture_time = duration_s * ratio if duration_s > 0 else 0.0
        image_path = os.path.join(artifacts_dir, f"frame_{index + 1:02d}.jpg")
        try:
            media_mod.extract_thumbnail(preview_clip, image_path, capture_time)
        except Exception as exc:
            warnings.append(f"frame sample {index + 1} failed: {exc}")
            continue
        role = "hero" if abs(ratio - 0.5) < 1e-9 else "gallery"
        label = "Midpoint frame" if role == "hero" else f"Sample frame {index + 1}"
        artifacts.append(
            artifact_record(
                bundle_dir,
                image_path,
                artifact_id=f"frame_{index + 1:02d}",
                role=role,
                kind="image",
                label=label,
                time_s=round(capture_time, 3),
            )
        )

    metrics = _metrics(session)
    summary = {
        "headline": (
            f"Openscreen {recipe} preview rendered"
            + (f" at {width}x{height}" if width and height else "")
        ),
        "facts": {
            "recipe": recipe,
            "duration_s": round(duration_s, 3),
            "resolution": f"{width}x{height}" if width and height else "unknown",
            **metrics,
        },
        "warnings": warnings,
        "next_actions": [
            "Inspect the review clip for zoom timing, speed ramps, and padding.",
            "Open the bundle in cli-hub previews html for a gallery layout.",
        ],
    }

    source_video = session.data.get("media", {}).get("screenVideoPath") or session.data.get("videoPath")
    manifest = finalize_bundle(
        bundle_dir=bundle_dir,
        bundle_id=prepared["bundle_id"],
        bundle_kind="capture",
        software="openscreen",
        recipe=recipe,
        source={
            "project_path": session.project_path,
            "project_name": os.path.basename(session.project_path) if session.project_path else None,
            "project_fingerprint": source_fingerprint,
            "source_video": source_video,
            "session_id": session.session_id,
        },
        artifacts=artifacts,
        summary=summary,
        cache_key=prepared["cache_key"],
        generator={
            "entry_point": "cli-anything-openscreen",
            "harness_version": HARNESS_VERSION,
            "command": command or f"cli-anything-openscreen preview capture --recipe {recipe}",
        },
        status="partial" if warnings else "ok",
        warnings=warnings or None,
        context={
            "editor": {"aspectRatio": metrics["aspect_ratio"], "background": metrics["background"]},
            "trajectory_path": trajectory_rel,
        },
        metrics=metrics,
        labels=["video", "screen-recording", "preview"],
    )
    trajectory = append_live_trajectory(
        trajectory_dir,
        software="openscreen",
        recipe=recipe,
        bundle_manifest=manifest,
        publish_reason="capture",
        project_path=session.project_path,
        project_name=os.path.basename(session.project_path) if session.project_path else None,
        session_name=f"{os.path.splitext(os.path.basename(session.project_path or 'untitled'))[0]}-{recipe}",
        command=command,
        stage_label="preview-capture",
    )
    manifest["_trajectory_path"] = trajectory["_trajectory_path"]
    manifest["cached"] = False
    return manifest


def latest(
    *,
    project_path: Optional[str] = None,
    recipe: Optional[str] = None,
    root_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the latest preview bundle manifest for Openscreen."""
    manifest = find_latest_manifest(
        software="openscreen",
        recipe=recipe,
        bundle_kind="capture",
        project_path=project_path,
        root_dir=root_dir,
    )
    if manifest is None:
        raise FileNotFoundError("No Openscreen preview bundle found")
    return _attach_trajectory_ref(manifest)
