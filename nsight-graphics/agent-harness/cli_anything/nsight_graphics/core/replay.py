"""Replay analysis for existing Nsight Graphics capture files."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from cli_anything.nsight_graphics.utils import nsight_graphics_backend as backend

SUPPORTED_CAPTURE_SUFFIXES = {
    ".ngfx-capture": "graphics_capture",
    ".ngfx-gputrace": "gpu_trace",
}


def _capture_type(path: Path) -> str:
    """Return the supported capture type for a file path."""
    suffix = path.suffix.lower()
    capture_type = SUPPORTED_CAPTURE_SUFFIXES.get(suffix)
    if capture_type is None:
        supported = ", ".join(sorted(SUPPORTED_CAPTURE_SUFFIXES))
        raise ValueError(f"Unsupported Nsight capture file extension '{suffix}'. Expected one of: {supported}.")
    return capture_type


def _write_stdout(path: Path, text: str) -> bool:
    """Write stdout to an artifact file when there is output."""
    if not text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _read_text(path: Path) -> str:
    """Read a generated replay artifact as text, tolerating missing files."""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _load_json_artifact(path: Path) -> tuple[Any | None, str | None]:
    """Load a JSON artifact, returning a parse error instead of raising."""
    text = _read_text(path).strip()
    if not text:
        return None, None
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"{exc.msg} at line {exc.lineno}, column {exc.colno}"


def _top_counts(counter: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    """Return top counter entries in a stable JSON shape."""
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def _first_value(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-empty value from a dict."""
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _records_from_json(data: Any, collection_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Extract a list of dict records from common metadata JSON shapes."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in collection_keys:
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _summarize_metadata(path: Path | None) -> dict[str, Any]:
    """Summarize ngfx-replay --metadata without echoing large environment blocks."""
    if path is None:
        return {"parsed": False}
    data, error = _load_json_artifact(path)
    summary: dict[str, Any] = {"parsed": isinstance(data, dict)}
    if error:
        summary["parse_error"] = error
    if not isinstance(data, dict):
        return summary

    graphics_apis = data.get("graphics_apis")
    if isinstance(graphics_apis, dict):
        api_names = sorted(str(key) for key in graphics_apis)
    elif isinstance(graphics_apis, list):
        api_names = [str(item) for item in graphics_apis]
    else:
        api_names = []

    for key in [
        "nsight_version",
        "nsight_version_build_id",
        "captured_frame",
        "primary_api",
        "primary_gpu",
        "driver_vendor",
        "driver_version",
        "os_information",
        "has_unsupported_operation",
        "non_portable",
    ]:
        if key in data:
            summary[key] = data[key]
    summary["graphics_apis"] = api_names
    summary["process_command_line_present"] = bool(data.get("process_command_line"))
    return summary


def _summarize_objects(path: Path | None) -> dict[str, Any]:
    """Summarize object metadata from ngfx-replay --metadata-objects."""
    if path is None:
        return {"parsed": False, "total": 0, "top_types": [], "top_apis": []}
    data, error = _load_json_artifact(path)
    records = _records_from_json(data, ("objects", "resources", "items"))
    type_counts: Counter[str] = Counter()
    api_counts: Counter[str] = Counter()
    named_count = 0
    uid_count = 0
    samples: list[dict[str, Any]] = []

    for item in records:
        type_value = _first_value(item, ("type_name", "type", "object_type", "objectType", "resource_type", "resourceType"))
        api_value = _first_value(item, ("api", "graphics_api", "graphicsApi"))
        name_value = _first_value(item, ("object_name", "name", "label"))
        uid_value = _first_value(item, ("uid", "id", "object_id", "objectId"))
        if type_value is not None:
            type_counts[str(type_value)] += 1
        if api_value is not None:
            api_counts[str(api_value)] += 1
        if name_value is not None:
            named_count += 1
        if uid_value is not None:
            uid_count += 1
        if len(samples) < 5:
            samples.append(
                {
                    "uid": uid_value,
                    "type": type_value,
                    "name": name_value,
                    "api": api_value,
                }
            )

    summary: dict[str, Any] = {
        "parsed": bool(records),
        "total": len(records),
        "named_count": named_count,
        "uid_count": uid_count,
        "top_types": _top_counts(type_counts),
        "top_apis": _top_counts(api_counts),
        "samples": samples,
    }
    if error:
        summary["parse_error"] = error
    return summary


def _summarize_functions(path: Path | None) -> dict[str, Any]:
    """Summarize function-stream metadata from ngfx-replay --metadata-functions."""
    if path is None:
        return {"parsed": False, "total": 0, "unique_count": 0, "top_functions": []}

    data, error = _load_json_artifact(path)
    records = _records_from_json(data, ("functions", "events", "items"))
    names: list[str] = []
    thread_ids: set[str] = set()
    sequence_ids: list[int] = []

    for item in records:
        name = _first_value(item, ("function_name", "name", "function", "call"))
        if name is not None:
            names.append(str(name))
        thread_id = _first_value(item, ("thread_index", "thread_id", "threadId"))
        if thread_id is not None:
            thread_ids.add(str(thread_id))
        sequence_id = _first_value(item, ("sequence_id", "sequenceId", "event_index", "eventIndex"))
        if isinstance(sequence_id, int):
            sequence_ids.append(sequence_id)

    fallback_used = False
    if not records and not error:
        lines = [line.strip() for line in _read_text(path).splitlines() if line.strip()]
        if lines:
            fallback_used = True
            names = lines

    counts = Counter(names)
    summary: dict[str, Any] = {
        "parsed": bool(records) or fallback_used,
        "total": len(names),
        "unique_count": len(counts),
        "top_functions": _top_counts(counts),
        "thread_count": len(thread_ids),
    }
    if sequence_ids:
        summary["first_sequence_id"] = min(sequence_ids)
        summary["last_sequence_id"] = max(sequence_ids)
    if error:
        summary["parse_error"] = error
    if fallback_used:
        summary["parse_mode"] = "line_fallback"
    return summary


def _compact_result(kind: str, result: dict[str, Any], *, stdout_file: Path | None = None, output_file: Path | None = None) -> dict[str, Any]:
    """Return a JSON-friendly command result without embedding large stdout blobs."""
    payload: dict[str, Any] = {
        "kind": kind,
        "ok": result.get("ok", False),
        "returncode": result.get("returncode"),
        "command": result.get("command"),
        "stdout_bytes": len((result.get("stdout") or "").encode("utf-8")),
        "stderr": result.get("stderr") or "",
    }
    if stdout_file is not None:
        payload["stdout_file"] = str(stdout_file)
        payload["stdout_file_present"] = stdout_file.is_file() and stdout_file.stat().st_size > 0
    if output_file is not None:
        payload["output_file"] = str(output_file)
        payload["output_file_present"] = output_file.is_file() and output_file.stat().st_size > 0
    return payload


def _run_stdout_export(
    binaries: dict[str, str | None],
    *,
    capture_file: str,
    output_file: Path,
    kind: str,
    replay_flag: str,
    timeout: int = 300,
) -> dict[str, Any]:
    """Run a metadata-style replay command and save stdout."""
    command = backend.build_replay_command(
        binaries,
        capture_file=capture_file,
        extra_args=[replay_flag],
    )
    result = backend.run_command(command, timeout=timeout)
    _write_stdout(output_file, result.get("stdout") or "")
    return _compact_result(kind, result, stdout_file=output_file)


def _read_error_summary(path: Path, limit: int = 10) -> list[str]:
    """Read a compact captured-log error summary."""
    if not path.is_file():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    return [line for line in lines if line][:limit]


def _is_no_error_line(line: str) -> bool:
    """Return whether ngfx-replay is explicitly reporting an empty error set."""
    return line.strip().lower().startswith("no log messages found")


def _summarize_logs(log_file: Path | None, errors_file: Path | None, limit: int = 10) -> dict[str, Any]:
    """Summarize captured replay logs and separate no-error markers from errors."""
    log_lines = [line.strip() for line in _read_text(log_file).splitlines() if line.strip()] if log_file else []
    raw_error_lines = [line.strip() for line in _read_text(errors_file).splitlines() if line.strip()] if errors_file else []
    if raw_error_lines and all(_is_no_error_line(line) for line in raw_error_lines):
        error_lines: list[str] = []
        status = "no_errors"
    elif raw_error_lines:
        error_lines = raw_error_lines
        status = "errors_present"
    else:
        error_lines = []
        status = "no_error_artifact" if errors_file else "not_requested"

    return {
        "log_line_count": len(log_lines),
        "error_line_count": len(error_lines),
        "error_summary": error_lines[:limit],
        "raw_error_summary": raw_error_lines[:limit],
        "status": status,
    }


def _has_files(path: Path) -> bool:
    """Return whether a directory contains at least one non-empty file."""
    if not path.is_dir():
        return False
    for child in path.rglob("*"):
        if child.is_file() and child.stat().st_size > 0:
            return True
    return False


def _build_analysis(
    *,
    capture_kind: str,
    metadata_requested: bool,
    logs_requested: bool,
    screenshot_requested: bool,
    perf_requested: bool,
    metadata_present: dict[str, bool],
    metadata_summary: dict[str, Any],
    object_summary: dict[str, Any],
    function_summary: dict[str, Any],
    logs_summary: dict[str, Any],
    screenshot_payload: dict[str, Any],
    perf_payload: dict[str, Any],
    command_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact human-usable diagnosis layer over replay artifacts."""
    highlights: list[str] = []
    warnings: list[str] = []

    if capture_kind == "gpu_trace":
        warnings.append(
            "ngfx-replay metadata is documented for graphics capture files; "
            ".ngfx-gputrace inputs may not produce metadata on this Nsight version."
        )

    failed = [item["kind"] for item in command_results if not item.get("ok")]
    if failed:
        warnings.append(f"Replay command failures: {', '.join(failed)}.")

    if metadata_requested:
        if metadata_summary.get("primary_api"):
            highlights.append(f"Primary API: {metadata_summary['primary_api']}.")
        if metadata_summary.get("primary_gpu"):
            highlights.append(f"Primary GPU: {metadata_summary['primary_gpu']}.")
        if object_summary.get("total"):
            highlights.append(f"Metadata objects: {object_summary['total']}.")
        if function_summary.get("total"):
            highlights.append(f"Function events: {function_summary['total']}.")
        if not any(metadata_present.values()):
            warnings.append("No replay metadata artifacts were produced.")

    if logs_requested:
        if logs_summary.get("error_line_count"):
            warnings.append(f"Captured log errors: {logs_summary['error_line_count']}.")
        elif logs_summary.get("status") == "no_errors":
            highlights.append("Captured replay logs reported no severity >= 2 errors.")

    if screenshot_requested:
        if screenshot_payload.get("present"):
            highlights.append("Metadata screenshot exported.")
        else:
            warnings.append("Metadata screenshot was requested but no non-empty image was produced.")

    if perf_requested:
        if perf_payload.get("present"):
            highlights.append("Replay performance report exported.")
        else:
            warnings.append("Performance report was requested but no non-empty report files were produced.")

    return {
        "summary": {
            "metadata_artifacts_present": metadata_present,
            "primary_api": metadata_summary.get("primary_api"),
            "primary_gpu": metadata_summary.get("primary_gpu"),
            "object_count": object_summary.get("total", 0),
            "function_event_count": function_summary.get("total", 0),
            "log_error_count": logs_summary.get("error_line_count", 0),
            "screenshot_present": screenshot_payload.get("present", False),
            "perf_report_present": perf_payload.get("present", False),
        },
        "highlights": highlights,
        "warnings": warnings,
    }


def analyze_capture(
    *,
    nsight_path: str | None,
    capture_file: str,
    output_dir: str,
    metadata: bool,
    logs: bool,
    screenshot: bool,
    perf_report: bool,
) -> dict[str, Any]:
    """Analyze an existing capture through ngfx-replay metadata and replay outputs."""
    capture_path = Path(capture_file).resolve()
    if not capture_path.is_file():
        raise FileNotFoundError(f"Capture file does not exist: {capture_file}")
    capture_kind = _capture_type(capture_path)

    if not any((metadata, logs, screenshot, perf_report)):
        metadata = True
        logs = True
        perf_report = True

    report = backend.probe_installation(nsight_path=nsight_path)
    binaries = report["binaries"]
    if not binaries.get("ngfx_replay"):
        raise RuntimeError(
            "ngfx-replay.exe is required for replay analyze. Install Nsight Graphics "
            "with replay tools or set NSIGHT_GRAPHICS_PATH to an install containing ngfx-replay.exe."
        )

    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    before = backend.snapshot_files([str(output_root)])

    command_results: list[dict[str, Any]] = []
    metadata_files: dict[str, str | None] = {
        "summary": None,
        "functions": None,
        "objects": None,
    }
    logs_payload: dict[str, Any] = {
        "log_file": None,
        "errors_file": None,
        "log_line_count": 0,
        "error_line_count": 0,
        "error_summary": [],
        "raw_error_summary": [],
        "status": "not_requested",
    }
    screenshot_payload: dict[str, Any] = {"path": None, "present": False}
    perf_payload: dict[str, Any] = {"dir": None, "present": False}

    if metadata:
        for kind, flag, filename in [
            ("metadata", "--metadata", "metadata.txt"),
            ("metadata_functions", "--metadata-functions", "metadata_functions.txt"),
            ("metadata_objects", "--metadata-objects", "metadata_objects.json"),
        ]:
            output_file = output_root / filename
            command_results.append(
                _run_stdout_export(
                    binaries,
                    capture_file=str(capture_path),
                    output_file=output_file,
                    kind=kind,
                    replay_flag=flag,
                )
            )
            metadata_key = kind.replace("metadata_", "") if kind != "metadata" else "summary"
            metadata_files[metadata_key] = str(output_file) if output_file.is_file() else None

    if logs:
        log_file = output_root / "metadata_logs.txt"
        errors_file = output_root / "metadata_log_errors.txt"
        command_results.append(
            _run_stdout_export(
                binaries,
                capture_file=str(capture_path),
                output_file=log_file,
                kind="metadata_logs",
                replay_flag="--metadata-logs",
            )
        )
        command_results.append(
            _run_stdout_export(
                binaries,
                capture_file=str(capture_path),
                output_file=errors_file,
                kind="metadata_log_errors",
                replay_flag="--metadata-logs-errors",
            )
        )
        logs_payload["log_file"] = str(log_file) if log_file.is_file() else None
        logs_payload["errors_file"] = str(errors_file) if errors_file.is_file() else None
        logs_payload.update(_summarize_logs(log_file, errors_file))

    if screenshot:
        screenshot_file = output_root / "metadata_screenshot.png"
        command = backend.build_replay_command(
            binaries,
            capture_file=str(capture_path),
            extra_args=["--metadata-screenshot", str(screenshot_file)],
        )
        result = backend.run_command(command, timeout=300)
        command_results.append(_compact_result("metadata_screenshot", result, output_file=screenshot_file))
        screenshot_payload = {
            "path": str(screenshot_file),
            "present": screenshot_file.is_file() and screenshot_file.stat().st_size > 0,
        }

    if perf_report:
        perf_dir = output_root / "perf_report"
        perf_dir.mkdir(parents=True, exist_ok=True)
        command = backend.build_replay_command(
            binaries,
            capture_file=str(capture_path),
            extra_args=[
                "--loop-count",
                "1",
                "--present-hidden",
                "--no-block-on-incompatibility",
                "--perf-report-dir",
                str(perf_dir),
            ],
        )
        result = backend.run_command(command, timeout=600)
        command_results.append(_compact_result("perf_report", result, output_file=perf_dir))
        perf_payload = {
            "dir": str(perf_dir),
            "present": _has_files(perf_dir),
        }

    after = backend.snapshot_files([str(output_root)])
    artifacts = backend.diff_snapshots(before, after)
    metadata_present = {
        "summary": bool(metadata_files["summary"] and Path(metadata_files["summary"]).is_file()),
        "functions": bool(metadata_files["functions"] and Path(metadata_files["functions"]).is_file()),
        "objects": bool(metadata_files["objects"] and Path(metadata_files["objects"]).is_file()),
    }
    metadata_summary = _summarize_metadata(Path(metadata_files["summary"]) if metadata_files["summary"] else None)
    function_summary = _summarize_functions(Path(metadata_files["functions"]) if metadata_files["functions"] else None)
    object_summary = _summarize_objects(Path(metadata_files["objects"]) if metadata_files["objects"] else None)
    all_commands_ok = all(item["ok"] for item in command_results)
    ok = all_commands_ok
    if screenshot:
        ok = ok and screenshot_payload["present"]
    if perf_report:
        ok = ok and perf_payload["present"]
    analysis = _build_analysis(
        capture_kind=capture_kind,
        metadata_requested=metadata,
        logs_requested=logs,
        screenshot_requested=screenshot,
        perf_requested=perf_report,
        metadata_present=metadata_present,
        metadata_summary=metadata_summary,
        object_summary=object_summary,
        function_summary=function_summary,
        logs_summary=logs_payload,
        screenshot_payload=screenshot_payload,
        perf_payload=perf_payload,
        command_results=command_results,
    )

    return {
        "ok": ok,
        "capture_file": str(capture_path),
        "capture_type": capture_kind,
        "version": report.get("version"),
        "tool_mode": report.get("tool_mode"),
        "compatibility_mode": report.get("compatibility_mode"),
        "replay_executable": binaries.get("ngfx_replay"),
        "output_dir": str(output_root),
        "requested_outputs": {
            "metadata": metadata,
            "logs": logs,
            "screenshot": screenshot,
            "perf_report": perf_report,
        },
        "command_results": command_results,
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "metadata": {
            "files": metadata_files,
            "present": metadata_present,
            "summary": metadata_summary,
            "functions": function_summary,
            "objects": object_summary,
        },
        "logs": logs_payload,
        "screenshot": screenshot_payload,
        "perf_report": perf_payload,
        "analysis": analysis,
    }
