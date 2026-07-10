"""LibreOffice backend — invoke LibreOffice headless for format conversions.

This module is the bridge between the CLI and the real LibreOffice installation.
Instead of reimplementing document rendering, we generate valid ODF files and
then use `libreoffice --headless --convert-to` to produce PDF, DOCX, XLSX, PPTX,
and other formats that require the full LibreOffice engine.

Requires: libreoffice (system package)
    apt install libreoffice   # Debian/Ubuntu
    brew install --cask libreoffice   # macOS
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


# Conservative flags used for every headless invocation. Each one suppresses an
# interactive UI surface that headless conversions should never need:
#   --headless           no GUI
#   --nologo             no startup splash
#   --nodefault          do not open any default doc/start center
#   --norestore          do not try to restore a crashed session
#   --nolockcheck        ignore stale .~lock files left by a prior Office run
#   --nofirststartwizard skip first-run setup
#
# These are particularly important on macOS, where stale lock files from prior
# Office runs and the start center can both trigger SIGABRT ("Trace/BPT trap")
# during headless conversion — see upstream bug
# https://bugs.documentfoundation.org/show_bug.cgi?id=169711.
_HEADLESS_FLAGS = (
    "--headless",
    "--nologo",
    "--nodefault",
    "--norestore",
    "--nolockcheck",
    "--nofirststartwizard",
)


def find_libreoffice() -> str:
    """Find the LibreOffice executable.

    Returns the absolute path to the libreoffice/soffice binary.
    Searches PATH first, then common installation directories on each platform.
    Raises RuntimeError if not found.
    """
    # 1) Check PATH
    for name in ("libreoffice", "soffice"):
        path = shutil.which(name)
        if path:
            return path

    # 2) Check common installation paths (Windows)
    if sys.platform == "win32" or os.name == "nt" or "MSYS" in os.environ.get("MSYSTEM", "") or "msys" in sys.platform or os.path.exists("C:/"):
        win_candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                         "LibreOffice", "program", "soffice.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                         "LibreOffice", "program", "soffice.exe"),
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for candidate in win_candidates:
            if os.path.isfile(candidate):
                return candidate

    # 3) Check common installation paths (macOS)
    mac_candidate = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.isfile(mac_candidate):
        return mac_candidate

    raise RuntimeError(
        "LibreOffice is not installed. Install it with:\n"
        "  apt install libreoffice          # Debian/Ubuntu\n"
        "  brew install --cask libreoffice   # macOS\n"
        "  winget install TheDocumentFoundation.LibreOffice  # Windows"
    )


def get_version() -> str:
    """Get the installed LibreOffice version string."""
    lo = find_libreoffice()
    try:
        result = subprocess.run(
            [lo, "--headless", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        version = result.stdout.strip()
        if version:
            return version
        # Some Windows builds print to stderr
        if result.stderr.strip():
            return result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return f"LibreOffice (path: {lo})"


def _macos_app_bundle(soffice_path: str) -> Optional[str]:
    """Return the .app bundle path for a macOS soffice binary, or None.

    Detects layouts like ``/Applications/LibreOffice.app/Contents/MacOS/soffice``
    and returns ``/Applications/LibreOffice.app``. Used to drive the
    ``open -W -n -a <bundle>`` fallback when a direct headless invocation
    aborts during conversion.
    """
    if sys.platform != "darwin":
        return None
    p = Path(soffice_path).resolve()
    for ancestor in p.parents:
        if ancestor.suffix == ".app":
            return str(ancestor)
    return None


def _looks_like_macos_abort(result: subprocess.CompletedProcess) -> bool:
    """Detect the macOS SIGABRT pattern reported in issue #221.

    On macOS, soffice's headless conversion sometimes aborts with a negative
    return code (signal) or a "Trace/BPT trap" / "Abort trap" stderr message
    before producing any output. Treat any of those as a candidate for the
    LaunchServices retry path.
    """
    if result.returncode < 0:
        return True
    stderr = (result.stderr or "").lower()
    return "trace/bpt trap" in stderr or "abort trap" in stderr


def _convert_via_launchservices(
    app_bundle: str,
    output_format: str,
    output_dir: str,
    input_path: str,
    profile_uri: str,
    timeout: int,
) -> subprocess.CompletedProcess:
    """Re-attempt a conversion through ``open -W -n -a <bundle> --args …``.

    LaunchServices spawns the .app bundle through the standard macOS app
    activation pathway, which avoids some of the headless-abort scenarios that
    direct ``soffice`` invocation can hit. ``open`` does not proxy the child's
    stdout/stderr, so callers must verify success by checking for the expected
    output file.
    """
    cmd = [
        "open", "-W", "-n", "-a", app_bundle, "--args",
        *_HEADLESS_FLAGS,
        f"-env:UserInstallation={profile_uri}",
        "--convert-to", output_format,
        "--outdir", output_dir,
        input_path,
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
    )


def _macos_conversion_error(
    cmd: list[str],
    result: subprocess.CompletedProcess,
    input_path: str,
    output_dir: str,
) -> RuntimeError:
    """Build a clear, actionable error for the macOS headless-abort case."""
    return RuntimeError(
        "LibreOffice headless conversion failed on macOS even after the "
        "LaunchServices fallback. This commonly tracks upstream LibreOffice "
        "bug https://bugs.documentfoundation.org/show_bug.cgi?id=169711, "
        "where headless conversion can SIGABRT in some macOS environments.\n"
        f"  Last command: {' '.join(cmd)}\n"
        f"  Return code:  {result.returncode}\n"
        f"  stderr:       {(result.stderr or '').strip()}\n"
        "Manual workarounds to try:\n"
        f"  1) Re-run with an isolated profile yourself:\n"
        f"     /Applications/LibreOffice.app/Contents/MacOS/soffice \\\n"
        f"       -env:UserInstallation=file:///tmp/lo-profile-$$ \\\n"
        f"       --headless --nologo --nodefault --norestore --nolockcheck \\\n"
        f"       --convert-to <fmt> --outdir {output_dir} {input_path}\n"
        f"  2) Force the LaunchServices path manually:\n"
        f"     open -W -n -a 'LibreOffice' --args --headless --convert-to <fmt> "
        f"--outdir {output_dir} {input_path}"
    )


def convert(
    input_path: str,
    output_format: str,
    output_dir: Optional[str] = None,
    timeout: int = 120,
) -> str:
    """Convert a file using LibreOffice headless.

    Args:
        input_path: Path to the input file (ODF, HTML, etc.)
        output_format: Target format (pdf, docx, xlsx, pptx, txt, html, png, etc.)
        output_dir: Directory for the output file. Defaults to same dir as input.
        timeout: Maximum seconds to wait for conversion.

    Returns:
        Absolute path to the converted output file.

    Raises:
        RuntimeError: If LibreOffice is not installed or conversion fails.
        FileNotFoundError: If the input file doesn't exist.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    lo = find_libreoffice()
    input_path = os.path.abspath(input_path)

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile_dir, \
            tempfile.TemporaryDirectory(prefix="lo-runtime-") as runtime_dir, \
            tempfile.TemporaryDirectory(prefix="lo-config-") as config_dir, \
            tempfile.TemporaryDirectory(prefix="lo-cache-") as cache_dir:
        env = os.environ.copy()
        if os.name == "posix":
            try:
                os.chmod(runtime_dir, 0o700)
            except OSError:
                pass
            env.update({
                "XDG_RUNTIME_DIR": runtime_dir,
                "XDG_CONFIG_HOME": config_dir,
                "XDG_CACHE_HOME": cache_dir,
            })

        profile_uri = Path(profile_dir).resolve().as_uri()

        cmd = [
            lo,
            *_HEADLESS_FLAGS,
            f"-env:UserInstallation={profile_uri}",
            "--convert-to", output_format,
            "--outdir", output_dir,
            input_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout,
            env=env,
        )

        base = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{base}.{output_format}")

        # macOS: if the direct invocation aborted or produced no output,
        # retry through LaunchServices once. See issue #221.
        if (sys.platform == "darwin"
                and (result.returncode != 0
                     or _looks_like_macos_abort(result)
                     or not os.path.exists(output_path))):
            app_bundle = _macos_app_bundle(lo)
            if app_bundle is not None:
                fallback = _convert_via_launchservices(
                    app_bundle, output_format, output_dir,
                    input_path, profile_uri, timeout,
                )
                if os.path.exists(output_path):
                    return os.path.abspath(output_path)
                # LaunchServices also failed — surface a macOS-specific error
                # with manual workarounds before the generic path takes over.
                raise _macos_conversion_error(
                    cmd, fallback, input_path, output_dir,
                )

    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed (exit {result.returncode}):\n"
            f"  Command: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}"
        )

    if not os.path.exists(output_path):
        raise RuntimeError(
            f"LibreOffice conversion produced no output file.\n"
            f"  Expected: {output_path}\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )

    return os.path.abspath(output_path)


def convert_odf_to(
    odf_path: str,
    output_format: str,
    output_path: Optional[str] = None,
    overwrite: bool = False,
    timeout: int = 120,
) -> dict:
    """Convert an ODF file to another format via LibreOffice headless.

    This is the high-level function used by the CLI export pipeline.

    Args:
        odf_path: Path to the ODF file (.odt, .ods, .odp).
        output_format: Target format (pdf, docx, xlsx, pptx, etc.).
        output_path: Desired output path. If None, uses same dir as input.
        overwrite: Allow overwriting existing output files.
        timeout: Maximum seconds for conversion.

    Returns:
        Dict with output path, format, and file size.
    """
    if output_path and os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"Output file exists: {output_path}. Use --overwrite."
        )

    # Convert to a temp dir first, then move to desired location
    with tempfile.TemporaryDirectory() as tmpdir:
        converted = convert(odf_path, output_format, output_dir=tmpdir, timeout=timeout)

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            shutil.move(converted, output_path)
            final_path = os.path.abspath(output_path)
        else:
            # Move to same directory as input
            dest_dir = os.path.dirname(os.path.abspath(odf_path))
            dest = os.path.join(dest_dir, os.path.basename(converted))
            if os.path.exists(dest) and not overwrite:
                raise FileExistsError(f"Output file exists: {dest}. Use --overwrite.")
            shutil.move(converted, dest)
            final_path = os.path.abspath(dest)

    return {
        "action": "convert",
        "output": final_path,
        "format": output_format,
        "method": "libreoffice-headless",
        "libreoffice_version": get_version(),
        "file_size": os.path.getsize(final_path),
    }
