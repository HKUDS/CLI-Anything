"""
Exporter command construction and execution helpers.
"""

from __future__ import annotations

import ctypes
import os
import re
import shlex
import tempfile
from pathlib import Path

from cli_anything.unrealinsights.utils import unrealinsights_backend as backend

EXPORTER_COMMANDS = {
    "threads": "TimingInsights.ExportThreads",
    "timers": "TimingInsights.ExportTimers",
    "timing-events": "TimingInsights.ExportTimingEvents",
    "timer-stats": "TimingInsights.ExportTimerStatistics",
    "timer-callees": "TimingInsights.ExportTimerCallees",
    "counters": "TimingInsights.ExportCounters",
    "counter-values": "TimingInsights.ExportCounterValues",
}


def _quote(value: str) -> str:
    return f'"{value}"'


def _is_legacy_unrealinsights(version: str | None) -> bool:
    return bool(version and version.startswith("5.3"))


def _windows_short_path(path: Path) -> str | None:
    if os.name != "nt":
        return None
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    if result == 0:
        return None
    return buffer.value


def _legacy_filename_arg(output_path: str) -> str:
    path = Path(output_path).expanduser().resolve()
    path_str = str(path)
    if " " not in path_str:
        return path_str

    parent = path.parent
    short_parent = _windows_short_path(parent)
    if not short_parent:
        raise RuntimeError(
            f"Legacy UnrealInsights export requires a path without spaces or a resolvable short path: {path}"
        )
    if " " in path.name:
        raise RuntimeError(
            f"Legacy UnrealInsights export does not support spaces in the output filename: {path.name}"
        )
    return str(Path(short_parent) / path.name)


def _modern_filename_arg(output_path: str) -> str:
    """Build a filename token compatible with modern UnrealInsights builds."""
    path = Path(output_path).expanduser().resolve()
    path_str = str(path)
    if os.name != "nt":
        return _quote(path_str)
    if " " not in path_str:
        return path_str

    short_path = _windows_short_path(path)
    if short_path:
        return short_path

    raise RuntimeError(
        "UnrealInsights export requires a path without spaces or a resolvable short path on Windows: "
        f"{path}"
    )


def _filename_arg(output_path: str, insights_version: str | None = None) -> str:
    output_abs = str(Path(output_path).expanduser().resolve())
    if _is_legacy_unrealinsights(insights_version):
        return _legacy_filename_arg(output_abs)
    return _modern_filename_arg(output_abs)


def _option_value_arg(name: str, value: str) -> str:
    if not any(ch.isspace() for ch in value):
        return f"-{name}={value}"
    return f"-{name}={_quote(value)}"


def build_export_exec_command(
    exporter: str,
    output_path: str,
    *,
    insights_version: str | None = None,
    columns: str | None = None,
    threads: str | None = None,
    timers: str | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    region: str | None = None,
    counter: str | None = None,
) -> str:
    """Build a TimingInsights exporter command string."""
    if exporter not in EXPORTER_COMMANDS:
        raise RuntimeError(f"Unsupported exporter: {exporter}")

    output_abs = str(Path(output_path).expanduser().resolve())
    filename_token = _filename_arg(output_abs, insights_version=insights_version)

    parts = [EXPORTER_COMMANDS[exporter], filename_token]

    if counter:
        parts.append(_option_value_arg("counter", counter))
    if columns:
        parts.append(_option_value_arg("columns", columns))
    if threads:
        parts.append(_option_value_arg("threads", threads))
    if timers:
        parts.append(_option_value_arg("timers", timers))
    if start_time is not None:
        parts.append(f"-startTime={start_time}")
    if end_time is not None:
        parts.append(f"-endTime={end_time}")
    if region:
        parts.append(_option_value_arg("region", region))

    return " ".join(parts)


def build_rsp_exec_command(rsp_path: str) -> str:
    """Build the response-file execution token."""
    return f"@={Path(rsp_path).expanduser().resolve()}"


