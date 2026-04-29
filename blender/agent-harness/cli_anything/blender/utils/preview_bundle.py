"""Shared helpers for CLI-Anything preview bundles."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

PROTOCOL_VERSION = "preview-bundle/v1"
TRAJECTORY_PROTOCOL_VERSION = "preview-trajectory/v1"


def _slug(value: str) -> str:
    text = (value or "preview").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "preview"


def _json_dumps(data: Any) -> str:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def hash_data(data: Any) -> str:
    return hashlib.sha256(_json_dumps(data).encode("utf-8")).hexdigest()


def fingerprint_data(data: Any) -> str:
    return f"sha256:{hash_data(data)}"


def fingerprint_file(path: str) -> str:
    resolved = os.path.abspath(path)
    stat = os.stat(resolved)
    return fingerprint_data(
        {
            "path": resolved,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    )


def bundle_root(
    software: str,
    recipe: str,
    project_path: Optional[str] = None,
    root_dir: Optional[str] = None,
) -> Path:
    if root_dir:
        base = Path(root_dir).expanduser().resolve()
    elif project_path:
        base = Path(project_path).expanduser().resolve().parent / ".cli-anything" / "previews"
    else:
        base = Path.home() / ".cli-anything" / "previews"
    return base / _slug(software) / _slug(recipe)


def build_cache_key(
    software: str,
    recipe: str,
    bundle_kind: str,
    source_fingerprint: str,
    options: Optional[Dict[str, Any]] = None,
    harness_version: Optional[str] = None,
    protocol_version: str = PROTOCOL_VERSION,
) -> str:
    return fingerprint_data(
        {
            "protocol_version": protocol_version,
            "software": software,
            "recipe": recipe,
            "bundle_kind": bundle_kind,
            "source_fingerprint": source_fingerprint,
            "options": options or {},
            "harness_version": harness_version or "",
        }
    )


def _iter_manifests(search_root: Path) -> Iterable[Path]:
    if not search_root.exists():
        return []
    return sorted(search_root.rglob("manifest.json"), reverse=True)


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_cached_manifest(
    software: str,
    recipe: str,
    bundle_kind: str,
    cache_key: str,
    project_path: Optional[str] = None,
    root_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    root = bundle_root(software, recipe, project_path=project_path, root_dir=root_dir)
    for manifest_path in _iter_manifests(root):
        try:
            manifest = _load_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            manifest.get("protocol_version") == PROTOCOL_VERSION
            and manifest.get("software") == software
            and manifest.get("recipe") == recipe
            and manifest.get("bundle_kind") == bundle_kind
            and manifest.get("status") in {"ok", "partial"}
            and manifest.get("cache_key") == cache_key
        ):
            manifest["_manifest_path"] = str(manifest_path.resolve())
            manifest["_bundle_dir"] = str(manifest_path.parent.resolve())
            manifest["_summary_path"] = str(
                (manifest_path.parent / manifest.get("summary_path", "summary.json")).resolve()
            )
            return manifest
    return None


def find_latest_manifest(
    software: str,
    recipe: Optional[str] = None,
    bundle_kind: Optional[str] = None,
    project_path: Optional[str] = None,
    root_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if root_dir:
        search_root = Path(root_dir).expanduser().resolve() / _slug(software)
    elif project_path:
        search_root = Path(project_path).expanduser().resolve().parent / ".cli-anything" / "previews" / _slug(software)
    else:
        search_root = Path.home() / ".cli-anything" / "previews" / _slug(software)
    if recipe:
        search_root = search_root / _slug(recipe)
    for manifest_path in _iter_manifests(search_root):
        try:
            manifest = _load_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("software") != software:
            continue
        if recipe and manifest.get("recipe") != recipe:
            continue
        if bundle_kind and manifest.get("bundle_kind") != bundle_kind:
            continue
        if manifest.get("status") not in {"ok", "partial"}:
            continue
        manifest["_manifest_path"] = str(manifest_path.resolve())
        manifest["_bundle_dir"] = str(manifest_path.parent.resolve())
        manifest["_summary_path"] = str(
            (manifest_path.parent / manifest.get("summary_path", "summary.json")).resolve()
        )
        return manifest
    return None


def prepare_bundle(
    software: str,
    recipe: str,
    bundle_kind: str,
    source_fingerprint: str,
    options: Optional[Dict[str, Any]] = None,
    harness_version: Optional[str] = None,
    project_path: Optional[str] = None,
    root_dir: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    cache_key = build_cache_key(
        software=software,
        recipe=recipe,
        bundle_kind=bundle_kind,
        source_fingerprint=source_fingerprint,
        options=options or {},
        harness_version=harness_version,
    )
    if not force:
        cached = find_cached_manifest(
            software=software,
            recipe=recipe,
            bundle_kind=bundle_kind,
            cache_key=cache_key,
            project_path=project_path,
            root_dir=root_dir,
        )
        if cached:
            return {
                "cached": True,
                "cache_key": cache_key,
                "bundle_id": cached.get("bundle_id"),
                "bundle_dir": cached["_bundle_dir"],
                "manifest_path": cached["_manifest_path"],
                "summary_path": os.path.join(cached["_bundle_dir"], cached.get("summary_path", "summary.json")),
                "manifest": cached,
            }

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_id = f"{now}_{cache_key.split(':', 1)[-1][:8]}_{_slug(recipe)}"
    out_dir = bundle_root(software, recipe, project_path=project_path, root_dir=root_dir) / bundle_id
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=False)
    return {
        "cached": False,
        "cache_key": cache_key,
        "bundle_id": bundle_id,
        "bundle_dir": str(out_dir.resolve()),
        "artifacts_dir": str(artifacts_dir.resolve()),
        "manifest_path": str((out_dir / "manifest.json").resolve()),
        "summary_path": str((out_dir / "summary.json").resolve()),
    }


def artifact_record(
    bundle_dir: str,
    path: str,
    artifact_id: str,
    role: str,
    kind: str,
    label: str,
    media_type: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    bundle_path = Path(bundle_dir).resolve()
    file_path = Path(path).resolve()
    rel_path = file_path.relative_to(bundle_path).as_posix()
    record: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "role": role,
        "kind": kind,
        "label": label,
        "media_type": media_type or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
        "path": rel_path,
    }
    if file_path.exists():
        record["bytes"] = file_path.stat().st_size
    record.update({k: v for k, v in extra.items() if v is not None})
    return record


def write_json(path: str, data: Any) -> str:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
        fh.write("\n")
    return str(output_path)


def finalize_bundle(
    bundle_dir: str,
    bundle_id: str,
    bundle_kind: str,
    software: str,
    recipe: str,
    source: Dict[str, Any],
    artifacts: list[Dict[str, Any]],
    summary: Dict[str, Any],
    cache_key: str,
    generator: Dict[str, Any],
    status: str = "ok",
    warnings: Optional[list[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    labels: Optional[list[str]] = None,
    source_bundles: Optional[list[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    bundle_path = Path(bundle_dir).resolve()
    summary_rel = "summary.json"
    summary_path = write_json(str(bundle_path / summary_rel), summary)
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "bundle_id": bundle_id,
        "bundle_kind": bundle_kind,
        "software": software,
        "recipe": recipe,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cache_key": cache_key,
        "generator": generator,
        "source": source,
        "summary_path": summary_rel,
        "artifacts": artifacts,
    }
    if warnings:
        manifest["warnings"] = warnings
    if context:
        manifest["context"] = context
    if metrics:
        manifest["metrics"] = metrics
    if labels:
        manifest["labels"] = labels
    if source_bundles:
        manifest["source_bundles"] = source_bundles
    manifest_path = write_json(str(bundle_path / "manifest.json"), manifest)
    manifest["_manifest_path"] = manifest_path
    manifest["_bundle_dir"] = str(bundle_path)
    manifest["_summary_path"] = summary_path
    return manifest


def _clean_none_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def live_trajectory_path(session_dir: str | Path) -> Path:
    return Path(session_dir).expanduser().resolve() / "trajectory.json"


def load_live_trajectory(session_dir: str | Path) -> Dict[str, Any]:
    trajectory_path = live_trajectory_path(session_dir)
    if not trajectory_path.is_file():
        return {}
    return _load_json(trajectory_path)


def summarize_trajectory(trajectory: Dict[str, Any], *, recent_steps: int = 3) -> Dict[str, Any]:
    steps = list(trajectory.get("steps") or [])
    latest = steps[-1] if steps else {}
    recent = steps[-max(1, int(recent_steps)):] if steps else []
    return _clean_none_fields(
        {
            "protocol_version": trajectory.get("protocol_version"),
            "software": trajectory.get("software"),
            "recipe": trajectory.get("recipe"),
            "step_count": trajectory.get("step_count", len(steps)),
            "current_step_id": trajectory.get("current_step_id"),
            "latest_command": latest.get("command"),
            "latest_publish_reason": latest.get("publish_reason"),
            "latest_bundle_id": latest.get("bundle_id"),
            "recent_steps": [
                _clean_none_fields(
                    {
                        "step_id": item.get("step_id"),
                        "step_index": item.get("step_index"),
                        "bundle_id": item.get("bundle_id"),
                        "publish_reason": item.get("publish_reason"),
                        "command": item.get("command"),
                        "command_finished_at": item.get("command_finished_at"),
                        "status": item.get("status"),
                        "cached": item.get("cached"),
                    }
                )
                for item in recent
            ],
        }
    )


def build_live_history_item(
    bundle_manifest: Dict[str, Any],
    *,
    step_id: Optional[str] = None,
    step_index: Optional[int] = None,
    publish_reason: Optional[str] = None,
    command: Optional[str] = None,
    command_started_at: Optional[str] = None,
    command_finished_at: Optional[str] = None,
    source_fingerprint: Optional[str] = None,
    stage_label: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    source = bundle_manifest.get("source") or {}
    resolved_command = command or (bundle_manifest.get("generator") or {}).get("command")
    resolved_fingerprint = (
        source_fingerprint
        or source.get("project_fingerprint")
        or source.get("capture_fingerprint")
    )
    created_at = bundle_manifest.get("created_at")
    return _clean_none_fields(
        {
            "step_id": step_id,
            "step_index": step_index,
            "bundle_id": bundle_manifest.get("bundle_id"),
            "bundle_dir": bundle_manifest.get("_bundle_dir"),
            "manifest_path": bundle_manifest.get("_manifest_path"),
            "summary_path": bundle_manifest.get("_summary_path"),
            "created_at": created_at,
            "status": bundle_manifest.get("status"),
            "cached": bool(bundle_manifest.get("cached")),
            "publish_reason": publish_reason,
            "command": resolved_command,
            "command_started_at": command_started_at or created_at,
            "command_finished_at": command_finished_at or created_at,
            "source_fingerprint": resolved_fingerprint,
            "stage_label": stage_label,
            "note": note,
        }
    )


def append_live_trajectory(
    session_dir: str | Path,
    *,
    software: str,
    recipe: str,
    bundle_manifest: Dict[str, Any],
    publish_reason: str,
    project_path: Optional[str] = None,
    project_name: Optional[str] = None,
    session_name: Optional[str] = None,
    command: Optional[str] = None,
    command_started_at: Optional[str] = None,
    command_finished_at: Optional[str] = None,
    source_fingerprint: Optional[str] = None,
    stage_label: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    session_path = Path(session_dir).expanduser().resolve()
    existing = load_live_trajectory(session_path)
    steps = list(existing.get("steps") or [])
    finished_at = (
        command_finished_at
        or bundle_manifest.get("created_at")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    started_at = command_started_at or finished_at
    step_index = len(steps) + 1
    step_id = f"step-{step_index:04d}"
    step = build_live_history_item(
        bundle_manifest,
        step_id=step_id,
        step_index=step_index,
        publish_reason=publish_reason,
        command=command,
        command_started_at=started_at,
        command_finished_at=finished_at,
        source_fingerprint=source_fingerprint,
        stage_label=stage_label,
        note=note,
    )
    steps.append(step)

    trajectory: Dict[str, Any] = dict(existing)
    trajectory.update(
        _clean_none_fields(
            {
                "protocol_version": TRAJECTORY_PROTOCOL_VERSION,
                "software": software,
                "recipe": recipe,
                "session_name": session_name or session_path.name,
                "project_path": project_path,
                "project_name": project_name,
                "created_at": existing.get("created_at", finished_at),
                "updated_at": finished_at,
                "step_count": len(steps),
                "current_step_id": step_id,
            }
        )
    )
    trajectory["steps"] = steps
    trajectory_path = write_json(str(live_trajectory_path(session_path)), trajectory)
    trajectory["_trajectory_path"] = trajectory_path
    trajectory["latest_step"] = step
    return trajectory
