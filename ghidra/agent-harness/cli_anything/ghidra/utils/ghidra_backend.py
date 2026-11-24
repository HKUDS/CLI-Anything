"""Ghidra headless backend - drives the real analyzeHeadless launcher.

Security notes:
- The target binary is only read and copied, never executed.
- On Windows analyzeHeadless is a .bat file, so cmd.exe parses its arguments even
  for list-form subprocess calls (BatBadBut). Every user-supplied string that
  reaches the command line is therefore checked against a strict allowlist, and
  the input binary is staged under a hash-derived safe name so its own filename
  never appears on the command line.
- Paths that reach the command line (work folder, script folder, scratch folder,
  launcher) are checked for the same characters, so a folder such as "R&D" cannot
  split the command line either.
- Results are written by the post-script to a JSON file; stdout (Ghidra log noise)
  is never parsed.
- On timeout the whole process tree is killed: on Windows the .bat would otherwise
  leave java.exe running, holding the project lock.
"""

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any

INSTALL_ENV = "GHIDRA_INSTALL_DIR"
JAVA_ENV = "GHIDRA_JAVA_HOME"
HOME_ENV = "CLI_ANYTHING_GHIDRA_HOME"
SCRIPT_NAME = "CliAnythingQuery.java"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
DEFAULT_ANALYSIS_TIMEOUT = 600
QUERY_TIMEOUT = 300


_TARGET = re.compile(r"^[A-Za-z0-9_.$@?][A-Za-z0-9_.$@?-]{0,199}$")
_ADDRESS = re.compile(r"^(0x)?[0-9a-fA-F]{1,16}$")
_LOADER = re.compile(r"^[A-Za-z0-9_]{1,60}$")
_PROCESSOR = re.compile(r"^[A-Za-z0-9_.+-]+:(LE|BE):\d+:[A-Za-z0-9_.+-]+$")

_PATH_UNSAFE = frozenset('&|<>^%!()"' + chr(10) + chr(13) + chr(0))

INSTALL_HELP = (
    f"Ghidra not found. Download Ghidra 12.x from https://github.com/NationalSecurityAgency/ghidra/releases, "
    f"unzip it, and set {INSTALL_ENV} to the unzipped folder (the one containing 'support'). "
    f"Ghidra 12 needs a JDK 25+ (set {JAVA_ENV} to it if your default JAVA_HOME is older)."
)


def check(value: str, pattern: "re.Pattern[str]", what: str) -> str:
    """Return value if it matches the allowlist, else raise."""
    value = str(value).strip()
    if not pattern.match(value):
        raise RuntimeError(f"Invalid {what} {value!r}: contains characters that are not allowed.")
    return value


def check_path(path: Path | str, what: str) -> Path | str:
    """Refuse paths that cmd.exe would split or expand, or that the launcher script cannot take."""
    text = str(path)
    if any(c in _PATH_UNSAFE for c in text):
        raise RuntimeError(
            f"The {what} {text!r} contains a character that cmd.exe or the Ghidra launcher "
            "script cannot take (& | < > ^ % ! ( ) or a quote). "
            f"Use another folder (for the work folder set {HOME_ENV})."
        )
    return path


def popen_kwargs() -> dict:
    """Start the launcher in its own process group so the whole tree can be killed."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def _kill_tree(proc: "subprocess.Popen") -> None:
    """Kill proc and its children (killing only cmd.exe leaves java.exe running)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass


def find_analyze_headless() -> Path:
    install = os.environ.get(INSTALL_ENV, "").strip()
    name = "analyzeHeadless.bat" if os.name == "nt" else "analyzeHeadless"
    if install:
        candidate = Path(install) / "support" / name
        if candidate.is_file():
            return candidate
        raise RuntimeError(f"{INSTALL_ENV}={install!r} has no support/{name}. " + INSTALL_HELP)
    found = shutil.which("analyzeHeadless") or shutil.which(name)
    if not found:
        raise RuntimeError(INSTALL_HELP)
    return Path(found)


def work_home() -> Path:
    """Where projects and staged inputs live. Ghidra rejects any path element starting with '.'."""
    home = Path(os.environ.get(HOME_ENV) or Path.home() / "cli-anything-ghidra").expanduser().resolve()
    bad = [p for p in home.parts if p.startswith(".")]
    if bad:
        raise RuntimeError(
            f"Ghidra cannot use a project path containing {bad[0]!r} (folders starting with '.'). "
            f"Set {HOME_ENV} to another folder."
        )
    return home


