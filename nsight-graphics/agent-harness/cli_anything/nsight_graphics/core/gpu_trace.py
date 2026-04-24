"""GPU Trace orchestration and export summarization."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Sequence

from cli_anything.nsight_graphics.utils import nsight_graphics_backend as backend

SUMMARY_METRICS = {
    "draw_count": "fe__draw_count.sum",
    "dispatch_count": "gr__dispatch_count.sum",
    "graphics_engine_active_pct": "gr__cycles_active.avg.pct_of_peak_sustained_elapsed",
    "compute_queue_sync_active_pct": "gr__compute_cycles_active_queue_sync.avg.pct_of_peak_sustained_elapsed",
    "compute_queue_async_active_pct": "gr__compute_cycles_active_queue_async.avg.pct_of_peak_sustained_elapsed",
    "sm_throughput_pct": "sm__throughput.avg.pct_of_peak_sustained_elapsed",
    "l1tex_throughput_pct": "l1tex__throughput.avg.pct_of_peak_sustained_elapsed",
    "l2_throughput_pct": "lts__throughput.avg.pct_of_peak_sustained_elapsed",
    "dram_throughput_pct": "dramc__throughput.avg.pct_of_peak_sustained_elapsed",
    "pcie_throughput_pct": "pcie__throughput.avg.pct_of_peak_sustained_elapsed",
}

REQUIRED_EXPORT_FILES = (
    "FRAME.xls",
    "GPUTRACE_FRAME.xls",
    "D3DPERF_EVENTS.xls",
)


def _find_export_dir(output_dir: str) -> tuple[str, dict[str, str]]:
    """Pick the newest export directory containing a complete GPU Trace export."""
    output_root = Path(output_dir).resolve()
    matches_by_name = {
        name: sorted(output_root.rglob(name))
        for name in (*REQUIRED_EXPORT_FILES, "GPUTRACE_REGIMES.xls")
    }

    candidate_dirs = {
        path.parent
        for name in REQUIRED_EXPORT_FILES
        for path in matches_by_name[name]
    }
    complete_candidates: list[tuple[int, Path, dict[str, str]]] = []
    for directory in candidate_dirs:
        required_paths = [directory / name for name in REQUIRED_EXPORT_FILES]
        if not all(path.is_file() for path in required_paths):
            continue
        newest_required_mtime = max(path.stat().st_mtime_ns for path in required_paths)
        files = {
            "frame": str(directory / "FRAME.xls"),
            "trace_frame": str(directory / "GPUTRACE_FRAME.xls"),
            "events": str(directory / "D3DPERF_EVENTS.xls"),
            "regimes": None,
        }
        regimes_path = directory / "GPUTRACE_REGIMES.xls"
        if regimes_path.is_file():
            files["regimes"] = str(regimes_path)
        complete_candidates.append((newest_required_mtime, directory, files))

    if complete_candidates:
        _, export_dir, files = max(
            complete_candidates,
            key=lambda item: (item[0], str(item[1])),
        )
        return str(export_dir), files

    missing = [
        name
        for name in REQUIRED_EXPORT_FILES
        if not matches_by_name[name]
    ]
    if missing:
        raise RuntimeError(
            "GPU Trace export summary requires exported tables. Missing: "
            + ", ".join(missing)
        )
    raise RuntimeError(
        "GPU Trace export summary requires FRAME.xls, GPUTRACE_FRAME.xls, and "
        "D3DPERF_EVENTS.xls to exist under the same export directory."
    )


def _read_kv_file(path: str) -> dict[str, str]:
    """Read a simple tab-separated key/value file."""
    data: dict[str, str] = {}
    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or "\t" not in line:
                continue
            key, value = line.split("\t", 1)
            data[key.strip()] = value.strip()
    return data


def _read_event_rows(path: str) -> list[dict[str, str]]:
    """Read D3DPERF event rows from the exported TSV."""
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = []
        for row in reader:
            event_text = (row.get("event_text") or "").rstrip()
            time_ms = (row.get("time_ms") or "").strip()
            if not event_text or not time_ms:
                continue
            rows.append({"event_text": event_text, "time_ms": time_ms})
        return rows


def _safe_float(value: str | None) -> float | None:
    """Convert a string to float when possible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: float | None) -> int | None:
    """Convert a float to int when available."""
    if value is None:
        return None
    return int(round(value))


