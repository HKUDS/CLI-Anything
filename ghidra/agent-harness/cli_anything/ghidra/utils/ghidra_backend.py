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

import contextlib
import hashlib
import json
import locale
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

try:  # Windows
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None
    import fcntl

INSTALL_ENV = "GHIDRA_INSTALL_DIR"
JAVA_ENV = "GHIDRA_JAVA_HOME"
HOME_ENV = "CLI_ANYTHING_GHIDRA_HOME"
SCRIPT_NAME = "CliAnythingQuery.java"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
DEFAULT_ANALYSIS_TIMEOUT = 600
QUERY_TIMEOUT = 300


_TARGET = re.compile(r"^[A-Za-z0-9_.$@?][A-Za-z0-9_.$@?:-]{0,199}$")  # ":" for spaces like ram:00401000
_ADDRESS = re.compile(r"^(0x)?[0-9a-fA-F]{1,16}$")
_LOADER = re.compile(r"^[A-Za-z0-9_]{1,60}$")
_PROCESSOR = re.compile(r"^[A-Za-z0-9_.+-]+:(LE|BE):\d+:[A-Za-z0-9_.+-]+$")

IS_WINDOWS = os.name == "nt"
ANALYZED_SUFFIX = ".analyzed"  # marker written only after a successful analyze: a .gpr alone proves nothing
_CONTROL = frozenset(chr(10) + chr(13) + chr(0))
POSIX_FALLBACK_BASE = Path("/var/tmp")
_PATH_SEPARATORS = "/:" + chr(92)  # separators and the drive colon are not part of a name
_GHIDRA_NAME_EXTRA = frozenset(" _-.~@+[]")
_PATH_UNSAFE = frozenset('&|<>^%!()"') | _CONTROL

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
    """Refuse paths the launcher cannot take.

    On Windows the launcher is a .bat run by cmd.exe, which splits or expands & | < > ^ % ! and quotes,
    and the script itself exits with 255 on parentheses. On POSIX it is a shell script started without
    a shell, so only newline, CR and NUL are refused.
    """
    text = str(path)
    if IS_WINDOWS and any(c in _PATH_UNSAFE for c in text):
        raise RuntimeError(
            f"The {what} {text!r} contains a character that cmd.exe or the Ghidra launcher "
            "script cannot take (& | < > ^ % ! ( ) or a quote). "
            f"Use another folder (for the work folder set {HOME_ENV})."
        )
    if any(c in _CONTROL for c in text):
        raise RuntimeError(f"The {what} contains a newline or NUL character.")
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


def _try_lock(handle) -> bool:
    """Take an exclusive, non-blocking lock on the first byte of the lock file."""
    handle.seek(0)
    try:
        if msvcrt:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle) -> None:
    handle.seek(0)
    if msvcrt:
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle, fcntl.LOCK_UN)


