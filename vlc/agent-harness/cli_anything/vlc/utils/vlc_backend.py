"""Backend bridge to the real VLC binary.

This module NEVER reimplements media processing in Python. It only locates the VLC
binary and invokes it with command lines built by ``core/transcode.py``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List

from ..core.transcode import (
    build_transcode_sout,
    build_stream_sout,
    build_snapshot_args,
)
from ..core.media import parse_vlc_stats

# `info` plays the input only long enough for VLC to emit stats, so a probe returns in
# bounded time regardless of how long the media is.
_INFO_PROBE_SECONDS = 2


def _identifies_as_vlc(binary: Path) -> bool:
    """Ask the candidate for its version and require it to name VLC.

    Scoped to an explicit ``VLC_BINARY``: a PATH entry literally called ``vlc`` needs no
    such probe, and putting one on the hot path of every media command would add a
    subprocess to each run for no gain.
    """
    try:
        result = subprocess.run([str(binary), "--version"], capture_output=True,
                                text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    # A zero status *and* the VLC signature: a binary that prints "VLC" but exits
    # nonzero is broken, and `doctor` must not call that ready.
    if result.returncode != 0:
        return False
    combined = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
    return "vlc" in combined


def find_vlc() -> Path:
    """Locate the VLC binary.

    Honours ``VLC_BINARY`` (absolute path). Otherwise searches ``PATH`` for
    ``vlc`` / ``cvlc`` / ``vlc.exe``. Raises ``RuntimeError`` with install
    instructions when not found — this is a hard dependency, never skipped.
    """
    env = os.environ.get("VLC_BINARY")
    if env:
        p = Path(env)
        if p.is_file() and (os.name != "posix" or os.access(p, os.X_OK)):
            # Runnable is not the same as being VLC: /bin/true used to satisfy this
            # branch, so `doctor` reported ready on a machine with no VLC at all.
            if not _identifies_as_vlc(p):
                raise RuntimeError(
                    f"VLC_BINARY is set to '{env}', which runs but does not identify as "
                    "VLC. Unset VLC_BINARY to search PATH, or point it at the real "
                    "vlc/vlc.exe executable."
                )
            return p
        # An explicit VLC_BINARY that points nowhere runnable must fail loudly so
        # `doctor` does not report ready against something unusable.
        raise RuntimeError(
            f"VLC_BINARY is set to '{env}', which is not an executable VLC binary. "
            "Unset VLC_BINARY to search PATH, or point it at the vlc/vlc.exe executable."
        )
    for name in ("vlc", "cvlc", "vlc.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
    raise RuntimeError(
        "VLC not found on PATH. Install VLC (https://www.videolan.org/vlc/) and ensure "
        "'vlc' is on PATH, or set VLC_BINARY to the absolute binary path."
    )


def run_transcode(job: Dict[str, Any], timeout: int = 600) -> Dict[str, Any]:
    """Transcode the first input to the job's output using the real VLC engine."""
    vlc = find_vlc()
    inputs = job.get("inputs") or []
    if not inputs:
        raise ValueError("job has no inputs")
    out = job["output"]["path"]

    # P1: never let the output clobber the source VLC is still reading.
    if Path(out).resolve() == Path(inputs[0]).resolve():
        raise ValueError(
            f"refusing to transcode: output '{out}' aliases the input '{inputs[0]}'"
        )

    # P1: write to a temp sibling and replace on success, so a pre-existing
    # destination can never be mistaken for a freshly produced result when VLC
    # exits 0 without writing anything.
    final = Path(out)
    final.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".vlc-tc-", suffix=final.suffix or ".tmp",
                                    dir=str(final.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    tmp.unlink(missing_ok=True)  # let VLC create the file fresh

    tmp_job = dict(job)
    tmp_job["output"] = dict(job.get("output", {}))
    tmp_job["output"]["path"] = str(tmp)
    chain = build_transcode_sout(tmp_job)
    cmd: List[str] = [
        str(vlc), "-I", "dummy", "--play-and-exit", "--quiet",
        "--sout", chain, str(inputs[0]),
    ]
    published = False
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"vlc exited {result.returncode}: {result.stderr[-800:]}")
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise RuntimeError(f"VLC produced no output for {out}\n{result.stderr[-800:]}")
        os.replace(tmp, final)  # atomic publish only after a genuine, non-empty write
        published = True
    finally:
        # A subprocess timeout (or any other failure) raises before the cleanup
        # branches above would run, which used to leave a partial `.vlc-tc-*`
        # sibling beside the destination; repeated slow jobs then ate disk.
        if not published:
            tmp.unlink(missing_ok=True)
    p = final
    return {
        "output": str(p),
        "format": job["output"].get("format"),
        "file_size": p.stat().st_size,
        "method": "vlc-transcode",
        "returncode": result.returncode,
    }