def _normalize_rsp_line(line: str, insights_version: str | None = None) -> tuple[str, str | None]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return line, None

    match = re.match(r'^(?P<indent>\s*)(?P<command>\S+)\s+(?P<output>"[^"]*"|\S+)(?P<rest>.*)$', line)
    if not match:
        return line, None

    command = match.group("command")
    if command not in EXPORTER_COMMANDS.values():
        return line, None

    output_path = match.group("output").strip('"')
    normalized_output = _filename_arg(output_path, insights_version=insights_version)
    normalized_line = f"{match.group('indent')}{command} {normalized_output}{match.group('rest')}"
    return normalized_line, str(Path(output_path).expanduser().resolve())


def _path_contains_placeholders(path: Path) -> bool:
    return "{counter}" in path.name or "{region}" in path.name


def collect_materialized_outputs(output_path: str) -> list[str]:
    """Collect actual output files for a requested exporter path."""
    path = Path(output_path).expanduser().resolve()
    if _path_contains_placeholders(path):
        pattern = path.name.replace("{counter}", "*").replace("{region}", "*")
        return sorted(str(match.resolve()) for match in path.parent.glob(pattern) if match.is_file())
    if path.is_file():
        return [str(path)]
    return []


def _token_output_path(command_line: str) -> str | None:
    try:
        tokens = shlex.split(command_line, posix=False)
    except ValueError:
        return None
    if len(tokens) < 2:
        return None
    return tokens[1].strip('"')


def expected_outputs_from_rsp(rsp_path: str) -> list[str]:
    """Read a response file and infer output files from each command line."""
    path = Path(rsp_path).expanduser().resolve()
    outputs: list[str] = []
    if not path.is_file():
        return outputs

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        output = _token_output_path(stripped)
        if output:
            outputs.append(str(Path(output).expanduser().resolve()))
    return outputs


def normalize_response_file_lines(lines: list[str], *, insights_version: str | None = None) -> list[str]:
    """Normalize response-file output filename tokens for UnrealInsights parsing."""
    normalized_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            normalized_lines.append(line)
            continue
        try:
            tokens = shlex.split(stripped, posix=False)
        except ValueError:
            normalized_lines.append(line)
            continue
        if len(tokens) < 2:
            normalized_lines.append(line)
            continue
        output_path = tokens[1].strip('"')
        filename_token = _filename_arg(output_path, insights_version=insights_version)
        normalized_lines.append(" ".join([tokens[0], filename_token, *tokens[2:]]))
    return normalized_lines


def normalized_response_file_path(rsp_path: str, *, insights_version: str | None = None) -> str:
    """Return a normalized temporary response file path when normalization changes content."""
    path = Path(rsp_path).expanduser().resolve()
    if not path.is_file():
        return str(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    normalized_lines = normalize_response_file_lines(lines, insights_version=insights_version)
    if normalized_lines == lines:
        return str(path)

    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        errors="replace",
        suffix=".rsp",
        prefix=f"{path.stem}-normalized-",
        delete=False,
    )
    with handle:
        handle.write("\n".join(normalized_lines))
        handle.write("\n")
    return str(Path(handle.name).resolve())


def default_log_path(reference_path: str, suffix: str = ".insights.log") -> str:
    path = Path(reference_path).expanduser().resolve()
    return str(path.with_name(f"{path.stem}{suffix}"))


def _execute_insights(
    insights_exe: str,
    trace_path: str,
    exec_command: str,
    expected_outputs: list[str],
    log_path: str,
) -> dict[str, object]:
    backend.ensure_parent_dir(log_path)
    for output in expected_outputs:
        if "{" not in Path(output).name:
            backend.ensure_parent_dir(output)

    raw_command = backend.build_insights_command_line(insights_exe, trace_path, exec_command, log_path)
    run_result = backend.run_process(
        raw_command,
        wait=True,
    )
    log_info = backend.parse_unreal_log(log_path)

    actual_outputs: list[str] = []
    seen: set[str] = set()
    for output in expected_outputs:
        for match in collect_materialized_outputs(output):
            if match not in seen:
                actual_outputs.append(match)
                seen.add(match)

    output_status, status_message = classify_export_result(run_result, log_info, actual_outputs, expected_outputs)

    run_result.update(
        {
            "trace_path": str(Path(trace_path).expanduser().resolve()),
            "exec_command": exec_command,
            "expected_outputs": expected_outputs,
            "output_files": actual_outputs,
            "log_path": log_info["path"],
            "warnings": log_info["warnings"],
            "errors": log_info["errors"],
            "output_status": output_status,
            "status_message": status_message,
            "succeeded": output_status == "ok",
        }
    )
    return run_result


