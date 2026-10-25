"""Transcription domain — wraps `voxtype transcribe FILE`.

voxtype runs VAD, the configured ASR engine, and the text pipeline
(replacements, spoken punctuation, filler filtering). This module only
normalizes the input audio (via ffmpeg) and parses voxtype's report.
"""

import glob
import os
import re
import shutil
import tempfile
import time
from typing import Optional

from cli_anything.voxtype.core import project as project_mod
from cli_anything.voxtype.utils import audio as audio_mod
from cli_anything.voxtype.utils import voxtype_backend as backend

AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".webm", ".mka", ".mp4")

_RE_FORMAT = re.compile(r"^Audio format:\s*(\d+)\s*Hz,\s*(\d+)\s*channel")
_RE_PROCESS = re.compile(r"^Processing\s+(\d+)\s+samples\s+\(([\d.]+)s\)")
_RE_VAD = re.compile(r"^VAD:\s*([\d.]+)s speech\s*\(([\d.]+)% of audio\)")


def parse_transcribe_output(stdout: str) -> dict:
    """Parse the human report printed by `voxtype transcribe`.

    Layout (src/app/transcribe_file.rs):
        Loading audio file: "..."
        Audio format: 16000 Hz, 1 channel(s), Int
        [Resampling from N Hz to 16000 Hz...]
        Processing N samples (X.XXs)...
        [VAD: X.XXs speech (Y.Y% of audio)]
        [No speech detected, skipping transcription.]
        <blank>
        <transcript, possibly multi-line>
    """
    result = {
        "text": "",
        "sample_rate_in": None,
        "channels_in": None,
        "resampled": False,
        "samples": None,
        "duration_secs": None,
        "vad": None,
        "no_speech": False,
    }
    lines = stdout.splitlines()
    transcript_start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if m := _RE_FORMAT.match(s):
            result["sample_rate_in"] = int(m.group(1))
            result["channels_in"] = int(m.group(2))
        elif s.startswith("Resampling from"):
            result["resampled"] = True
        elif m := _RE_PROCESS.match(s):
            result["samples"] = int(m.group(1))
            result["duration_secs"] = float(m.group(2))
        elif m := _RE_VAD.match(s):
            result["vad"] = {"speech_secs": float(m.group(1)), "speech_percent": float(m.group(2))}
        elif s.startswith("No speech detected"):
            result["no_speech"] = True
        elif s == "" and result["samples"] is not None and transcript_start is None:
            transcript_start = i + 1
    if transcript_start is not None and not result["no_speech"]:
        result["text"] = "\n".join(lines[transcript_start:]).strip()
    return result


