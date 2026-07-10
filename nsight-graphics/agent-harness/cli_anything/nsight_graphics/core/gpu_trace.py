"""GPU Trace orchestration and export summarization."""

from __future__ import annotations

from collections import Counter
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


def _find_export_dir(
    output_dir: str,
    *,
    artifact_paths: Sequence[str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Pick the newest export directory containing a complete GPU Trace export."""
    output_root = Path(output_dir).resolve()
    artifact_path_set = None
    if artifact_paths is not None:
        artifact_path_set = {str(Path(path).resolve()) for path in artifact_paths}

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
        if artifact_path_set is not None and not all(str(path.resolve()) in artifact_path_set for path in required_paths):
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

    if artifact_path_set is not None:
        raise RuntimeError(
            "GPU Trace capture finished without a complete newly exported table set "
            "(FRAME.xls, GPUTRACE_FRAME.xls, D3DPERF_EVENTS.xls). Refusing to "
            "summarize stale export data."
        )

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


def _read_table_rows(path: str | None) -> tuple[list[str], list[dict[str, str]]]:
    """Read a generic tab-separated table."""
    if not path:
        return [], []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = [
            {str(key): (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
        return list(reader.fieldnames or []), rows


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


def _metric_unit(metric_name: str) -> str:
    """Classify a metric suffix into a compact unit family."""
    lowered = metric_name.lower()
    if lowered.endswith(".avg.pct_of_peak_sustained_elapsed"):
        return "pct_of_peak"
    if lowered.endswith(".pct"):
        return "percent"
    if lowered.endswith(".sum.per_second"):
        return "per_second"
    if lowered.endswith(".sum"):
        return "count"
    if lowered.endswith(".avg.per_cycle_elapsed"):
        return "per_cycle"
    if lowered.endswith(".avg.peak_sustained"):
        return "peak_sustained"
    if ".avg." in lowered:
        return "average"
    return "other"


def _metric_category(metric_name: str) -> str:
    """Classify a metric by GPU subsystem using stable metric prefixes."""
    lowered = metric_name.lower()
    if "pcie__" in lowered:
        return "pcie"
    if "dramc__" in lowered:
        return "dram"
    if "lts__" in lowered:
        return "l2_cache"
    if "l1tex__" in lowered:
        return "l1_texture"
    if "sm__" in lowered or "smsp__" in lowered or "tpc__" in lowered:
        return "shader_core"
    if "crop__" in lowered or "zrop__" in lowered or "raster__" in lowered or "prop__" in lowered or "vaf__" in lowered:
        return "raster_rop"
    if "fe__" in lowered:
        return "frontend"
    if "gr__" in lowered or "gpu__" in lowered:
        return "graphics_engine"
    return "other"


def _numeric_metrics(metrics: dict[str, str]) -> list[dict[str, Any]]:
    """Return metrics with parsed numeric values and basic classification."""
    parsed: list[dict[str, Any]] = []
    for key, value in metrics.items():
        numeric = _safe_float(value)
        if numeric is None:
            continue
        parsed.append(
            {
                "metric": key,
                "value": numeric,
                "unit": _metric_unit(key),
                "category": _metric_category(key),
            }
        )
    return parsed


def _top_numeric_metrics(
    parsed_metrics: list[dict[str, Any]],
    *,
    unit: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Return top numeric metrics for a unit family."""
    candidates = [item for item in parsed_metrics if item["unit"] == unit]
    candidates.sort(key=lambda item: abs(item["value"]), reverse=True)
    return candidates[:limit]


def _metric_inventory(metrics: dict[str, str], top_n: int) -> dict[str, Any]:
    """Summarize the exported GPU Trace metric table."""
    parsed = _numeric_metrics(metrics)
    return {
        "metric_count": len(metrics),
        "numeric_metric_count": len(parsed),
        "unit_counts": dict(Counter(item["unit"] for item in parsed)),
        "category_counts": dict(Counter(item["category"] for item in parsed)),
        "top_pct_of_peak_metrics": _top_numeric_metrics(parsed, unit="pct_of_peak", limit=top_n),
        "top_count_metrics": _top_numeric_metrics(parsed, unit="count", limit=top_n),
    }


def _pick_metric(metrics: dict[str, str], needle: str) -> float | None:
    """Find the first metric whose key ends with the requested suffix."""
    for key, value in metrics.items():
        if key.endswith(needle):
            return _safe_float(value)
    return None


def _event_depth(event_text: str) -> int:
    """Compute indentation depth for an event row."""
    return len(event_text) - len(event_text.lstrip(" "))


def _table_file_info(path: str | None) -> dict[str, Any]:
    """Return compact file metadata for an optional table path."""
    if not path:
        return {"path": None, "present": False, "size": 0}
    table_path = Path(path)
    return {
        "path": str(table_path),
        "present": table_path.is_file(),
        "size": table_path.stat().st_size if table_path.is_file() else 0,
    }


def _table_inventory(
    *,
    files: dict[str, str | None],
    frame_data: dict[str, str],
    trace_metrics: dict[str, str],
    event_rows: list[dict[str, str]],
    regime_columns: list[str],
    regime_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Describe exported tables and how much usable data they contain."""
    frame_info = _table_file_info(files["frame"])
    frame_info.update({"row_count": len(frame_data), "metric_count": len(frame_data)})

    trace_info = _table_file_info(files["trace_frame"])
    trace_info.update({"row_count": len(trace_metrics), "metric_count": len(trace_metrics)})

    events_info = _table_file_info(files["events"])
    events_info.update({"row_count": len(event_rows), "column_count": 2})

    regimes_info = _table_file_info(files.get("regimes"))
    regimes_info.update(
        {
            "row_count": len(regime_rows),
            "column_count": len(regime_columns),
            "metric_column_count": max(len(regime_columns) - 1, 0),
        }
    )

    return {
        "frame": frame_info,
        "trace_frame": trace_info,
        "events": events_info,
        "regimes": regimes_info,
    }


def _frame_budget(frame_time_ms: float | None, fps_estimate: float | None) -> dict[str, Any]:
    """Classify frame time against common budgets."""
    if frame_time_ms is None:
        return {
            "frame_time_ms": None,
            "fps_estimate": fps_estimate,
            "bucket": "unknown",
            "over_60fps_budget_ms": None,
            "over_30fps_budget_ms": None,
        }
    return {
        "frame_time_ms": frame_time_ms,
        "fps_estimate": fps_estimate,
        "bucket": "over_30fps_budget" if frame_time_ms > 33.3 else "over_60fps_budget" if frame_time_ms > 16.7 else "within_60fps_budget",
        "over_60fps_budget_ms": max(frame_time_ms - 16.6667, 0.0),
        "over_30fps_budget_ms": max(frame_time_ms - 33.3333, 0.0),
    }


def _workload_classification(metrics: dict[str, float | int | None]) -> dict[str, Any]:
    """Classify draw/dispatch balance."""
    draw_count = metrics.get("draw_count")
    dispatch_count = metrics.get("dispatch_count")
    draw_count = draw_count if isinstance(draw_count, int) else 0
    dispatch_count = dispatch_count if isinstance(dispatch_count, int) else 0

    if dispatch_count > max(draw_count * 2, 500):
        classification = "compute_heavy"
    elif draw_count > max(dispatch_count * 2, 100):
        classification = "graphics_heavy"
    elif draw_count or dispatch_count:
        classification = "mixed"
    else:
        classification = "unknown"

    return {
        "classification": classification,
        "draw_count": draw_count,
        "dispatch_count": dispatch_count,
    }


def _throughput_units(metrics: dict[str, float | int | None]) -> list[dict[str, Any]]:
    """Rank selected throughput metrics by utilization."""
    units = [
        ("graphics_engine", "graphics_engine_active_pct"),
        ("shader_sm", "sm_throughput_pct"),
        ("l1_texture", "l1tex_throughput_pct"),
        ("l2_cache", "l2_throughput_pct"),
        ("dram", "dram_throughput_pct"),
        ("pcie", "pcie_throughput_pct"),
        ("sync_compute", "compute_queue_sync_active_pct"),
        ("async_compute", "compute_queue_async_active_pct"),
    ]
    ranked = [
        {"name": name, "metric": metric_name, "pct": value}
        for name, metric_name in units
        if isinstance((value := metrics.get(metric_name)), float)
    ]
    ranked.sort(key=lambda item: item["pct"], reverse=True)
    return ranked


def _build_trace_analysis(
    *,
    frame_time_ms: float | None,
    fps_estimate: float | None,
    metrics: dict[str, float | int | None],
    ranked_events: list[dict[str, Any]],
    table_inventory: dict[str, Any],
) -> dict[str, Any]:
    """Build higher-level GPU Trace diagnostics from exported tables."""
    budget = _frame_budget(frame_time_ms, fps_estimate)
    workload = _workload_classification(metrics)
    throughput_units = _throughput_units(metrics)
    dominant_unit = throughput_units[0] if throughput_units else None
    event_depths = [item["depth"] for item in ranked_events]

    bottlenecks: list[dict[str, Any]] = []
    recommendations: list[str] = []
    warnings: list[str] = []
    highlights: list[str] = []

    if budget["bucket"] == "over_30fps_budget":
        bottlenecks.append(
            {
                "id": "frame_budget_30fps",
                "severity": "high",
                "value": frame_time_ms,
                "message": "GPU frame time exceeds a 30 FPS budget.",
            }
        )
        recommendations.append("Start from the longest GPU events and reduce work on the critical frame path.")
    elif budget["bucket"] == "over_60fps_budget":
        bottlenecks.append(
            {
                "id": "frame_budget_60fps",
                "severity": "medium",
                "value": frame_time_ms,
                "message": "GPU frame time exceeds a 60 FPS budget.",
            }
        )

    for item in throughput_units:
        pct = item["pct"]
        if pct >= 80.0:
            severity = "high"
        elif pct >= 60.0:
            severity = "medium"
        else:
            continue
        bottlenecks.append(
            {
                "id": f"high_{item['name']}_throughput",
                "severity": severity,
                "value": pct,
                "message": f"{item['name']} utilization is {pct:.1f}% of peak sustained elapsed.",
            }
        )

    if workload["classification"] == "compute_heavy":
        recommendations.append("Dispatch count dominates draw count; inspect compute workloads and synchronization.")
    if any(item["name"] == "dram" and item["pct"] >= 60.0 for item in throughput_units):
        recommendations.append("DRAM throughput is high; inspect bandwidth, render target size, and cache locality.")
    if any(item["name"] == "pcie" and item["pct"] >= 60.0 for item in throughput_units):
        recommendations.append("PCIe throughput is high; inspect uploads, readbacks, and host-visible buffer traffic.")
    if any(item["name"] == "shader_sm" and item["pct"] >= 60.0 for item in throughput_units):
        recommendations.append("SM throughput is high; inspect expensive shaders and dispatch/draw ranges.")
    if not ranked_events:
        warnings.append("D3DPERF_EVENTS.xls contains no timed GPU event rows; add markers/NVTX ranges for pass-level attribution.")
    if table_inventory["regimes"]["present"] and table_inventory["regimes"]["row_count"] == 0:
        warnings.append("GPUTRACE_REGIMES.xls contains headers but no per-regime rows.")

    if dominant_unit:
        highlights.append(f"Dominant throughput unit: {dominant_unit['name']} at {dominant_unit['pct']:.3f}%.")
    if workload["classification"] != "unknown":
        highlights.append(
            f"Workload classification: {workload['classification']} "
            f"({workload['draw_count']} draws, {workload['dispatch_count']} dispatches)."
        )

    return {
        "frame_budget": budget,
        "workload": workload,
        "throughput": {
            "dominant_unit": dominant_unit,
            "top_units": throughput_units,
        },
        "event_summary": {
            "event_count": len(ranked_events),
            "top_level_event_count": sum(1 for item in ranked_events if item["depth"] == 0),
            "max_depth": max(event_depths) if event_depths else 0,
        },
        "bottlenecks": bottlenecks,
        "recommendations": recommendations,
        "warnings": warnings,
        "highlights": highlights,
    }


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


def summarize_export_dir(
    output_dir: str,
    top_n: int = 10,
    *,
    artifact_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Summarize exported GPU Trace tables from an output directory."""
    output_root = str(Path(output_dir).resolve())
    export_dir, files = _find_export_dir(output_root, artifact_paths=artifact_paths)
    frame_path = files["frame"]
    trace_frame_path = files["trace_frame"]
    events_path = files["events"]
    regimes_path = files["regimes"]

    frame_data = _read_kv_file(frame_path)
    trace_metrics = _read_kv_file(trace_frame_path)
    event_rows = _read_event_rows(events_path)
    regime_columns, regime_rows = _read_table_rows(regimes_path)

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
    top_level_events = [item for item in ranked_events if item["depth"] == 0][:top_n]
    tables = _table_inventory(
        files=files,
        frame_data=frame_data,
        trace_metrics=trace_metrics,
        event_rows=event_rows,
        regime_columns=regime_columns,
        regime_rows=regime_rows,
    )
    analysis = _build_trace_analysis(
        frame_time_ms=frame_time_ms,
        fps_estimate=fps_estimate,
        metrics=summary_metrics,
        ranked_events=ranked_events,
        table_inventory=tables,
    )
    highlights = _make_highlights(frame_time_ms, summary_metrics, top_events) + analysis["highlights"]

    return {
        "output_dir": export_dir,
        "search_root": output_root,
        "files": files,
        "tables": tables,
        "frame_time_ms": frame_time_ms,
        "fps_estimate": fps_estimate,
        "metrics": summary_metrics,
        "metric_inventory": _metric_inventory(trace_metrics, top_n),
        "top_events": top_events,
        "top_level_events": top_level_events,
        "highlights": highlights,
        "analysis": analysis,
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
    output_dir = backend.prepare_output_dir(output_dir)
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
        if not result.get("ok"):
            raise RuntimeError(
                "GPU Trace capture failed; refusing to summarize stale export tables. "
                f"stderr: {result.get('stderr') or '<empty>'}"
            )
        artifact_paths = [item["path"] for item in result.get("artifacts", [])]
        result["summary"] = summarize_export_dir(
            result["output_dir"],
            top_n=summary_limit,
            artifact_paths=artifact_paths,
        )
    return result
