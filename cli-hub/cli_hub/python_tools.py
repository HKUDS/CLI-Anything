"""Python harness installation with persistent pip/uv ownership.

The registry describes the package source; installed.json records which engine
owns it. In particular, a missing uv must never turn an uninstall into a pip
uninstall in an unrelated environment.
"""

import re
import shlex
import shutil
import subprocess
import sys
from pathlib import PurePosixPath


def select_backend(requested="auto", recorded=None, uv_path=None):
    """Choose an engine without executing anything or changing existing ownership."""
    if requested not in {"auto", "pip", "uv"}:
        raise ValueError("Python backend must be auto, pip, or uv.")
    if recorded is not None and not isinstance(recorded, dict):
        raise ValueError("Invalid installed Python record; inspect installed.json.")
    has_record = recorded is not None
    recorded = recorded or {}
    owner = recorded.get("python_backend")
    if owner is None and has_record:
        # Before backend tracking, Python harnesses were installed with pip.
        owner = "pip"
    if owner is not None and owner not in {"pip", "uv"}:
        raise ValueError("Invalid recorded Python backend; inspect installed.json.")
    if owner and requested not in {"auto", owner}:
        raise ValueError(
            f"This CLI is managed by {owner}. Uninstall it before switching "
            f"to {requested}; no packages were changed."
        )
    return owner or (requested if requested != "auto" else "uv" if uv_path else "pip")


def pip_install_args(command):
    """Extract argv from supported pip install spellings without running a shell."""
    try:
        words = shlex.split(command)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid pip install command in registry.") from exc
    if not words:
        raise ValueError("Missing pip install command in registry.")
    executable = words[0].replace("\\", "/").rsplit("/", 1)[-1]
    if re.fullmatch(r"pip(?:3(?:\.\d+)?)?(?:\.exe)?", executable):
        prefix = 1
    elif (re.fullmatch(r"(?:python(?:3(?:\.\d+)?)?|py)(?:\.exe)?", executable)
          and words[1:3] == ["-m", "pip"]):
        prefix = 3
    else:
        raise ValueError("Python harnesses require a pip install command in the registry.")
    if words[prefix:prefix + 1] != ["install"] or not words[prefix + 1:]:
        raise ValueError("Expected a pip install command with a package source.")
    args = words[prefix + 1:]
    if any(word in {"|", "||", "&&", ";", "&", ">", ">>", "<"} for word in args):
        raise ValueError("Shell command chains are not Python package sources.")
    return args


def uv_install_args(args):
    """Translate the supported single-tool pip subset, rejecting lossy conversions."""
    converted = []
    sources = []
    valued = {"--index-url", "--extra-index-url", "--find-links", "-i", "-f"}
    flags = {
        "--upgrade": ["--upgrade"], "-U": ["--upgrade"],
        "--force-reinstall": ["--reinstall"], "--no-cache-dir": ["--no-cache"],
        "--pre": ["--prerelease", "allow"], "--no-index": ["--no-index"],
        "--no-build-isolation": ["--no-build-isolation"],
        "--editable": ["--editable"], "-e": ["--editable"],
    }
    index = 0
    while index < len(args):
        word = args[index]
        flag, separator, value = word.partition("=")
        if flag in valued:
            if not separator:
                index += 1
                value = args[index] if index < len(args) else ""
            if not value or value.startswith("-"):
                raise ValueError(f"Missing value after {flag} in pip install command.")
            converted.extend([flag, value])
        elif word in flags:
            converted.extend(flags[word])
        elif word.startswith("-"):
            raise ValueError(
                f"pip option {word!r} cannot be translated to uv tool install. "
                "Use --backend pip for this registry entry."
            )
        else:
            sources.append(word)
        index += 1
    if len(sources) != 1:
        raise ValueError(
            "uv tool install requires exactly one package source. "
            "Use --backend pip for multi-package or requirements-file installs."
        )
    return converted + sources


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True)
    except OSError as exc:
        return subprocess.CompletedProcess(argv, 127, stdout="", stderr=str(exc))