def run_stream(job: Dict[str, Any], run_time: int = None, timeout: int = None) -> Dict[str, Any]:
    """Stream the first input over the network using the real VLC engine.

    ``run_time`` keeps the process bounded so it exits (used by tests / demos).
    Omitting it (``run_time=None``) yields a persistent stream with no VLC time
    limit, matching the documented "omit --run-time" workflow.

    When ``run_time`` is set, the subprocess timeout is scaled with it so a long
    requested stream is not killed mid-run by the default 120s ceiling.
    """
    vlc = find_vlc()
    chain = build_stream_sout(job)
    inputs = job.get("inputs") or []
    if not inputs:
        raise ValueError("job has no inputs")
    s = job.get("stream") or {}
    if run_time is None:
        cmd: List[str] = [
            str(vlc), "-I", "dummy", "--play-and-exit", "--quiet",
            "--sout", chain, str(inputs[0]),
        ]
        effective_timeout = timeout  # None => unbounded (persistent)
        note = "persistent stream (no run-time limit)"
    else:
        cmd = [
            str(vlc), "-I", "dummy", "--play-and-exit", "--quiet",
            f"--run-time={run_time}",
            "--sout", chain, str(inputs[0]),
        ]
        # Always allow the process to outlive its requested run time by a margin.
        effective_timeout = max(int(timeout or 120), int(run_time) + 30)
        note = f"streamed for {run_time}s then exited"
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=effective_timeout)
    if result.returncode != 0:
        raise RuntimeError(f"vlc exited {result.returncode}: {result.stderr[-800:]}")
    return {
        "protocol": s.get("protocol", "rtp"),
        "destination": f"{s.get('dst', '127.0.0.1')}:{s.get('port', 1234)}",
        "method": "vlc-stream",
        "returncode": result.returncode,
        "note": note,
    }


def run_snapshot(job: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
    """Extract a still frame from the first input using VLC's scene video filter."""
    vlc = find_vlc()
    snap = job.get("snapshot") or {}
    out_dir = snap.get("path")
    if not out_dir:
        raise ValueError("snapshot.path (output directory) is required")
    inputs = job.get("inputs") or []
    if not inputs:
        raise ValueError("job has no inputs")
    scene_dir = Path(out_dir)
    scene_dir.mkdir(parents=True, exist_ok=True)
    # A unique prefix per invocation. VLC names scenes `<prefix>NNNNN.png`, so with a
    # fixed prefix a reused directory makes this run overwrite a file a previous run
    # already produced: the pathname-only diff against the pre-run set then comes out
    # empty and a successful refresh is misreported as a failure. Globbing only our
    # own prefix also keeps pre-existing PNGs out of both the result and the count.
    prefix = f"vlc-snap-{os.getpid()}-{uuid.uuid4().hex[:8]}-"
    args = build_snapshot_args(job, scene_prefix=prefix)
    cmd: List[str] = [str(vlc), "-I", "dummy", "--play-and-exit", *args, str(inputs[0])]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"vlc exited {result.returncode}: {result.stderr[-800:]}")
        produced = sorted(scene_dir.glob(f"{prefix}*.png"))
        if not produced:
            raise RuntimeError(f"VLC produced no new snapshot in {out_dir}\n{result.stderr[-800:]}")
    except Exception:
        # VLC can have written frames already when it fails or times out; those partial
        # PNGs would otherwise accumulate on every unsuccessful invocation, which adds
        # up fast for low-ratio jobs.
        for stray in scene_dir.glob(f"{prefix}*.png"):
            stray.unlink(missing_ok=True)
        raise
    # Most recent file this run produced (robust against naming/sort quirks).
    last = max(produced, key=lambda p: p.stat().st_mtime)
    return {
        "snapshot": str(last),
        "count": len(produced),
        "file_size": last.stat().st_size,
        "method": "vlc-scene",
    }


def run_info(input_path, timeout: int = 120) -> Dict[str, Any]:
    """Probe a media file via VLC dummy-mode stats (best-effort parse).

    Playback is deliberately bounded to ``_INFO_PROBE_SECONDS``: ``--play-and-exit``
    otherwise waits for EOF, so probing anything longer than ``timeout`` aborts
    instead of returning metadata, and shorter media still costs its full playback
    duration. The subprocess timeout is sized from that bound, not from media length.
    """
    vlc = find_vlc()
    cmd: List[str] = [
        str(vlc), "-I", "dummy", "--play-and-exit", "--stats",
        f"--run-time={_INFO_PROBE_SECONDS}",
        "--no-video-title-show", str(input_path),
    ]
    effective = max(int(timeout or 120), int(_INFO_PROBE_SECONDS) + 30)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=effective)
    if result.returncode != 0:
        raise RuntimeError(
            f"VLC exited {result.returncode} while probing {input_path}\n"
            f"{result.stderr[-800:]}"
        )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    info = parse_vlc_stats(combined)
    info["path"] = str(input_path)
    info["returncode"] = result.returncode
    try:
        info["size_bytes"] = Path(input_path).stat().st_size
    except OSError:
        pass
    return info
