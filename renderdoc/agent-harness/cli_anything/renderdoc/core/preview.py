"""Preview bundle generation for the RenderDoc harness."""

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
    write_json,
)
from . import actions as actions_mod
from . import diff as diff_mod
from . import pipeline as pipeline_mod
from . import textures as textures_mod

HARNESS_VERSION = "0.1.0"

RECIPES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "description": "Capture thumbnail, output targets, and pipeline snapshot",
        "max_thumb_dim": 768,
    },
}


def list_recipes() -> List[Dict[str, Any]]:
    """Return available preview recipes."""
    recipes = [
        {
            "name": name,
            "description": config["description"],
            "bundle_kind": "capture",
            "artifacts": ["hero", "gallery", "metadata"],
        }
        for name, config in RECIPES.items()
    ]
    recipes.append(
        {
            "name": "diff",
            "description": "Compare two pipeline states and their output targets",
            "bundle_kind": "diff",
            "artifacts": ["gallery", "diff", "metadata"],
        }
    )
    return recipes


def _default_event_id(handle) -> Optional[int]:
    drawcalls = actions_mod.get_drawcalls_only(handle.controller)
    if not drawcalls:
        return None
    return int(drawcalls[-1]["eventId"])


def _compact_diff(obj: Any) -> Any:
    if isinstance(obj, dict):
        pruned = {}
        for key, value in obj.items():
            if value == "SAME":
                continue
            compacted = _compact_diff(value)
            if compacted is not None:
                pruned[key] = compacted
        return pruned or None
    if isinstance(obj, list):
        values = [_compact_diff(item) for item in obj if item != "SAME"]
        values = [item for item in values if item is not None]
        return values or None
    return obj


def _count_differences(obj: Any) -> int:
    if isinstance(obj, dict):
        return sum(_count_differences(value) for value in obj.values()) or len(obj)
    if isinstance(obj, list):
        return sum(_count_differences(item) for item in obj) or len(obj)
    return 1