def _tool_package(uv_path, entry_point):
    """Resolve the installed distribution from uv's documented tool/executable list.

    A registry slug or console script need not equal the distribution name.
    uv currently has no JSON output for `tool list`; parse only package headers
    and exact executable lines, and reject ambiguous or missing ownership.
    """
    result = _run([uv_path, "tool", "list", "--color", "never"])
    if result.returncode:
        raise ValueError(f"Unable to inspect uv tools: {result.stderr or result.stdout}")
    matches = set()
    package = None
    expected = entry_point.removesuffix(".exe")
    for line in result.stdout.splitlines():
        if line.startswith("- "):
            executable = line[2:].strip().removesuffix(".exe")
            if executable == expected and package:
                matches.add(package)
        elif line and not line[0].isspace():
            header = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*) v(\S+)", line)
            package = (header[1], header[2]) if header else None
    if len(matches) != 1:
        raise ValueError(
            f"Cannot identify the uv tool owning {entry_point!r}. "
            "Inspect `uv tool list` before retrying; no pip fallback was attempted."
        )
    return matches.pop()


def _pip_package(cli, args):
    # Preserve the legacy slug fallback for VCS sources; named requirements and
    # wheels provide an explicit distribution identity without importing code.
    if len(args) == 1:
        source = args[0]
        if source.endswith(".whl"):
            return PurePosixPath(source.replace("\\", "/")).name.split("-", 1)[0]
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[|[=<>!~]|\s*@|$)", source)
        if match:
            return match[1]
    return f"cli-anything-{cli['name']}"


def python_action(cli, action, requested="auto", recorded=None, uv_path=None):
    """Return (success, message, metadata) for one Python harness operation."""
    try:
        backend = select_backend(requested, recorded, uv_path)
        recorded = recorded or {}
        if backend == "uv" and not uv_path:
            raise ValueError(
                "uv is not installed or is not on PATH. Install uv and retry "
                "(https://docs.astral.sh/uv/getting-started/installation/). "
                "The recorded installation has not been changed."
            )
        if action not in {"install", "update", "uninstall"}:
            raise ValueError(f"Unknown Python package action: {action}")
        package = recorded.get("python_package")
        python = recorded.get("python_executable") or sys.executable
        if package is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", package):
            raise ValueError("Invalid recorded Python distribution name.")
        if backend == "uv":
            if action == "install":
                args = uv_install_args(pip_install_args(cli.get("install_cmd")))
                argv = [uv_path, "tool", "install", *args]
            else:
                if not package:
                    package, _ = _tool_package(uv_path, cli["entry_point"])
                argv = [uv_path, "tool", "uninstall", package] if action == "uninstall" else [
                    uv_path, "tool", "upgrade", "--reinstall", package,
                ]
        elif action == "uninstall":
            package = package or f"cli-anything-{cli['name']}"
            argv = [python, "-m", "pip", "uninstall", "-y", package]
        else:
            args = pip_install_args(cli.get("install_cmd"))
            package = package or _pip_package(cli, args)
            argv = [python, "-m", "pip", "install"]
            if action == "update":
                argv.extend(["--upgrade", "--force-reinstall"])
            argv.extend(args)
        result = _run(argv)
        if result.returncode:
            return False, f"{backend} {action} failed:\n{result.stderr or result.stdout}", {}
        if backend == "uv" and action != "uninstall":
            try:
                package, version = _tool_package(uv_path, cli["entry_point"])
            except ValueError as exc:
                return False, f"uv {action} completed, but ownership verification failed: {exc}", {}
        metadata = {"python_backend": backend, "python_package": package}
        if backend == "uv" and action != "uninstall":
            metadata["version"] = version
        if backend == "pip":
            metadata["python_executable"] = python
        verb = {"install": "Installed", "update": "Updated", "uninstall": "Uninstalled"}[action]
        message = f"{verb} {cli['display_name']} via {backend} ({cli['entry_point']})"
        if backend == "uv" and action != "uninstall" and not shutil.which(cli["entry_point"]):
            message += (
                "\nThe executable is not on PATH. Check `uv tool dir --bin`; "
                "run `uv tool update-shell` and reopen your shell if needed."
            )
        return True, message, metadata
    except (ValueError, TypeError) as exc:
        return False, str(exc), {}