def collect_inputs(paths: list[str], recursive: bool = False) -> list[str]:
    """Expand files, directories and globs into a sorted list of audio files."""
    found: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            pattern = os.path.join(p, "**", "*") if recursive else os.path.join(p, "*")
            found += [f for f in glob.glob(pattern, recursive=recursive)
                      if os.path.isfile(f) and f.lower().endswith(AUDIO_EXTENSIONS)]
        elif any(ch in p for ch in "*?["):
            found += [f for f in glob.glob(p, recursive=recursive) if os.path.isfile(f)]
        elif os.path.isfile(p):
            found.append(p)
        else:
            raise FileNotFoundError(f"Audio input not found: {p}")
    seen, out = set(), []
    for f in sorted(os.path.abspath(x) for x in found):
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def prepare_audio(path: str, workdir: str) -> tuple[str, bool]:
    """Return (path_voxtype_can_read, converted?). Converts with ffmpeg if needed."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")
    if not audio_mod.needs_conversion(path):
        return path, False
    base = os.path.splitext(os.path.basename(path))[0]
    dst = os.path.join(workdir, f"{base}.16k.wav")
    backend.convert_to_wav16k(path, dst)
    return dst, True


def transcribe_file(path: str, config_path: Optional[str] = None,
                    overrides: Optional[dict] = None, engine: Optional[str] = None,
                    keep_converted: Optional[str] = None, timeout: int = 900) -> dict:
    """Transcribe one audio file with the real voxtype binary."""
    overrides = dict(overrides or {})
    flags = project_mod.override_flags(overrides)
    workdir = tempfile.mkdtemp(prefix="cli-anything-voxtype-")
    try:
        src, converted = prepare_audio(path, workdir)
        args = ["transcribe", src]
        if engine:
            args += ["--engine", engine]
        t0 = time.time()
        proc = backend.run(args, config_path, global_flags=flags, timeout=timeout)
        elapsed = time.time() - t0
        parsed = parse_transcribe_output(proc.stdout)
        if parsed["samples"] is None:
            raise backend.VoxtypeError(
                f"Unexpected output from voxtype transcribe: {proc.stdout[-300:]!r}",
                stdout=proc.stdout, stderr=proc.stderr)
        if keep_converted and converted:
            os.makedirs(os.path.dirname(os.path.abspath(keep_converted)) or ".", exist_ok=True)
            shutil.copy2(src, keep_converted)
        text = parsed["text"]
        return {
            "file": os.path.abspath(path),
            "text": text,
            "words": len(text.split()) if text else 0,
            "characters": len(text),
            "duration_secs": parsed["duration_secs"],
            "samples": parsed["samples"],
            "sample_rate_in": parsed["sample_rate_in"],
            "channels_in": parsed["channels_in"],
            "resampled": parsed["resampled"],
            "converted": converted,
            "vad": parsed["vad"],
            "no_speech": parsed["no_speech"],
            "elapsed_secs": round(elapsed, 3),
            "realtime_factor": round(elapsed / parsed["duration_secs"], 3) if parsed["duration_secs"] else None,
            "engine": engine or overrides.get("engine"),
            "model": overrides.get("model"),
            "flags": flags,
            "config_path": config_path,
            "ts": time.time(),
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def transcribe_batch(paths: list[str], config_path: Optional[str] = None,
                     overrides: Optional[dict] = None, engine: Optional[str] = None,
                     recursive: bool = False, continue_on_error: bool = True,
                     progress=None) -> dict:
    files = collect_inputs(paths, recursive)
    if not files:
        raise ValueError("No audio files found in the given inputs.")
    results, errors = [], []
    for i, f in enumerate(files, 1):
        if progress:
            progress(i, len(files), os.path.basename(f))
        try:
            results.append(transcribe_file(f, config_path, overrides, engine))
        except Exception as e:  # noqa: BLE001 — collected and reported per file
            if not continue_on_error:
                raise
            errors.append({"file": f, "error": str(e)})
    return {
        "count": len(files),
        "succeeded": len(results),
        "failed": len(errors),
        "total_audio_secs": round(sum(r["duration_secs"] or 0 for r in results), 3),
        "results": results,
        "errors": errors,
    }


# ── export of transcription results ────────────────────────────────────

EXPORT_FORMATS = ("txt", "md", "json", "csv", "jsonl")


def export_results(results: list[dict], output: str, fmt: Optional[str] = None,
                   overwrite: bool = False) -> dict:
    import csv
    import json

    if not results:
        raise ValueError("No transcription results to export.")
    fmt = (fmt or os.path.splitext(output)[1].lstrip(".") or "txt").lower()
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unknown export format '{fmt}'. Valid: {', '.join(EXPORT_FORMATS)}")
    if os.path.exists(output) and not overwrite:
        raise FileExistsError(f"{output} exists; pass --overwrite")
    os.makedirs(os.path.dirname(os.path.abspath(output)) or ".", exist_ok=True)

    if fmt == "txt":
        body = "\n\n".join(r["text"] for r in results if r.get("text")) + "\n"
        with open(output, "w", encoding="utf-8") as f:
            f.write(body)
    elif fmt == "md":
        parts = ["# Transcriptions", ""]
        for r in results:
            parts += [f"## {os.path.basename(r['file'])}",
                      f"*{r.get('duration_secs')}s audio, {r.get('words')} words*", "",
                      r.get("text") or "_(no speech)_", ""]
        with open(output, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
    elif fmt == "json":
        with open(output, "w", encoding="utf-8") as f:
            json.dump({"count": len(results), "results": results}, f, indent=2)
    elif fmt == "jsonl":
        with open(output, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
    elif fmt == "csv":
        cols = ["file", "duration_secs", "words", "elapsed_secs", "no_speech", "text"]
        with open(output, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in results:
                w.writerow(r)
    return {"output": os.path.abspath(output), "format": fmt, "entries": len(results),
            "file_size": os.path.getsize(output)}