def ghidra_version(launcher: Path) -> str:
    """Build of the Ghidra install the launcher belongs to (application.version in Ghidra/application.properties)."""
    props = Path(launcher).parent.parent / "Ghidra" / "application.properties"
    try:
        for line in props.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("application.version="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


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


def ghidra_path_problem(path: str) -> str | None:
    """The first character Ghidra refuses in a project path, or None.

    Probed with Ghidra 12.2: letters and digits are accepted if the Windows code page can represent them
    (so "J\u00fcrgen M\u00fcller" works), plus space and _ - . ~ @ + [ ]. Refused: $ { } , ; = ` ' # and currency or
    other symbols, and letters outside the code page (CJK names). A user whose profile path contains one of them
    cannot use a work folder inside it.
    """
    codepage = locale.getpreferredencoding(False)
    for ch in path:
        if ch in _PATH_SEPARATORS or ch in _GHIDRA_NAME_EXTRA:
            continue
        try:
            ch.encode(codepage)
        except (UnicodeEncodeError, LookupError):
            return ch
        if not ch.isalnum():
            return ch
    return None


def _home_problem(home: Path) -> str | None:
    dotted = [p for p in home.parts if p.startswith(".")]
    if dotted:
        return f"Ghidra cannot use a project path containing {dotted[0]!r} (folders starting with '.')."
    bad = ghidra_path_problem(str(home))
    if bad is not None:
        return f"Ghidra cannot use a project path containing the character {bad!r} ({home})."
    return None


def _short_path(path: Path) -> Path | None:
    """The 8.3 alias of an existing Windows folder: ASCII-only, and still inside the user's own profile."""
    try:
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    except (AttributeError, OSError, ImportError):
        return None
    return Path(buffer.value) if 0 < length < len(buffer) else None


def _private_dir(path: Path) -> Path:
    """Create `path` for this user only, or verify that an existing one really is theirs.

    The base folder is shared and the name is guessable, so another local user could have created it first
    (or put a symlink there). An existing folder is accepted only if it is a real directory owned by this user
    that nobody else can write to or read.
    """
    try:
        path.mkdir(mode=0o700, parents=True)
    except FileExistsError:
        info = path.lstat()
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise RuntimeError(f"{path} exists but is not a private folder of this user (owner, permissions or "
                               f"symlink). Remove it, or set {HOME_ENV} to a folder of your own.")
    return path


def _fallback_home() -> Path | None:
    """An ASCII-safe work folder for a profile path Ghidra cannot take, or None when there is none.

    Windows: the 8.3 alias of the profile folder, so it stays per-user and protected by the profile's own
    permissions (None if 8.3 names are disabled on the volume). POSIX: a private 0700 folder per user under
    /var/tmp, verified when it already exists. A shared folder with a guessable name would let another local
    user pre-create it, so there is no ProgramData-style shared fallback.
    """
    if IS_WINDOWS:
        short = _short_path(Path.home())
        return short / "cli-anything-ghidra" if short else None
    tag = hashlib.sha256(str(Path.home()).encode("utf-8", "replace")).hexdigest()[:8]
    return _private_dir(POSIX_FALLBACK_BASE / f"cli-anything-ghidra-{tag}")


def work_home() -> Path:
    """Where projects and staged inputs live: CLI_ANYTHING_GHIDRA_HOME, else ~/cli-anything-ghidra, else (when
    Ghidra cannot take the profile path, for example O'Neil or a CJK name) an ASCII-safe per-user folder."""
    explicit = os.environ.get(HOME_ENV)
    # (how to build the folder, whether to resolve it): the 8.3 alias must not be resolved back to the long name
    sources = ([(lambda: Path(explicit), True)] if explicit
               else [(lambda: Path.home() / "cli-anything-ghidra", True), (_fallback_home, False)])
    problem = f"No usable work folder. Set {HOME_ENV}."
    for build, resolve in sources:
        candidate = build()
        if candidate is None:
            continue
        home = candidate.expanduser()
        home = home.resolve() if resolve else home.absolute()
        problem = _home_problem(home)
        if problem is None:
            return home
    raise RuntimeError(f"{problem} Set {HOME_ENV} to a folder whose path uses only letters, digits, space and "
                       "_ - . ~ @ + [ ].")


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
        self.ghidra = ghidra_version(self.launcher)
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

    @staticmethod
    def _stop(proc: "subprocess.Popen") -> None:
        """Kill the launcher's whole tree and reap it; never wait forever for a stubborn child."""
        _kill_tree(proc)
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    def _run(self, args: list, output: Path, timeout: int) -> tuple:
        """Run the launcher; returns (data from the post-script's JSON file, Ghidra's log text)."""
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
            self._stop(proc)
            raise RuntimeError(f"Ghidra timed out after {timeout}s. Raise --timeout or analyze a smaller binary.")
        except BaseException:  # Ctrl-C and friends: the launcher has its own process group, so stop it here
            self._stop(proc)
            raise
        if not output.is_file():
            raise RuntimeError(self._failure(subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)))
        try:
            return json.loads(output.read_text(encoding="utf-8")), (stdout or "") + (stderr or "")
        except ValueError:
            raise RuntimeError("Ghidra left an unreadable result file (killed mid-write?). Run the command again.")

    @staticmethod
    def _failure(proc: subprocess.CompletedProcess) -> str:
        """Explain a run that produced no result file, from the launcher's exit code and log.

        Observed with Ghidra 12.2: exit 0 with "Import failed"/"No load spec found" in the log, exit 1 with an
        ERROR line (bad option, missing folder, "Unable to lock project!"), exit 255 from cmd.exe alone (a single
        localized syntax-error line, no ERROR line) when a path contains parentheses.
        """
        text = (proc.stdout or "") + (proc.stderr or "")
        if "JDK" in text and "could not be found" in text:
            return f"Ghidra could not find a supported JDK (12.x needs 25+). Set {JAVA_ENV} to a JDK 25+ folder."
        if "No load spec found" in text:
            return ("Ghidra does not recognize the file format. For raw firmware or shellcode pass "
                    "--loader BinaryLoader --processor <language id, e.g. x86:LE:64:default>.")
        if "Unable to lock project" in text or "LockException" in text:
            return "The Ghidra project for this binary is busy (another analyze or query runs). Retry in a moment."
        lines = [ln.strip() for ln in text.splitlines() if "ERROR" in ln or "Exception" in ln]
        if lines:
            detail = " | ".join(ln[:200] for ln in lines[:3])
        else:
            tail = [ln.strip() for ln in text.splitlines() if ln.strip()][-2:]
            if IS_WINDOWS and proc.returncode == 255:
                detail = ("cmd.exe could not parse the launcher command line, usually because a path contains "
                          "a special character such as a parenthesis" + (f" ({tail[-1][:120]})" if tail else ""))
            else:
                detail = " | ".join(t[:160] for t in tail) or "the launcher printed nothing"
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

    @contextlib.contextmanager
    def _locked(self, key: str, wait: float):
        """Serialize runs on one binary. Ghidra locks the project even for read-only queries, so a parallel
        call would fail with "Unable to lock project"; here it waits up to `wait` seconds for the other run."""
        locks = self.home / "locks"  # not in the project folder: Ghidra's own project lock is <name>.lock there
        locks.mkdir(parents=True, exist_ok=True)
        handle = open(locks / f"{key}.lock", "a+b")
        try:
            if handle.seek(0, 2) == 0:  # the lock needs one byte to lock
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + wait
            while not _try_lock(handle):
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"The Ghidra project for this binary stayed busy for {int(wait)}s "
                                       "(another analyze or query is running). Retry later.")
                time.sleep(0.2)
            try:
                yield
            finally:
                _unlock(handle)
        finally:
            handle.close()

    def _cached(self, path: Path, options: dict) -> dict | None:
        """Stored result of an earlier, complete analyze of the same bytes with the same options."""
        key = file_key(path)
        try:
            saved = json.loads((self.projects / f"{key}{ANALYZED_SUFFIX}").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(saved, dict) or saved.get("options") != options or saved.get("timed_out"):
            return None
        if saved.get("ghidra") != self.ghidra:  # another Ghidra build was selected: its analysis may differ
            return None
        return {"key": key, **saved["info"], "analysis_timed_out": False, "cached": True}

    def analyze(self, binary: str, loader: str | None = None, processor: str | None = None,
                entry: str | None = None, timeout: int = DEFAULT_ANALYSIS_TIMEOUT, force: bool = False) -> dict:
        """Import and analyze once; the same bytes with the same options are reused unless force is set."""
        args_extra = []
        if loader:
            args_extra += ["-loader", check(loader, _LOADER, "loader")]
        if processor:
            args_extra += ["-processor", check(processor, _PROCESSOR, "processor")]
        entry_arg = check(entry, _ADDRESS, "entry address") if entry else ""
        options = {"loader": loader or "", "processor": processor or "", "entry": entry_arg}
        path = Path(binary).expanduser()
        if not path.is_file():
            raise RuntimeError(f"Binary not found: {binary}")
        cached = None if force else self._cached(path, options)
        if cached:
            return cached
        key, staged, staging = self._stage(binary)
        marker = self.projects / f"{key}{ANALYZED_SUFFIX}"
        try:
            with self._locked(key, int(timeout) + 120):
                cached = None if force else self._cached(path, options)  # a parallel analyze may have finished
                if cached:
                    return cached
                marker.unlink(missing_ok=True)  # a failed re-analysis must not leave the old "analyzed" claim
                with self._scratch() as tmp:
                    out = Path(tmp) / "out.json"
                    info, log = self._run(
                        [key, "-import", str(staged), "-overwrite", "-analysisTimeoutPerFile", str(int(timeout))]
                        + args_extra
                        + ["-scriptPath", str(SCRIPTS_DIR), "-postScript", SCRIPT_NAME, "info", str(out)]
                        + ([entry_arg] if entry_arg else []),
                        out, int(timeout) + 120,
                    )
                # Ghidra ends a timed-out analysis with exit 0 and a partial result, so say so.
                timed_out = "Analysis timed out" in log
                saved = {"options": options, "ghidra": self.ghidra, "timed_out": timed_out, "info": info}
                marker.write_text(json.dumps(saved),
                                  encoding="utf-8")
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return {"key": key, **info, "analysis_timed_out": timed_out, "cached": False}

    def query(self, binary: str, command: str, target: str | None = None, timeout: int | None = None) -> Any:
        timeout = timeout or self.query_timeout
        path = Path(binary).expanduser()
        if not path.is_file():
            raise RuntimeError(f"Binary not found: {binary}")
        key = file_key(path)
        extra = [check(target, _TARGET, "target")] if target else []
        if command == "decompile":  # the decompiler's own budget; the JVM start-up is not part of it
            extra.append(str(max(10, timeout - 30)))
        with self._locked(key, timeout):  # parallel calls on the same binary queue up instead of failing
            if not (self.projects / f"{key}{ANALYZED_SUFFIX}").is_file():
                raise RuntimeError(f"{binary} has not been analyzed yet. Run: cli-anything-ghidra analyze {binary}")
            with self._scratch() as tmp:
                out = Path(tmp) / "out.json"
                data, _ = self._run(
                    [key, "-process", f"{key}.bin", "-noanalysis", "-readOnly",
                     "-scriptPath", str(SCRIPTS_DIR), "-postScript", SCRIPT_NAME, command, str(out)] + extra,
                    out, timeout,
                )
                return data
