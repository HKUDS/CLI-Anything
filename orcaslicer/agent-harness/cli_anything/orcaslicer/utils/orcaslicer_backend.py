"""OrcaSlicer backend — invokes the real OrcaSlicer binary in headless CLI mode.

OrcaSlicer is a hard dependency. Install it with:
    macOS:   brew install --cask orcaslicer
    Linux:   https://github.com/OrcaSlicer/OrcaSlicer/releases (AppImage) or your package manager
    Windows: https://github.com/OrcaSlicer/OrcaSlicer/releases
Set ORCASLICER_BIN to point at a non-standard location.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

INSTALL_HELP = (
    "OrcaSlicer is not installed (or not found). Install it with:\n"
    "  brew install --cask orcaslicer        # macOS\n"
    "  https://github.com/OrcaSlicer/OrcaSlicer/releases   # Linux / Windows\n"
    "or set ORCASLICER_BIN to the executable path."
)

# CLI_* codes from libslic3r/Utils.hpp. The process exit status is the code modulo 256.
EXIT_CODES: Dict[int, str] = {
    0: "CLI_SUCCESS",
    -1: "CLI_ENVIRONMENT_ERROR",
    -2: "CLI_INVALID_PARAMS",
    -3: "CLI_FILE_NOTFOUND",
    -4: "CLI_FILELIST_INVALID_ORDER",
    -5: "CLI_CONFIG_FILE_ERROR",
    -6: "CLI_DATA_FILE_ERROR",
    -7: "CLI_INVALID_PRINTER_TECH",
    -8: "CLI_UNSUPPORTED_OPERATION",
    -9: "CLI_COPY_OBJECTS_ERROR",
    -10: "CLI_SCALE_TO_FIT_ERROR",
    -11: "CLI_EXPORT_STL_ERROR",
    -12: "CLI_EXPORT_OBJ_ERROR",
    -13: "CLI_EXPORT_3MF_ERROR",
    -14: "CLI_OUT_OF_MEMORY",
    -15: "CLI_3MF_NOT_SUPPORT_MACHINE_CHANGE",
    -16: "CLI_3MF_NEW_MACHINE_NOT_SUPPORTED",
    -17: "CLI_PROCESS_NOT_COMPATIBLE",
    -18: "CLI_INVALID_VALUES_IN_3MF",
    -19: "CLI_POSTPROCESS_NOT_SUPPORTED",
    -20: "CLI_PRINTABLE_SIZE_REDUCED",
    -21: "CLI_OBJECT_ARRANGE_FAILED",
    -22: "CLI_OBJECT_ORIENT_FAILED",
    -23: "CLI_MODIFIED_PARAMS_TO_PRINTER",
    -24: "CLI_FILE_VERSION_NOT_SUPPORTED",
    -25: "CLI_EXPORT_STATISTICS_ERROR",
    -50: "CLI_NO_SUITABLE_OBJECTS",
    -51: "CLI_VALIDATE_ERROR",
    -52: "CLI_OBJECTS_PARTLY_INSIDE",
    -53: "CLI_EXPORT_CACHE_DIRECTORY_CREATE_FAILED",
    -54: "CLI_EXPORT_CACHE_WRITE_FAILED",
    -55: "CLI_IMPORT_CACHE_NOT_FOUND",
    -56: "CLI_IMPORT_CACHE_DATA_CAN_NOT_USE",
    -57: "CLI_IMPORT_CACHE_LOAD_FAILED",
    -58: "CLI_SLICING_TIME_EXCEEDS_LIMIT",
    -59: "CLI_TRIANGLE_COUNT_EXCEEDS_LIMIT",
    -60: "CLI_NO_SUITABLE_OBJECTS_AFTER_SKIP",
    -61: "CLI_FILAMENT_NOT_MATCH_BED_TYPE",
    -62: "CLI_FILAMENTS_DIFFERENT_TEMP",
    -63: "CLI_OBJECT_COLLISION_IN_SEQ_PRINT",
    -64: "CLI_OBJECT_COLLISION_IN_LAYER_PRINT",
    -65: "CLI_SPIRAL_MODE_INVALID_PARAMS",
    -66: "CLI_FILAMENT_CAN_NOT_MAP",
    -67: "CLI_ONLY_ONE_TPU_SUPPORTED",
    -68: "CLI_FILAMENTS_NOT_SUPPORTED_BY_EXTRUDER",
    -69: "CLI_MIXED_FILAMENT_INVALID",
    -100: "CLI_SLICING_ERROR",
    -101: "CLI_GCODE_PATH_CONFLICTS",
    -102: "CLI_GCODE_PATH_IN_UNPRINTABLE_AREA",
}

SUPPORTED_MODEL_EXTENSIONS = (".stl", ".obj", ".3mf", ".step", ".stp", ".amf")


class OrcaSlicerError(RuntimeError):
    """The OrcaSlicer binary failed (or could not be run)."""

    def __init__(self, message: str, code: Optional[int] = None,
                 code_name: Optional[str] = None, stdout: str = "", stderr: str = "",
                 command: Optional[List[str]] = None):
        super().__init__(message)
        self.code = code
        self.code_name = code_name
        self.stdout = stdout
        self.stderr = stderr
        self.command = command or []


# ── Discovery ────────────────────────────────────────────────────


def _candidate_paths() -> List[str]:
    cands: List[str] = []
    env = os.environ.get("ORCASLICER_BIN")
    if env:
        cands.append(env)
    for name in ("orca-slicer", "OrcaSlicer", "orcaslicer"):
        found = shutil.which(name)
        if found:
            cands.append(found)
    cands += [
        "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer",
        os.path.expanduser("~/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer"),
        "/usr/bin/orca-slicer",
        "/usr/local/bin/orca-slicer",
        "/opt/orca-slicer/bin/orca-slicer",
        r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
    ]
    return cands


def find_orcaslicer() -> str:
    """Return the OrcaSlicer executable path. Raises RuntimeError with install help."""
    for path in _candidate_paths():
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise RuntimeError(INSTALL_HELP)


# ── Exit-code decoding ───────────────────────────────────────────


def decode_returncode(rc: int) -> Tuple[int, str]:
    """Map a process return code to (CLI code, symbolic name).

    OrcaSlicer returns negative CLI_* codes, which the OS truncates to 0..255.
    Python reports death-by-signal as a negative returncode (e.g. -11 = SIGSEGV).
    """
    if rc < 0:
        return rc, f"KILLED_BY_SIGNAL_{-rc}"
    code = rc - 256 if rc > 127 else rc
    return code, EXIT_CODES.get(code, f"UNKNOWN_EXIT_{rc}")


# ── Running ──────────────────────────────────────────────────────


def run(args: Sequence[str], cwd: Optional[str] = None, timeout: int = 600,
        check: bool = False) -> Dict[str, Any]:
    """Run OrcaSlicer with args. Returns a result dict; raises on failure if check=True."""
    exe = find_orcaslicer()
    cmd = [exe, *[str(a) for a in args]]
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, errors="replace")
    except subprocess.TimeoutExpired as exc:
        raise OrcaSlicerError(
            f"OrcaSlicer timed out after {timeout}s", code_name="TIMEOUT",
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            command=cmd) from exc
    code, name = decode_returncode(proc.returncode)
    result = {
        "command": cmd,
        "returncode": proc.returncode,
        "code": code,
        "code_name": name,
        "ok": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_s": round(time.time() - start, 3),
    }
    if check and not result["ok"]:
        raise_for_result(result)
    return result


def raise_for_result(result: Dict[str, Any]) -> None:
    tail = (result["stderr"] or result["stdout"] or "").strip().splitlines()[-6:]
    detail = "\n    ".join(tail)
    msg = f"OrcaSlicer failed: {result['code_name']} (exit {result['returncode']})"
    if name_hint(result["code_name"]):
        msg += f"\n  hint: {name_hint(result['code_name'])}"
    if detail:
        msg += f"\n  output:\n    {detail}"
    raise OrcaSlicerError(msg, code=result["code"], code_name=result["code_name"],
                          stdout=result["stdout"], stderr=result["stderr"],
                          command=result["command"])


_HINTS = {
    "CLI_FILE_NOTFOUND": "an input model or settings file does not exist",
    "CLI_CONFIG_FILE_ERROR": "a setting value is invalid — check `config set` values against `config keys`",
    "CLI_VALIDATE_ERROR": "the preset combination failed OrcaSlicer's validation (see output)",
    "CLI_OBJECTS_PARTLY_INSIDE": "an object is outside the printable area — try `transform arrange` or a larger machine preset",
    "CLI_NO_SUITABLE_OBJECTS": "no object fits on the plate — check scale and machine bed size",
    "CLI_PROCESS_NOT_COMPATIBLE": "the process preset is not compatible with the machine preset",
    "CLI_SLICING_ERROR": "the slicing engine reported an error (see output)",
    "CLI_INVALID_PARAMS": "an option was rejected — see `backend info` for supported flags",
}


def name_hint(code_name: str) -> str:
    if code_name.startswith("KILLED_BY_SIGNAL"):
        return "OrcaSlicer crashed; a preset likely lacks a required key (e.g. filament_diameter)"
    return _HINTS.get(code_name, "")


# ── Introspection ────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_help_text() -> str:
    res = run(["--help"], timeout=60)
    return res["stdout"] + res["stderr"]


def get_version() -> str:
    """Installed OrcaSlicer version, e.g. '2.5.0'."""
    m = re.search(r"OrcaSlicer-([0-9][^\s:]*)", get_help_text())
    return m.group(1) if m else "unknown"


def supported_flags() -> List[str]:
    return sorted(set(re.findall(r"^\s*(--[a-z0-9-]+)", get_help_text(), re.M)))


def supports_flag(flag: str) -> bool:
    return flag in supported_flags()


def backend_info() -> Dict[str, Any]:
    exe = find_orcaslicer()
    return {
        "executable": exe,
        "version": get_version(),
        "flags": supported_flags(),
        "result_json_supported": sys.platform.startswith("linux"),
    }


def _extract_json(text: str) -> Any:
    start = text.find("{")
    if start < 0:
        raise OrcaSlicerError("OrcaSlicer produced no JSON output")
    return json.JSONDecoder().raw_decode(text[start:])[0]


def export_default_settings() -> Dict[str, Any]:
    """Dump the full default config (all valid keys) from the real binary."""
    res = run(["--export-settings", "-"], timeout=60, check=True)
    return _extract_json(res["stdout"])


def inspect_models(paths: Sequence[str], timeout: int = 120) -> Dict[str, Any]:
    """Run --info (text → dict) and, when supported, --inspect-mesh (JSON)."""
    for p in paths:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Model not found: {p}")
    info_res = run(["--info", *[os.path.abspath(p) for p in paths]], timeout=timeout, check=True)
    out: Dict[str, Any] = {"info": parse_info(info_res["stdout"])}
    if supports_flag("--inspect-mesh"):
        mesh = run(["--inspect-mesh", *[os.path.abspath(p) for p in paths]], timeout=timeout)
        if mesh["ok"]:
            try:
                out["mesh"] = _extract_json(mesh["stdout"])
            except (OrcaSlicerError, ValueError):
                pass
    return out


def parse_info(text: str) -> Dict[str, Dict[str, Any]]:
    """Parse `--info` output: '[file]' headers followed by 'key = value' lines."""
    result: Dict[str, Dict[str, Any]] = {}
    current: Optional[Dict[str, Any]] = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            current = result.setdefault(m.group(1), {})
            continue
        if current is not None and "=" in line:
            k, v = [s.strip() for s in line.split("=", 1)]
            try:
                current[k] = float(v) if re.fullmatch(r"-?\d+\.\d+(e-?\d+)?", v) else (
                    int(v) if re.fullmatch(r"-?\d+", v) else v)
            except ValueError:
                current[k] = v
    return result