def _pick_metric(metrics: dict[str, str], needle: str) -> float | None:
    """Find the first metric whose key ends with the requested suffix."""
    for key, value in metrics.items():
        if key.endswith(needle):
            return _safe_float(value)
    return None


def _event_depth(event_text: str) -> int:
    """Compute indentation depth for an event row."""
    return len(event_text) - len(event_text.lstrip(" "))


def _make_highlights(
    frame_time_ms: float | None,
    metrics: dict[str, float | int | None],
    top_events: list[dict[str, Any]],
) -> list[str]:
    """Generate short heuristic findings."""
    highlights: list[str] = []

    if frame_time_ms is not None:
        if frame_time_ms > 33.3:
            highlights.append("GPU frame is slower than 30 FPS budget.")
        elif frame_time_ms > 16.7:
            highlights.append("GPU frame exceeds 60 FPS budget.")

    draw_count = metrics.get("draw_count")
    dispatch_count = metrics.get("dispatch_count")
    if isinstance(draw_count, int) and isinstance(dispatch_count, int):
        if dispatch_count > max(draw_count * 2, 500):
            highlights.append("Frame is compute-heavy relative to draw count.")

    compute_sync = metrics.get("compute_queue_sync_active_pct")
    if isinstance(compute_sync, float) and compute_sync > 50.0:
        highlights.append("Synchronous compute queue activity is high.")

    dram_pct = metrics.get("dram_throughput_pct")
    if isinstance(dram_pct, float) and dram_pct > 60.0:
        highlights.append("DRAM throughput is high enough to suggest memory pressure.")

    if top_events:
        top = top_events[0]
        if frame_time_ms and top["time_ms"] >= frame_time_ms * 0.25:
            highlights.append(f"Largest GPU event is '{top['event']}' at {top['time_ms']:.3f} ms.")

    return highlights


def summarize_export_dir(output_dir: str, top_n: int = 10) -> dict[str, Any]:
    """Summarize exported GPU Trace tables from an output directory."""
    output_root = str(Path(output_dir).resolve())
    export_dir, files = _find_export_dir(output_root)
    frame_path = files["frame"]
    trace_frame_path = files["trace_frame"]
    events_path = files["events"]
    regimes_path = files["regimes"]

    frame_data = _read_kv_file(frame_path)
    trace_metrics = _read_kv_file(trace_frame_path)
    event_rows = _read_event_rows(events_path)

    frame_time_ms = _safe_float(frame_data.get("GPU frame time"))
    fps_estimate = (1000.0 / frame_time_ms) if frame_time_ms and frame_time_ms > 0 else None

    summary_metrics: dict[str, float | int | None] = {}
    for name, needle in SUMMARY_METRICS.items():
        value = _pick_metric(trace_metrics, needle)
        if name in {"draw_count", "dispatch_count"}:
            summary_metrics[name] = _safe_int(value)
        else:
            summary_metrics[name] = value

    ranked_events: list[dict[str, Any]] = []
    for row in event_rows:
        event_name = row["event_text"]
        if event_name.startswith("Frame "):
            continue
        time_ms = _safe_float(row["time_ms"])
        if time_ms is None or time_ms <= 0:
            continue
        ranked_events.append(
            {
                "event": event_name.strip(),
                "time_ms": time_ms,
                "depth": _event_depth(event_name),
            }
        )

    ranked_events.sort(key=lambda item: item["time_ms"], reverse=True)
    top_events = ranked_events[:top_n]
    top_level_events = [item for item in top_events if item["depth"] == 0]

    return {
        "output_dir": export_dir,
        "search_root": output_root,
        "files": files,
        "frame_time_ms": frame_time_ms,
        "fps_estimate": fps_estimate,
        "metrics": summary_metrics,
        "top_events": top_events,
        "top_level_events": top_level_events,
        "highlights": _make_highlights(frame_time_ms, summary_metrics, top_events),
    }


