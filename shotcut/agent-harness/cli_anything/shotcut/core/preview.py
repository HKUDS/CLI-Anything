"""Preview bundle generation for the Shotcut harness."""

from __future__ import annotations

import json
import os
import re
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils import mlt_xml
from ..utils.preview_bundle import (
    append_live_trajectory,
    artifact_record,
    build_live_history_item,
    finalize_bundle,
    find_latest_manifest,
    fingerprint_data,
    fingerprint_file,
    live_trajectory_path,
    load_live_trajectory,
    prepare_bundle,
    summarize_trajectory,
)
from . import export as export_mod
from . import media as media_mod
from .session import Session

HARNESS_VERSION = "1.0.0"
LIVE_PROTOCOL_VERSION = "preview-live/v1"
DEFAULT_REFRESH_HINT_MS = 1500
DEFAULT_SOURCE_POLL_MS = 500
MIN_SOURCE_POLL_MS = 250

RECIPES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "description": "Fast low-res preview clip plus sampled frames",
        "preset": "h264-fast",
        "width": 640,
        "height": 360,
        "thumbnail_width": 640,
        "thumbnail_height": 360,
        "sample_ratios": [0.0, 0.25, 0.5, 0.75, 0.95],
    },
}


def list_recipes() -> List[Dict[str, Any]]:
    """Return available preview recipes."""
    recipes = []
    for name, config in RECIPES.items():
        recipes.append(
            {
                "name": name,
                "description": config["description"],
                "bundle_kind": "capture",
                "artifacts": ["preview-clip", "hero", "gallery"],
                "resolution": f"{config['width']}x{config['height']}",
            }
        )
    return recipes


