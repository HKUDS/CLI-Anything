import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class BackendConfig:
    binary: str = "joplin"
    profile: Optional[str] = None


def find_joplin(binary: str = "joplin") -> str:
    path = shutil.which(binary)
    if path:
        return path
    raise RuntimeError(
        "Joplin terminal binary not found in PATH. Install Joplin CLI and ensure `joplin` is executable."
    )


_BENIGN_NODE_WARNING_MARKERS = (
    ("dep0040", "punycode"),
    ("dep0169", "url.parse"),
)


def _line_is_benign_node_warning(line: str) -> bool:
    """Return True for Node.js deprecation warnings that Joplin emits on stderr.

    These warnings are emitted on every invocation by Node 20+ when Joplin's
    dependencies still use the deprecated builtin modules. They never indicate
    a real Joplin failure, but they are noisy on stderr.
    """
    lowered = line.lower()
    if "deprecationwarning" not in lowered and "experimentalwarning" not in lowered:
        return False
    return any(all(marker in lowered for marker in markers) for markers in _BENIGN_NODE_WARNING_MARKERS)


def _line_is_node_warning_continuation(line: str) -> bool:
    """Return True for the hint line that Node prints after each deprecation warning.

    Node consistently follows each DeprecationWarning with a one-line hint of
    the form ``(Use `node --trace-deprecation ...` to show where the warning
    was created)``.  That line is *not* a warning header, so
    ``_line_is_benign_node_warning`` does not match it.  Without this check,
    the continuation line is kept and makes the scrubbed text non-empty,
    causing ``run_joplin_command`` to raise on what are purely benign warnings.
    """
    stripped = line.strip()
    lowered = stripped.lower()
    # The hint always starts with "(use" and references --trace-deprecation.
    return stripped.startswith("(Use ") or (
        lowered.startswith("(use") and "--trace-deprecation" in lowered
    )


def _strip_benign_node_warnings(text: str) -> str:
    """Return ``text`` with known-benign Node warning lines removed.

    The filter is line-based and drops:
    - Lines matching ``_line_is_benign_node_warning``
    - The immediately following hint/continuation line if it matches
      ``_line_is_node_warning_continuation`` (e.g. the "Use node
      --trace-deprecation ..." line Node always emits after each warning)
    - Blank padding lines that hug a dropped line

    Real diagnostic content is preserved verbatim, including blank lines
    between paragraphs. Callers must NOT use the returned value to replace
    ``stdout`` payloads -- it is only meant for the success/failure decision.
    """
    if not text:
        return ""
    lines = text.splitlines()
    benign_indices: set[int] = set()
    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped:
            continue
        if _line_is_benign_node_warning(stripped):
            benign_indices.add(idx)
            # Also drop the continuation/hint line that Node appends right
            # after each deprecation warning.
            next_idx = idx + 1
            if next_idx < len(lines) and _line_is_node_warning_continuation(lines[next_idx]):
                benign_indices.add(next_idx)
    if not benign_indices:
        return text.strip()
    # Drop the warning/continuation lines and blank padding around them,
    # but keep blank lines that are part of legitimate payload structure.
    kept: list[str] = []
    for idx, raw_line in enumerate(lines):
        if idx in benign_indices:
            continue
        if raw_line.strip() == "":
            prev_is_warning = (idx - 1) in benign_indices
            next_is_warning = (idx + 1) in benign_indices
            if prev_is_warning or next_is_warning:
                continue
        kept.append(raw_line)
    return "\n".join(kept).strip()


def run_joplin_command(args: list[str], config: BackendConfig, timeout: Optional[int] = 120) -> dict:
    binary = find_joplin(config.binary)
    cmd = [binary]
    if config.profile:
        cmd += ["--profile", config.profile]
    cmd += args

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Joplin command timed out after {timeout}s") from e  # timeout is non-None here

    # IMPORTANT: stdout is the caller's payload (note bodies, JSON dumps,
    # config exports, ...). Preserve it verbatim -- collapsing blank lines or
    # stripping whitespace here would corrupt multi-paragraph note content,
    # exported markdown, and any client that compares bytes/lines. Only the
    # error-decision branch uses a scrubbed view, and it never writes back.
    stdout_raw = proc.stdout or ""
    stderr_raw = proc.stderr or ""

    result = {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": stdout_raw,
        "stderr": stderr_raw,
    }

    if proc.returncode != 0:
        # Scrub a *copy* of stderr/stdout to decide whether the non-zero exit
        # is a real Joplin failure or just Node noise. The returned result
        # keeps the raw streams so callers still see the original output if
        # they want to log or diff it.
        #
        # Decision rule (fail-safe / positive-proof):
        #   - If the scrubbed streams are non-empty  → real error; raise.
        #   - If the raw streams are non-empty AND scrubbing emptied them
        #     → the only output was benign Node noise; treat as success.
        #   - If BOTH raw streams are empty           → the process exited
        #     non-zero without writing anything; this is still a failure
        #     (e.g. rmnote on a missing note, a killed server process, a
        #     propagated SIGTERM). Raise with a generic message so callers
        #     get ok=false rather than a silent ok=true.
        scrubbed_stderr = _strip_benign_node_warnings(stderr_raw)
        scrubbed_stdout = _strip_benign_node_warnings(stdout_raw)
        if scrubbed_stderr or scrubbed_stdout:
            # Real diagnostic content survived scrubbing.
            raise RuntimeError(scrubbed_stderr or scrubbed_stdout)
        if not stderr_raw and not stdout_raw:
            # Empty streams with a non-zero exit code: process failed silently.
            raise RuntimeError(
                f"Joplin command exited with code {proc.returncode} "
                f"without producing any output (command: {' '.join(cmd)})"
            )

    return result


def run_joplin_json(args: list[str], config: BackendConfig, timeout: Optional[int] = 120) -> dict:
    command_args = args if "--format" in args or "-f" in args else args + ["--format", "json"]
    raw = run_joplin_command(command_args, config, timeout=timeout)
    text = raw["stdout"]
    if not text:
        return {"raw": raw, "data": None}

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Joplin's CLI occasionally pipes a Node deprecation warning to stdout
        # ahead of the JSON payload. Retry once with the warning lines removed
        # so JSON parsing succeeds; falls back to the original text on the
        # raw key if even the scrubbed form fails to parse.
        scrubbed = _strip_benign_node_warnings(text)
        if scrubbed and scrubbed != text.strip():
            try:
                data = json.loads(scrubbed)
            except json.JSONDecodeError:
                data = {"text": text}
        else:
            data = {"text": text}

    return {"raw": raw, "data": data}