def capture_trace(
    *,
    nsight_path: str | None,
    project: str | None,
    output_dir: str | None,
    hostname: str | None,
    platform_name: str | None,
    exe: str | None,
    working_dir: str | None,
    args: Sequence[str],
    envs: Sequence[str],
    start_after_frames: int | None,
    start_after_submits: int | None,
    start_after_ms: int | None,
    start_after_hotkey: bool,
    max_duration_ms: int | None,
    limit_to_frames: int | None,
    limit_to_submits: int | None,
    auto_export: bool,
    architecture: str | None,
    metric_set_id: str | None,
    multi_pass_metrics: bool,
    real_time_shader_profiler: bool,
    summarize: bool = False,
    summary_limit: int = 10,
) -> dict:
    """Run a GPU Trace capture."""
    report = backend.probe_installation(nsight_path=nsight_path)
    binaries = report["binaries"]
    backend.require_binary(binaries, "ngfx")
    backend.require_launch_target(project=project, exe=exe)

    backend.ensure_exactly_one(
        "gpu trace start trigger",
        {
            "start_after_frames": start_after_frames is not None,
            "start_after_submits": start_after_submits is not None,
            "start_after_ms": start_after_ms is not None,
            "start_after_hotkey": start_after_hotkey,
        },
    )
    backend.ensure_at_most_one(
        "gpu trace stop limit",
        {
            "limit_to_frames": limit_to_frames is not None,
            "limit_to_submits": limit_to_submits is not None,
        },
    )
    if metric_set_id and not architecture:
        raise ValueError("--metric-set-id requires --architecture.")
    if summary_limit < 1:
        raise ValueError("--summary-limit must be at least 1.")

    auto_export = auto_export or summarize

    extra_args: list[str] = []
    if start_after_frames is not None:
        extra_args.extend(["--start-after-frames", str(start_after_frames)])
    elif start_after_submits is not None:
        extra_args.extend(["--start-after-submits", str(start_after_submits)])
    elif start_after_ms is not None:
        extra_args.extend(["--start-after-ms", str(start_after_ms)])
    else:
        extra_args.append("--start-after-hotkey")

    if max_duration_ms is not None:
        extra_args.extend(["--max-duration-ms", str(max_duration_ms)])
    if limit_to_frames is not None:
        extra_args.extend(["--limit-to-frames", str(limit_to_frames)])
    if limit_to_submits is not None:
        extra_args.extend(["--limit-to-submits", str(limit_to_submits)])
    if auto_export:
        extra_args.append("--auto-export")
    if architecture:
        extra_args.extend(["--architecture", architecture])
    if metric_set_id:
        extra_args.extend(["--metric-set-id", str(metric_set_id)])
    if multi_pass_metrics:
        extra_args.append("--multi-pass-metrics")
    if real_time_shader_profiler:
        extra_args.append("--real-time-shader-profiler")

    command = backend.build_unified_command(
        binaries,
        activity="GPU Trace Profiler",
        project=project,
        output_dir=output_dir,
        hostname=hostname,
        platform_name=platform_name,
        exe=exe,
        working_dir=working_dir,
        args=args,
        envs=envs,
        extra_args=extra_args,
    )
    result = backend.run_with_artifacts(
        command,
        output_roots=backend.activity_artifact_roots("GPU Trace Profiler", output_dir),
        timeout=600,
    )
    result["tool_mode"] = "unified"
    result["activity"] = "GPU Trace Profiler"
    result["output_dir"] = output_dir or backend.default_output_dir()
    result["auto_export"] = auto_export

    if summarize:
        result["summary"] = summarize_export_dir(result["output_dir"], top_n=summary_limit)
    return result