def _seconds_to_timecode(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(total_ms, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    whole_seconds, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{ms:03d}"


def _project_fingerprint(session: Session) -> str:
    if not session.is_open:
        raise RuntimeError("No project is open")
    if session.project_path and not session.is_modified and os.path.isfile(session.project_path):
        return fingerprint_data(
            {
                "project_path": os.path.abspath(session.project_path),
                "project_file": fingerprint_file(session.project_path),
            }
        )
    payload: Dict[str, Any] = {
        "project_path": os.path.abspath(session.project_path) if session.project_path else "",
        "xml": mlt_xml.mlt_to_string(session.root),
    }
    if not session.project_path:
        payload["session_id"] = session.session_id
    return fingerprint_data(payload)


def _metrics(session: Session) -> Dict[str, Any]:
    tractor = session.get_main_tractor()
    producers = mlt_xml.get_all_producers(session.root)
    filters = mlt_xml.get_all_filters(session.root)
    renderable_producers = [
        producer
        for producer in producers
        if mlt_xml.get_property(producer, "resource", "") not in ("", "0")
        and mlt_xml.get_property(producer, "mlt_service", "") not in ("color", "colour")
    ]
    return {
        "track_count": len(mlt_xml.get_tractor_tracks(tractor)),
        "producer_count": len(renderable_producers),
        "filter_count": len(filters),
        "profile": session.get_profile(),
    }


def capture(
    session: Session,
    recipe: str = "quick",
    *,
    root_dir: Optional[str] = None,
    force: bool = False,
    command: Optional[str] = None,
) -> Dict[str, Any]:
    """Render a preview bundle for the active Shotcut project."""
    if not session.is_open:
        raise RuntimeError("No project is open")
    if recipe not in RECIPES:
        raise ValueError(
            f"Unknown preview recipe: {recipe!r}. Available: {', '.join(sorted(RECIPES))}"
        )

    config = RECIPES[recipe]
    source_fingerprint = _project_fingerprint(session)
    prepared = prepare_bundle(
        software="shotcut",
        recipe=recipe,
        bundle_kind="capture",
        source_fingerprint=source_fingerprint,
        options={k: config[k] for k in ("preset", "width", "height", "sample_ratios")},
        harness_version=HARNESS_VERSION,
        project_path=session.project_path,
        root_dir=root_dir,
        force=force,
    )
    if prepared["cached"]:
        manifest = dict(prepared["manifest"])
        manifest["cached"] = True
        return manifest

    bundle_dir = prepared["bundle_dir"]
    artifacts_dir = prepared["artifacts_dir"]
    preview_clip = os.path.join(artifacts_dir, "preview.mp4")

    render_result = export_mod.render(
        session,
        preview_clip,
        preset=config["preset"],
        width=config["width"],
        height=config["height"],
        overwrite=True,
        prefer_ffmpeg=True,
    )
    clip_meta = media_mod.probe_media(preview_clip)
    duration_s = float(clip_meta.get("duration_seconds", 0.0) or 0.0)
    video_stream = (clip_meta.get("video_streams") or [{}])[0]
    width = int(video_stream.get("width") or config["width"])
    height = int(video_stream.get("height") or config["height"])

    warnings: List[str] = []
    artifacts = [
        artifact_record(
            bundle_dir,
            preview_clip,
            artifact_id="clip",
            role="preview-clip",
            kind="clip",
            label="Quick preview render",
            width=width,
            height=height,
            duration_s=round(duration_s, 3),
            render_method=render_result.get("method"),
        )
    ]

    for index, ratio in enumerate(config["sample_ratios"]):
        capture_time = duration_s * ratio if duration_s > 0 else 0.0
        image_path = os.path.join(artifacts_dir, f"frame_{index + 1:02d}.png")
        try:
            media_mod.generate_thumbnail(
                preview_clip,
                image_path,
                _seconds_to_timecode(capture_time),
                config["thumbnail_width"],
                config["thumbnail_height"],
            )
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
                width=config["thumbnail_width"],
                height=config["thumbnail_height"],
                time_s=round(capture_time, 3),
            )
        )

    metrics = _metrics(session)
    summary = {
        "headline": (
            f"Shotcut {recipe} preview rendered at {width}x{height}"
            + (f" for {duration_s:.2f}s" if duration_s > 0 else "")
        ),
        "facts": {
            "recipe": recipe,
            "resolution": f"{width}x{height}",
            "duration_s": round(duration_s, 3),
            "track_count": metrics["track_count"],
            "producer_count": metrics["producer_count"],
            "filter_count": metrics["filter_count"],
        },
        "warnings": warnings,
        "next_actions": [
            "Inspect the preview clip for pacing, timing, and cut order.",
            "Use cli-hub previews html on the bundle for a richer inspection page.",
        ],
    }

    manifest = finalize_bundle(
        bundle_dir=bundle_dir,
        bundle_id=prepared["bundle_id"],
        bundle_kind="capture",
        software="shotcut",
        recipe=recipe,
        source={
            "project_path": session.project_path,
            "project_name": os.path.basename(session.project_path) if session.project_path else None,
            "project_fingerprint": source_fingerprint,
            "session_id": session.session_id,
        },
        artifacts=artifacts,
        summary=summary,
        cache_key=prepared["cache_key"],
        generator={
            "entry_point": "cli-anything-shotcut",
            "harness_version": HARNESS_VERSION,
            "command": command or f"cli-anything-shotcut preview capture --recipe {recipe}",
        },
        status="partial" if warnings else "ok",
        warnings=warnings or None,
        context={"profile": metrics["profile"]},
        metrics={k: v for k, v in metrics.items() if k != "profile"},
        labels=["video", "timeline", "preview"],
    )
    manifest["cached"] = False
    return manifest