def _trajectory_dir(capture_path: str, recipe: str, root_dir: Optional[str] = None) -> str:
    return str(
        bundle_root(
            "renderdoc",
            recipe,
            project_path=capture_path,
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
    handle,
    capture_path: str,
    recipe: str = "quick",
    *,
    event_id: Optional[int] = None,
    root_dir: Optional[str] = None,
    force: bool = False,
    command: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a capture preview bundle for a RenderDoc capture."""
    if recipe not in RECIPES:
        raise ValueError(
            f"Unknown preview recipe: {recipe!r}. Available: {', '.join(sorted(RECIPES))}"
        )

    config = RECIPES[recipe]
    source_fingerprint = fingerprint_file(capture_path)
    prepared = prepare_bundle(
        software="renderdoc",
        recipe=recipe,
        bundle_kind="capture",
        source_fingerprint=source_fingerprint,
        options={"event_id": event_id or "auto", **config},
        harness_version=HARNESS_VERSION,
        project_path=capture_path,
        root_dir=root_dir,
        force=force,
    )
    if prepared["cached"]:
        manifest = dict(prepared["manifest"])
        manifest["cached"] = True
        return _attach_trajectory_ref(manifest)

    bundle_dir = prepared["bundle_dir"]
    artifacts_dir = prepared["artifacts_dir"]
    trajectory_dir = _trajectory_dir(capture_path, recipe, root_dir=root_dir)
    trajectory_rel = os.path.relpath(Path(trajectory_dir) / "trajectory.json", Path(bundle_dir))
    warnings: List[str] = []
    artifacts: List[Dict[str, Any]] = []
    metadata = handle.metadata()
    action_summary = actions_mod.action_summary(handle.controller)

    hero_path = os.path.join(artifacts_dir, "hero.png")
    thumb_result = handle.thumbnail(hero_path, config["max_thumb_dim"])
    if thumb_result.get("error"):
        warnings.append(str(thumb_result["error"]))
    elif os.path.isfile(hero_path):
        artifacts.append(
            artifact_record(
                bundle_dir,
                hero_path,
                artifact_id="hero",
                role="hero",
                kind="image",
                label="Capture thumbnail",
                renderdoc_format=thumb_result.get("format"),
            )
        )

    chosen_event = event_id or _default_event_id(handle)
    output_count = 0
    if chosen_event is not None:
        outputs_dir = os.path.join(artifacts_dir, "outputs")
        output_results = textures_mod.save_action_outputs(handle.controller, chosen_event, outputs_dir, file_format="png")
        for index, item in enumerate(output_results):
            if item.get("error") or not item.get("path") or not os.path.isfile(item["path"]):
                warnings.append(item.get("error", f"missing output target {index}"))
                continue
            output_count += 1
            artifacts.append(
                artifact_record(
                    bundle_dir,
                    item["path"],
                    artifact_id=f"output_{index:02d}",
                    role="gallery",
                    kind="image",
                    label=item.get("label", f"Output {index}"),
                )
            )

        pipeline_state = pipeline_mod.get_pipeline_state(handle.controller, chosen_event)
        pipeline_path = os.path.join(artifacts_dir, "pipeline_state.json")
        write_json(pipeline_path, pipeline_state)
        artifacts.append(
            artifact_record(
                bundle_dir,
                pipeline_path,
                artifact_id="pipeline_state",
                role="metadata",
                kind="json",
                label=f"Pipeline state at event {chosen_event}",
                media_type="application/json",
            )
        )
    else:
        warnings.append("No drawcall event found; skipped output-target and pipeline capture.")

    summary_path = os.path.join(artifacts_dir, "action_summary.json")
    write_json(summary_path, action_summary)
    artifacts.append(
        artifact_record(
            bundle_dir,
            summary_path,
            artifact_id="action_summary",
            role="metadata",
            kind="json",
            label="Action summary",
            media_type="application/json",
        )
    )

    summary = {
        "headline": f"RenderDoc preview captured from {os.path.basename(capture_path)}",
        "facts": {
            "recipe": recipe,
            "api": metadata.get("api"),
            "event_id": chosen_event,
            "drawcalls": action_summary.get("drawcalls", 0),
            "output_targets": output_count,
        },
        "warnings": warnings,
        "next_actions": [
            "Inspect the hero thumbnail for a quick capture-level sanity check.",
            "Inspect output targets and pipeline_state.json for the selected event.",
        ],
    }

    manifest = finalize_bundle(
        bundle_dir=bundle_dir,
        bundle_id=prepared["bundle_id"],
        bundle_kind="capture",
        software="renderdoc",
        recipe=recipe,
        source={
            "capture_path": os.path.abspath(capture_path),
            "capture_name": os.path.basename(capture_path),
            "capture_fingerprint": source_fingerprint,
        },
        artifacts=artifacts,
        summary=summary,
        cache_key=prepared["cache_key"],
        generator={
            "entry_point": "cli-anything-renderdoc",
            "harness_version": HARNESS_VERSION,
            "command": command or f"cli-anything-renderdoc -c {capture_path} preview capture --recipe {recipe}",
        },
        status="partial" if warnings else "ok",
        warnings=warnings or None,
        context={"event_id": chosen_event, "trajectory_path": trajectory_rel},
        metrics={
            "drawcalls": action_summary.get("drawcalls", 0),
            "output_targets": output_count,
        },
        labels=["gpu", "capture", "preview"],
    )
    trajectory = append_live_trajectory(
        trajectory_dir,
        software="renderdoc",
        recipe=recipe,
        bundle_manifest=manifest,
        publish_reason="capture",
        project_path=os.path.abspath(capture_path),
        project_name=os.path.basename(capture_path),
        session_name=f"{os.path.splitext(os.path.basename(capture_path))[0]}-{recipe}",
        command=command,
        stage_label=f"event-{chosen_event}" if chosen_event is not None else "capture",
        note=f"RenderDoc capture preview for event {chosen_event}" if chosen_event is not None else None,
    )
    manifest["_trajectory_path"] = trajectory["_trajectory_path"]
    manifest["cached"] = False
    return manifest


def diff(
    handle_a,
    capture_path_a: str,
    event_a: int,
    handle_b,
    capture_path_b: str,
    event_b: int,
    *,
    compact: bool = True,
    root_dir: Optional[str] = None,
    force: bool = False,
    command: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a diff preview bundle for two RenderDoc events."""
    source_fingerprint = fingerprint_data(
        {
            "capture_a": fingerprint_file(capture_path_a),
            "event_a": event_a,
            "capture_b": fingerprint_file(capture_path_b),
            "event_b": event_b,
        }
    )
    prepared = prepare_bundle(
        software="renderdoc",
        recipe="diff",
        bundle_kind="diff",
        source_fingerprint=source_fingerprint,
        options={"compact": compact, "event_a": event_a, "event_b": event_b},
        harness_version=HARNESS_VERSION,
        project_path=capture_path_a,
        root_dir=root_dir,
        force=force,
    )
    if prepared["cached"]:
        manifest = dict(prepared["manifest"])
        manifest["cached"] = True
        return _attach_trajectory_ref(manifest)

    bundle_dir = prepared["bundle_dir"]
    artifacts_dir = prepared["artifacts_dir"]
    trajectory_dir = _trajectory_dir(capture_path_a, "diff", root_dir=root_dir)
    trajectory_rel = os.path.relpath(Path(trajectory_dir) / "trajectory.json", Path(bundle_dir))
    warnings: List[str] = []
    artifacts: List[Dict[str, Any]] = []

    thumb_a = os.path.join(artifacts_dir, "capture_a_thumb.png")
    thumb_a_result = handle_a.thumbnail(thumb_a, 512)
    if not thumb_a_result.get("error") and os.path.isfile(thumb_a):
        artifacts.append(
            artifact_record(
                bundle_dir,
                thumb_a,
                artifact_id="capture_a_thumb",
                role="gallery",
                kind="image",
                label=f"{os.path.basename(capture_path_a)} thumbnail",
            )
        )

    thumb_b = os.path.join(artifacts_dir, "capture_b_thumb.png")
    thumb_b_result = handle_b.thumbnail(thumb_b, 512)
    if not thumb_b_result.get("error") and os.path.isfile(thumb_b):
        artifacts.append(
            artifact_record(
                bundle_dir,
                thumb_b,
                artifact_id="capture_b_thumb",
                role="gallery",
                kind="image",
                label=f"{os.path.basename(capture_path_b)} thumbnail",
            )
        )

    outputs_a = textures_mod.save_action_outputs(
        handle_a.controller,
        event_a,
        os.path.join(artifacts_dir, "outputs_a"),
        file_format="png",
    )
    outputs_b = textures_mod.save_action_outputs(
        handle_b.controller,
        event_b,
        os.path.join(artifacts_dir, "outputs_b"),
        file_format="png",
    )
    for side, output_results in (("A", outputs_a), ("B", outputs_b)):
        for index, item in enumerate(output_results):
            if item.get("error") or not item.get("path") or not os.path.isfile(item["path"]):
                warnings.append(item.get("error", f"missing output target {side}{index}"))
                continue
            artifacts.append(
                artifact_record(
                    bundle_dir,
                    item["path"],
                    artifact_id=f"{side.lower()}_output_{index:02d}",
                    role="gallery",
                    kind="image",
                    label=f"{side} {item.get('label', f'Output {index}')}",
                )
            )

    diff_data = diff_mod.diff_pipeline(handle_a.controller, event_a, handle_b.controller, event_b)
    if compact:
        diff_data = _compact_diff(diff_data) or {}

    diff_path = os.path.join(artifacts_dir, "pipeline_diff.json")
    write_json(diff_path, diff_data)
    artifacts.append(
        artifact_record(
            bundle_dir,
            diff_path,
            artifact_id="pipeline_diff",
            role="diff",
            kind="json",
            label="Pipeline diff",
            media_type="application/json",
        )
    )

    pipeline_a = pipeline_mod.get_pipeline_state(handle_a.controller, event_a)
    pipeline_a_path = os.path.join(artifacts_dir, "pipeline_a.json")
    write_json(pipeline_a_path, pipeline_a)
    artifacts.append(
        artifact_record(
            bundle_dir,
            pipeline_a_path,
            artifact_id="pipeline_a",
            role="metadata",
            kind="json",
            label=f"Pipeline state A at event {event_a}",
            media_type="application/json",
        )
    )

    pipeline_b = pipeline_mod.get_pipeline_state(handle_b.controller, event_b)
    pipeline_b_path = os.path.join(artifacts_dir, "pipeline_b.json")
    write_json(pipeline_b_path, pipeline_b)
    artifacts.append(
        artifact_record(
            bundle_dir,
            pipeline_b_path,
            artifact_id="pipeline_b",
            role="metadata",
            kind="json",
            label=f"Pipeline state B at event {event_b}",
            media_type="application/json",
        )
    )

    diff_count = _count_differences(diff_data)
    summary = {
        "headline": f"RenderDoc diff bundle created for events {event_a} vs {event_b}",
        "facts": {
            "event_a": event_a,
            "event_b": event_b,
            "capture_a": os.path.basename(capture_path_a),
            "capture_b": os.path.basename(capture_path_b),
            "difference_count": diff_count,
        },
        "warnings": warnings,
        "next_actions": [
            "Inspect pipeline_diff.json for resource, shader, and state changes.",
            "Compare A/B output-target images for visible regressions.",
        ],
    }

    manifest = finalize_bundle(
        bundle_dir=bundle_dir,
        bundle_id=prepared["bundle_id"],
        bundle_kind="diff",
        software="renderdoc",
        recipe="diff",
        source={
            "capture_path": os.path.abspath(capture_path_a),
            "capture_name": os.path.basename(capture_path_a),
            "capture_fingerprint": fingerprint_file(capture_path_a),
        },
        artifacts=artifacts,
        summary=summary,
        cache_key=prepared["cache_key"],
        generator={
            "entry_point": "cli-anything-renderdoc",
            "harness_version": HARNESS_VERSION,
            "command": command
            or f"cli-anything-renderdoc -c {capture_path_a} preview diff {event_a} {event_b} --capture-b {capture_path_b}",
        },
        status="partial" if warnings else "ok",
        warnings=warnings or None,
        context={"event_a": event_a, "event_b": event_b, "trajectory_path": trajectory_rel},
        metrics={"difference_count": diff_count},
        labels=["gpu", "capture", "diff", "preview"],
        source_bundles=[
            {"capture_path": os.path.abspath(capture_path_a), "event_id": event_a},
            {"capture_path": os.path.abspath(capture_path_b), "event_id": event_b},
        ],
    )
    trajectory = append_live_trajectory(
        trajectory_dir,
        software="renderdoc",
        recipe="diff",
        bundle_manifest=manifest,
        publish_reason="diff",
        project_path=os.path.abspath(capture_path_a),
        project_name=os.path.basename(capture_path_a),
        session_name=f"{os.path.splitext(os.path.basename(capture_path_a))[0]}-diff",
        command=command,
        stage_label=f"diff-{event_a}-vs-{event_b}",
        note=f"Pipeline diff for events {event_a} vs {event_b}",
    )
    manifest["_trajectory_path"] = trajectory["_trajectory_path"]
    manifest["cached"] = False
    return manifest


def latest(
    *,
    project_path: Optional[str] = None,
    recipe: Optional[str] = None,
    bundle_kind: Optional[str] = None,
    root_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the latest preview bundle manifest for RenderDoc."""
    manifest = find_latest_manifest(
        software="renderdoc",
        recipe=recipe,
        bundle_kind=bundle_kind,
        project_path=project_path,
        root_dir=root_dir,
    )
    if manifest is None:
        raise FileNotFoundError("No RenderDoc preview bundle found")
    return _attach_trajectory_ref(manifest)
