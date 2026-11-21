"""Invoke the installed COPT solver and parse its documented CLI attributes."""

import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


class CoptError(Exception):
    pass


def parse_attributes(output, requested=None):
    attributes = {}
    current = None
    values = []
    for line in output.splitlines():
        command = re.match(r"^COPT>\s+get\s+(\w+)", line)
        if command:
            current = command.group(1)
            continue
        value = re.match(r"^\s+(IntAttr|DblAttr):\s+\[Current\]\s+(.+)$", line)
        if value:
            first, *rest = value.group(2).split(maxsplit=1)
            try:
                number = int(first) if value.group(1) == "IntAttr" else float(first.removesuffix("s"))
            except ValueError:
                raise CoptError(f"Cannot parse COPT attribute value: {value.group(2)}")
            values.append((number, rest[0] if rest else None))
            if requested is None and current:
                attributes[current] = number
                if rest and current.endswith("Status"):
                    attributes[current + "Text"] = rest[0]
            current = None
    if requested is not None:
        if len(values) != len(requested):
            raise CoptError(f"Expected {len(requested)} COPT attributes, got {len(values)}")
        for name, (number, label) in zip(requested, values):
            attributes[name] = number
            if label and name.endswith("Status"):
                attributes[name + "Text"] = label
    return attributes


def validate_model(path):
    model = Path(path).expanduser().resolve()
    if not model.is_file():
        raise CoptError(f"Model does not exist or is not a file: {model}")
    if not model.name.lower().endswith((".lp", ".mps", ".lp.gz", ".mps.gz")):
        raise CoptError("Unsupported model format; use .lp, .mps, .lp.gz, or .mps.gz")
    return model


def validate_parameters(*, time_limit, threads, rel_gap):
    commands = []
    if time_limit is not None:
        if not math.isfinite(time_limit) or time_limit <= 0:
            raise CoptError("TimeLimit must be a positive finite number")
        commands.append(f"set TimeLimit {time_limit:g}")
    if threads is not None:
        if threads < 1:
            raise CoptError("Threads must be at least 1")
        commands.append(f"set Threads {threads}")
    if rel_gap is not None:
        if not math.isfinite(rel_gap) or rel_gap < 0 or rel_gap > 1:
            raise CoptError("RelGap must be between 0 and 1")
        commands.append(f"set RelGap {rel_gap:g}")
    return commands


def find_copt():
    explicit = os.environ.get("COPT_CMD")
    candidates = [explicit] if explicit else []
    home = os.environ.get("COPT_HOME")
    if home:
        candidates.append(str(Path(home) / "bin" / "copt_cmd"))
    candidates.extend([shutil.which("copt_cmd"), "/Applications/copt802-scuc/bin/copt_cmd"])
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).resolve())
    raise CoptError("copt_cmd not found; set COPT_CMD or COPT_HOME")


def _invoke(binary, script, cwd=None):
    result = subprocess.run(
        [binary, "-c", script], cwd=cwd, capture_output=True, text=True,
        timeout=3600, check=False, start_new_session=True,
    )
    output = result.stdout + result.stderr
    if result.returncode or re.search(
        r"\[ERROR\]|Reading failed|Writing failed|Failed to open|Unknown COPT parameter or attribute|Unknown command",
        output, re.I,
    ):
        raise CoptError(f"COPT failed (exit {result.returncode}):\n{output}")
    return output


def doctor():
    binary = find_copt()
    output = _invoke(binary, "quit")
    version = output.splitlines()[0].strip() if output else "unknown"
    return {"binary": binary, "version": version, "license_warning": next(
        (line.strip() for line in output.splitlines() if "license expires" in line.lower()), None
    )}


def run_model(model_path, actions, *, output_path=None, output_command=None):
    """Run trusted COPT actions with the user model staged under a safe name."""
    model = validate_model(model_path)
    binary = find_copt()
    if output_path is not None and output_command is None:
        raise ValueError("output_command is required with output_path")
    if output_command is not None and output_command not in {
        "writejsonsol", "writesol", "writeiis", "writelp", "writemps", "writebasis", "writeparam"
    }:
        raise ValueError("Unsupported output command")
    destination = Path(output_path).expanduser().resolve() if output_path is not None else None
    if destination and destination.exists():
        raise CoptError(f"Output already exists: {destination}")
    if destination and not destination.parent.is_dir():
        raise CoptError(f"Output directory does not exist: {destination.parent}")
    with tempfile.TemporaryDirectory(prefix="cli-anything-copt-") as temporary:
        work = Path(temporary)
        suffix = ".lp.gz" if model.name.lower().endswith(".lp.gz") else ".mps.gz" if model.name.lower().endswith(".mps.gz") else model.suffix.lower()
        staged = work / f"model{suffix}"
        staged.symlink_to(model)
        script = [f"read {staged.name}", *actions]
        artifact = None
        if destination:
            artifact = work / f"result{destination.suffix.lower()}"
            script.append(f"{output_command} {artifact.name}")
        script.append("quit")
        log = _invoke(binary, "; ".join(script), cwd=work)
        requested = [match.group(1) for action in actions
                     if (match := re.fullmatch(r"get\s+(\w+)", action))]
        try:
            attributes = parse_attributes(log, requested=requested)
        except CoptError as exc:
            raise CoptError(f"{exc}\nCOPT output tail:\n" + "\n".join(log.splitlines()[-20:])) from exc
        result = {"model": str(model), "attributes": attributes, "log": log}
        if artifact:
            if not artifact.is_file() or artifact.stat().st_size == 0:
                raise CoptError(f"COPT did not create the requested artifact: {artifact.name}\n{log}")
            shutil.copy2(artifact, destination)
            result["output"] = str(destination)
        return result