def latest(
    *,
    project_path: Optional[str] = None,
    recipe: Optional[str] = None,
    root_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the latest preview bundle manifest for Shotcut."""
    manifest = find_latest_manifest(
        software="shotcut",
        recipe=recipe,
        bundle_kind="capture",
        project_path=project_path,
        root_dir=root_dir,
    )
    if manifest is None:
        raise FileNotFoundError("No Shotcut preview bundle found")
    return manifest


def _slug(value: str) -> str:
    text = (value or "preview").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "preview"


def _preview_base_dir(project_path: Optional[str] = None, root_dir: Optional[str] = None) -> Path:
    if root_dir:
        return Path(root_dir).expanduser().resolve() / "shotcut"
    if project_path:
        return Path(project_path).expanduser().resolve().parent / ".cli-anything" / "previews" / "shotcut"
    return Path.home() / ".cli-anything" / "previews" / "shotcut"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_poll_ms(value: Optional[int]) -> int:
    try:
        numeric = int(value or DEFAULT_SOURCE_POLL_MS)
    except (TypeError, ValueError):
        numeric = DEFAULT_SOURCE_POLL_MS
    return max(MIN_SOURCE_POLL_MS, numeric)


def _project_file_fingerprint(project_path: Optional[str]) -> Optional[str]:
    if not project_path:
        return None
    resolved = os.path.abspath(project_path)
    if not os.path.isfile(resolved):
        return None
    return fingerprint_file(resolved)


def _live_session_name(session: Session, recipe: str) -> str:
    project_name = Path(session.project_path).stem if session.project_path else session.session_id or "untitled"
    fingerprint_source = {
        "project_path": os.path.abspath(session.project_path) if session.project_path else "",
        "recipe": recipe,
    }
    if not session.project_path:
        fingerprint_source["session_id"] = session.session_id
    suffix = fingerprint_data(
        fingerprint_source
    ).split(":", 1)[-1][:8]
    return f"{_slug(project_name)}-{suffix}-{_slug(recipe)}"


def _live_session_dir(session: Session, recipe: str, root_dir: Optional[str] = None) -> Path:
    return _preview_base_dir(session.project_path, root_dir=root_dir) / "live" / _live_session_name(session, recipe)


def _read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
        fh.write("\n")
    return path


def _merge_nested_dict(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge_nested_dict(base[key], value)
        else:
            base[key] = value
    return base


def _pid_is_running(pid: Any) -> bool:
    try:
        numeric = int(pid)
    except (TypeError, ValueError):
        return False
    if numeric <= 0:
        return False
    try:
        os.kill(numeric, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _terminate_pid(pid: Any) -> bool:
    try:
        numeric = int(pid)
    except (TypeError, ValueError):
        return False
    if numeric <= 0:
        return False
    try:
        os.kill(numeric, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False


def _with_live_refs(session_dir: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    payload["_session_dir"] = str(session_dir.resolve())
    payload["_session_path"] = str((session_dir / "session.json").resolve())
    trajectory_path = live_trajectory_path(session_dir)
    if trajectory_path.is_file():
        payload["_trajectory_path"] = str(trajectory_path.resolve())
    return payload


def _write_live_session_updates(session_dir: Path, updates: Dict[str, Any]) -> Dict[str, Any]:
    payload = _load_existing_live_session(session_dir)
    if not payload:
        raise FileNotFoundError(f"Live preview session not found: {session_dir}")
    _merge_nested_dict(payload, updates)
    payload["updated_at"] = updates.get("updated_at", _now_iso())
    _write_json(session_dir / "session.json", payload)
    return _with_live_refs(session_dir, payload)


def _load_existing_live_session(session_dir: Path) -> Dict[str, Any]:
    session_path = session_dir / "session.json"
    if session_path.is_file():
        return _read_json(session_path)
    return {}


def _update_current_symlink(session_dir: Path, bundle_dir: str) -> Path:
    current_link = session_dir / "current"
    if current_link.is_symlink() or current_link.exists():
        if current_link.is_dir() and not current_link.is_symlink():
            raise RuntimeError(f"Live preview current path is unexpectedly a directory: {current_link}")
        current_link.unlink()
    target = os.path.relpath(Path(bundle_dir).resolve(), session_dir)
    os.symlink(target, current_link, target_is_directory=True)
    return current_link


def _history_item(bundle_manifest: Dict[str, Any]) -> Dict[str, Any]:
    return build_live_history_item(bundle_manifest)


def _publish_live_session(
    session: Session,
    bundle_manifest: Dict[str, Any],
    *,
    recipe: str,
    root_dir: Optional[str] = None,
    refresh_hint_ms: int = DEFAULT_REFRESH_HINT_MS,
    live_mode: Optional[str] = None,
    source_poll_ms: int = DEFAULT_SOURCE_POLL_MS,
    publish_reason: str = "manual",
    command: Optional[str] = None,
) -> Dict[str, Any]:
    session_dir = _live_session_dir(session, recipe, root_dir=root_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    _update_current_symlink(session_dir, bundle_manifest["_bundle_dir"])

    existing = _load_existing_live_session(session_dir)
    now = _now_iso()
    trajectory = append_live_trajectory(
        session_dir,
        software="shotcut",
        recipe=recipe,
        bundle_manifest=bundle_manifest,
        publish_reason=publish_reason,
        project_path=session.project_path,
        project_name=Path(session.project_path).name if session.project_path else "untitled",
        session_name=session_dir.name,
        command=command,
        command_started_at=now,
        command_finished_at=now,
    )
    current_item = dict(trajectory.get("latest_step") or _history_item(bundle_manifest))
    history = [current_item]
    for item in existing.get("history", []):
        if item.get("bundle_id") == current_item["bundle_id"]:
            continue
        history.append(item)
    history = history[:12]

    current_live_mode = live_mode or existing.get("live_mode") or "manual"
    current_source_poll_ms = _normalize_poll_ms(
        source_poll_ms if live_mode is not None or "source_poll_ms" not in existing else existing.get("source_poll_ms")
    )
    root_flag = f" --root-dir {root_dir}" if root_dir else ""
    project_flag = f" --project {session.project_path}" if session.project_path else ""
    poller = dict(existing.get("poller") or {})
    poller["running"] = _pid_is_running(poller.get("pid"))
    source_state = dict(existing.get("source_state") or {})
    project_file_fingerprint = _project_file_fingerprint(session.project_path)
    if session.project_path:
        source_state["source_type"] = "project-file"
        source_state["project_path"] = session.project_path
    if project_file_fingerprint:
        source_state["last_seen_fingerprint"] = project_file_fingerprint
        source_state["last_rendered_fingerprint"] = project_file_fingerprint
        source_state["last_rendered_at"] = now
    source_state["last_publish_reason"] = publish_reason
    trajectory_rel = os.path.relpath(Path(trajectory["_trajectory_path"]).resolve(), session_dir)

    payload = {
        "protocol_version": LIVE_PROTOCOL_VERSION,
        "software": "shotcut",
        "recipe": recipe,
        "status": "active",
        "live_mode": current_live_mode,
        "session_name": session_dir.name,
        "session_id": session.session_id,
        "project_path": session.project_path,
        "project_name": Path(session.project_path).name if session.project_path else "untitled",
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "refresh_hint_ms": int(refresh_hint_ms),
        "source_poll_ms": current_source_poll_ms,
        "preview_root_dir": root_dir,
        "current_link": "current",
        "current_bundle_id": bundle_manifest.get("bundle_id"),
        "current_bundle_dir": bundle_manifest.get("_bundle_dir"),
        "current_manifest_path": bundle_manifest.get("_manifest_path"),
        "current_summary_path": bundle_manifest.get("_summary_path"),
        "current_cached": bool(bundle_manifest.get("cached")),
        "bundle_count": len(history),
        "history": history,
        "trajectory_path": trajectory_rel,
        "trajectory_protocol_version": trajectory.get("protocol_version"),
        "trajectory_step_count": trajectory.get("step_count", 0),
        "current_step_id": trajectory.get("current_step_id"),
        "latest_command": current_item.get("command"),
        "latest_publish_reason": current_item.get("publish_reason", publish_reason),
        "source_state": source_state,
        "poller": poller,
        "publish_command": (
            f"cli-anything-shotcut{project_flag} preview live push --recipe {recipe}{root_flag}"
        ).strip(),
        "watch_command": (
            f"cli-hub previews watch {session_dir} --open --poll-ms {int(refresh_hint_ms)}"
        ),
        "inspect_command": f"cli-hub previews inspect {session_dir}",
        "html_command": f"cli-hub previews html {session_dir}",
        "start_command": (
            f"cli-anything-shotcut{project_flag} preview live start --recipe {recipe} "
            f"--mode {current_live_mode} --source-poll-ms {current_source_poll_ms}{root_flag}"
        ).strip(),
        "monitor_command": (
            f"cli-anything-shotcut preview live monitor --session-dir {session_dir}"
        ),
    }
    _write_json(session_dir / "session.json", payload)
    return _with_live_refs(session_dir, payload)


def live_start(
    session: Session,
    recipe: str = "quick",
    *,
    root_dir: Optional[str] = None,
    force: bool = False,
    refresh_hint_ms: int = DEFAULT_REFRESH_HINT_MS,
    live_mode: str = "poll",
    source_poll_ms: int = DEFAULT_SOURCE_POLL_MS,
    command: Optional[str] = None,
    publish_reason: str = "live-start",
) -> Dict[str, Any]:
    """Capture a preview and publish it into a live session."""
    if live_mode not in {"poll", "manual"}:
        raise ValueError("live_mode must be 'poll' or 'manual'")
    if live_mode == "poll" and not session.project_path:
        raise RuntimeError("Poll mode requires a saved project path")
    bundle_manifest = capture(
        session,
        recipe=recipe,
        root_dir=root_dir,
        force=force,
        command=command,
    )
    live_payload = _publish_live_session(
        session,
        bundle_manifest,
        recipe=recipe,
        root_dir=root_dir,
        refresh_hint_ms=refresh_hint_ms,
        live_mode=live_mode,
        source_poll_ms=source_poll_ms,
        publish_reason=publish_reason,
        command=command,
    )
    live_payload["bundle"] = {
        "bundle_id": bundle_manifest.get("bundle_id"),
        "bundle_dir": bundle_manifest.get("_bundle_dir"),
        "manifest_path": bundle_manifest.get("_manifest_path"),
        "cached": bool(bundle_manifest.get("cached")),
    }
    return live_payload


def live_push(
    session: Session,
    recipe: str = "quick",
    *,
    root_dir: Optional[str] = None,
    force: bool = False,
    refresh_hint_ms: int = DEFAULT_REFRESH_HINT_MS,
    source_poll_ms: int = DEFAULT_SOURCE_POLL_MS,
    command: Optional[str] = None,
    publish_reason: str = "manual-push",
) -> Dict[str, Any]:
    """Publish a fresh preview bundle into the current live session."""
    existing_mode: Optional[str] = None
    try:
        existing_mode = live_status(session, recipe=recipe, root_dir=root_dir).get("live_mode")
    except FileNotFoundError:
        existing_mode = "manual"
    return live_start(
        session,
        recipe=recipe,
        root_dir=root_dir,
        force=force,
        refresh_hint_ms=refresh_hint_ms,
        live_mode=existing_mode or "manual",
        source_poll_ms=source_poll_ms,
        command=command,
        publish_reason=publish_reason,
    )


def live_status(
    session: Session,
    recipe: str = "quick",
    *,
    root_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the live session metadata for the active project."""
    session_dir = _live_session_dir(session, recipe, root_dir=root_dir)
    session_path = session_dir / "session.json"
    if not session_path.is_file():
        raise FileNotFoundError("No Shotcut live preview session found")
    payload = _read_json(session_path)
    poller = dict(payload.get("poller") or {})
    if poller:
        poller["running"] = _pid_is_running(poller.get("pid"))
        payload["poller"] = poller
    trajectory = load_live_trajectory(session_dir)
    if trajectory:
        payload["trajectory_summary"] = summarize_trajectory(trajectory)
    return _with_live_refs(session_dir, payload)


def live_stop(
    session: Session,
    recipe: str = "quick",
    *,
    root_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a live preview session as stopped while preserving its latest bundle."""
    payload = live_status(session, recipe=recipe, root_dir=root_dir)
    now = _now_iso()
    poller = dict(payload.get("poller") or {})
    terminated = _terminate_pid(poller.get("pid"))
    poller["running"] = False
    poller["stopped_at"] = now
    poller["last_exit_reason"] = "manual-stop"
    poller["terminated"] = terminated
    payload["status"] = "stopped"
    payload["stopped_at"] = now
    payload["poller"] = poller
    session_path = Path(payload["_session_path"])
    _write_json(session_path, {k: v for k, v in payload.items() if not k.startswith("_")})
    return _with_live_refs(session_path.parent, payload)


def record_live_poller_spawn(
    session_dir: str,
    *,
    pid: int,
    command: List[str],
    log_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist initial poller spawn metadata before the worker heartbeat lands."""
    session_path = Path(session_dir).expanduser().resolve()
    return _write_live_session_updates(
        session_path,
        {
            "poller": {
                "pid": int(pid),
                "running": True,
                "spawned_at": _now_iso(),
                "command": command,
                "log_path": log_path,
            }
        },
    )


def poll_live_session_once(session_dir: str) -> Dict[str, Any]:
    """Run one poll cycle for a live session and capture if the source changed."""
    session_path = Path(session_dir).expanduser().resolve()
    payload = _load_existing_live_session(session_path)
    now = _now_iso()
    if not payload:
        return {"action": "exit", "reason": "missing-session"}

    if payload.get("status") != "active":
        _write_live_session_updates(
            session_path,
            {
                "poller": {
                    "pid": os.getpid(),
                    "running": False,
                    "last_heartbeat": now,
                    "last_exit_reason": f"session-status:{payload.get('status')}",
                }
            },
        )
        return {"action": "exit", "reason": f"status:{payload.get('status')}"}

    if payload.get("live_mode") != "poll":
        _write_live_session_updates(
            session_path,
            {
                "poller": {
                    "pid": os.getpid(),
                    "running": False,
                    "last_heartbeat": now,
                    "last_exit_reason": f"live-mode:{payload.get('live_mode')}",
                }
            },
        )
        return {"action": "exit", "reason": f"mode:{payload.get('live_mode')}"}

    project_path = payload.get("project_path")
    current_fingerprint = _project_file_fingerprint(project_path)
    base_updates: Dict[str, Any] = {
        "poller": {
            "pid": os.getpid(),
            "running": True,
            "last_heartbeat": now,
        },
        "source_state": {
            "source_type": "project-file",
            "project_path": project_path,
        },
    }
    if current_fingerprint:
        base_updates["source_state"]["last_seen_fingerprint"] = current_fingerprint

    last_rendered = (payload.get("source_state") or {}).get("last_rendered_fingerprint")
    if not project_path or not os.path.isfile(project_path):
        base_updates["source_state"]["last_error"] = f"Project path unavailable: {project_path or '(none)'}"
        base_updates["source_state"]["last_error_at"] = now
        _write_live_session_updates(session_path, base_updates)
        return {"action": "idle", "reason": "missing-project", "project_path": project_path}

    if current_fingerprint and current_fingerprint == last_rendered:
        _write_live_session_updates(session_path, base_updates)
        return {"action": "idle", "fingerprint": current_fingerprint}

    try:
        session = Session(f"live_poller_{int(time.time())}")
        session.open_project(project_path)
        live_payload = live_start(
            session,
            recipe=str(payload.get("recipe") or "quick"),
            root_dir=payload.get("preview_root_dir"),
            force=False,
            refresh_hint_ms=int(payload.get("refresh_hint_ms") or DEFAULT_REFRESH_HINT_MS),
            live_mode="poll",
            source_poll_ms=int(payload.get("source_poll_ms") or DEFAULT_SOURCE_POLL_MS),
            command=str(payload.get("monitor_command") or f"cli-anything-shotcut preview live monitor --session-dir {session_path}"),
            publish_reason="auto-poll",
        )
        _write_live_session_updates(
            session_path,
            {
                "poller": {
                    "pid": os.getpid(),
                    "running": True,
                    "last_heartbeat": now,
                    "last_capture_status": "ok",
                    "last_capture_finished_at": _now_iso(),
                },
                "source_state": {
                    "last_seen_fingerprint": current_fingerprint,
                    "last_rendered_fingerprint": current_fingerprint,
                    "last_rendered_at": _now_iso(),
                    "last_error": None,
                    "last_error_at": None,
                },
            },
        )
        return {
            "action": "captured",
            "bundle_id": live_payload.get("current_bundle_id"),
            "fingerprint": current_fingerprint,
        }
    except Exception as exc:
        _write_live_session_updates(
            session_path,
            {
                "poller": {
                    "pid": os.getpid(),
                    "running": True,
                    "last_heartbeat": now,
                    "last_capture_status": "error",
                    "last_capture_error": str(exc),
                    "last_capture_error_at": _now_iso(),
                },
                "source_state": {
                    "last_seen_fingerprint": current_fingerprint,
                    "last_error": str(exc),
                    "last_error_at": _now_iso(),
                },
            },
        )
        return {"action": "error", "error": str(exc), "fingerprint": current_fingerprint}


def run_live_poller(session_dir: str) -> Dict[str, Any]:
    """Run the long-lived poll loop for a live session."""
    session_path = Path(session_dir).expanduser().resolve()
    while True:
        result = poll_live_session_once(str(session_path))
        if result.get("action") == "exit":
            return result
        payload = _load_existing_live_session(session_path)
        poll_ms = _normalize_poll_ms((payload or {}).get("source_poll_ms"))
        time.sleep(poll_ms / 1000.0)