def classify_export_result(
    run_result: dict[str, object],
    log_info: dict[str, object],
    actual_outputs: list[str],
    expected_outputs: list[str],
) -> tuple[str, str]:
    """Classify an Unreal Insights exporter result for agent diagnostics."""
    if run_result.get("timed_out"):
        return "timed_out", "UnrealInsights.exe timed out before export completion."
    if run_result.get("exit_code") != 0:
        return "process_failed", f"UnrealInsights.exe exited with code {run_result.get('exit_code')}."
    if actual_outputs:
        return "ok", f"Materialized {len(actual_outputs)} output file(s)."

    errors = list(log_info.get("errors") or [])
    if errors:
        return "exporter_error", errors[-1]
    if expected_outputs:
        return (
            "no_output",
            "Exporter completed without materializing expected outputs; the trace may not contain matching data.",
        )
    return "no_expected_outputs", "No output paths were inferred for this export command."


def execute_export(
    insights_exe: str,
    trace_path: str,
    exporter: str,
    output_path: str,
    *,
    insights_version: str | None = None,
    columns: str | None = None,
    threads: str | None = None,
    timers: str | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    region: str | None = None,
    counter: str | None = None,
    log_path: str | None = None,
) -> dict[str, object]:
    """Execute a single TimingInsights exporter."""
    output_abs = str(Path(output_path).expanduser().resolve())
    resolved_log_path = log_path or default_log_path(output_abs)
    exec_command = build_export_exec_command(
        exporter,
        output_abs,
        insights_version=insights_version,
        columns=columns,
        threads=threads,
        timers=timers,
        start_time=start_time,
        end_time=end_time,
        region=region,
        counter=counter,
    )
    result = _execute_insights(
        insights_exe,
        trace_path,
        exec_command=exec_command,
        expected_outputs=[output_abs],
        log_path=resolved_log_path,
    )
    result["exporter"] = exporter
    return result


def execute_response_file(
    insights_exe: str,
    trace_path: str,
    rsp_path: str,
    *,
    insights_version: str | None = None,
    log_path: str | None = None,
) -> dict[str, object]:
    """Execute a response file batch export."""
    rsp_abs = str(Path(rsp_path).expanduser().resolve())
    resolved_log_path = log_path or default_log_path(rsp_abs)
    lines = Path(rsp_abs).read_text(encoding="utf-8", errors="replace").splitlines()

    normalized_lines: list[str] = []
    expected_outputs: list[str] = []
    for line in lines:
        normalized_line, normalized_output = _normalize_rsp_line(line, insights_version=insights_version)
        normalized_lines.append(normalized_line)
        if normalized_output:
            expected_outputs.append(normalized_output)

    if not expected_outputs:
        expected_outputs = expected_outputs_from_rsp(rsp_abs)

    temp_rsp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".rsp", delete=False, encoding="utf-8", newline="\n") as handle:
            temp_rsp_path = handle.name
            handle.write("\n".join(normalized_lines))
        result = _execute_insights(
            insights_exe,
            trace_path,
            exec_command=build_rsp_exec_command(temp_rsp_path),
            expected_outputs=expected_outputs,
            log_path=resolved_log_path,
        )
    finally:
        if temp_rsp_path:
            try:
                Path(temp_rsp_path).unlink()
            except OSError:
                pass
    result["response_file"] = rsp_abs
    result["executed_response_file"] = str(Path(temp_rsp_path).resolve()) if temp_rsp_path else rsp_abs
    result["exporter"] = "response-file"
    return result