def file_key(path: Path) -> str:
    """Content hash used as project and program name, so the filename never reaches the command line."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


class GhidraBackend:
    """Runs analyzeHeadless for import/analysis and for read-only queries."""

    def __init__(self, home: Path | None = None, query_timeout: int = QUERY_TIMEOUT):
        self.query_timeout = query_timeout
        self.launcher = find_analyze_headless()
        self.home = home or work_home()
        self.projects = self.home / "projects"
        self.projects.mkdir(parents=True, exist_ok=True)

    def _env(self) -> dict:
        env = dict(os.environ)
        if env.get(JAVA_ENV):
            env["JAVA_HOME"] = env[JAVA_ENV]
        return env

    def _scratch(self) -> "tempfile.TemporaryDirectory":
        scratch = self.home / "tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=scratch)

    def _run(self, args: list, output: Path, timeout: int) -> Any:
        for what, path in (("Ghidra launcher", self.launcher), ("work folder", self.projects),
                           ("script folder", SCRIPTS_DIR), ("scratch folder", output.parent)):
            check_path(path, what)
        cmd = [str(self.launcher), str(self.projects)] + args
        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", env=self._env(), **popen_kwargs(),
            )
        except OSError as e:
            raise RuntimeError(f"Cannot start Ghidra ({type(e).__name__}). " + INSTALL_HELP)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            proc.communicate()
            raise RuntimeError(f"Ghidra timed out after {timeout}s. Raise --timeout or analyze a smaller binary.")
        if not output.is_file():
            raise RuntimeError(self._failure(subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)))
        try:
            return json.loads(output.read_text(encoding="utf-8"))
        except ValueError:
            raise RuntimeError("Ghidra left an unreadable result file (killed mid-write?). Run the command again.")

    @staticmethod
    def _failure(proc: subprocess.CompletedProcess) -> str:
        text = (proc.stdout or "") + (proc.stderr or "")
        if "JDK" in text and "could not be found" in text:
            return f"Ghidra could not find a supported JDK (12.x needs 25+). Set {JAVA_ENV} to a JDK 25+ folder."
        lines = [ln.strip() for ln in text.splitlines() if "ERROR" in ln or "Exception" in ln]
        detail = " | ".join(ln[:200] for ln in lines[:3]) or "no output file was produced"
        return f"Ghidra failed (exit {proc.returncode}): {detail}"

    def _stage(self, binary: str) -> tuple:
        """Copy the binary into a private folder under a hash name; returns (key, staged file, folder).

        The key is hashed from the copy, so it always matches the bytes Ghidra imports, and two
        parallel runs on the same binary never share (or delete) each other's input.
        """
        path = Path(binary).expanduser()
        if not path.is_file():
            raise RuntimeError(f"Binary not found: {binary}")
        inputs = self.home / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(dir=inputs))
        try:
            incoming = staging / "incoming"
            shutil.copyfile(path, incoming)
            key = file_key(incoming)
            staged = staging / f"{key}.bin"
            incoming.rename(staged)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return key, staged, staging

    def analyze(self, binary: str, loader: str | None = None, processor: str | None = None,
                entry: str | None = None, timeout: int = DEFAULT_ANALYSIS_TIMEOUT) -> dict:
        args_extra = []
        if loader:
            args_extra += ["-loader", check(loader, _LOADER, "loader")]
        if processor:
            args_extra += ["-processor", check(processor, _PROCESSOR, "processor")]
        entry_arg = check(entry, _ADDRESS, "entry address") if entry else ""
        key, staged, staging = self._stage(binary)
        try:
            with self._scratch() as tmp:
                out = Path(tmp) / "out.json"
                info = self._run(
                    [key, "-import", str(staged), "-overwrite", "-analysisTimeoutPerFile", str(int(timeout))]
                    + args_extra
                    + ["-scriptPath", str(SCRIPTS_DIR), "-postScript", SCRIPT_NAME, "info", str(out)]
                    + ([entry_arg] if entry_arg else []),
                    out, int(timeout) + 120,
                )
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return {"key": key, **info}

    def query(self, binary: str, command: str, target: str | None = None, timeout: int | None = None) -> Any:
        timeout = timeout or self.query_timeout
        path = Path(binary).expanduser()
        if not path.is_file():
            raise RuntimeError(f"Binary not found: {binary}")
        key = file_key(path)
        if not (self.projects / f"{key}.gpr").is_file():
            raise RuntimeError(f"{binary} has not been analyzed yet. Run: cli-anything-ghidra analyze {binary}")
        target_arg = check(target, _TARGET, "target") if target else ""
        with self._scratch() as tmp:
            out = Path(tmp) / "out.json"
            return self._run(
                [key, "-process", f"{key}.bin", "-noanalysis", "-readOnly",
                 "-scriptPath", str(SCRIPTS_DIR), "-postScript", SCRIPT_NAME, command, str(out)]
                + ([target_arg] if target_arg else []),
                out, timeout,
            )
