import subprocess, json, os
from typing import Optional, List


def run(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True)


def download(
    url: str, output: Optional[str] = None, format: Optional[str] = None
) -> dict:
    cmd = ["yt-dlp", url]
    if output:
        cmd += ["-o", output]
    if format:
        cmd += ["-f", format]
    result = run(cmd)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def info(url: str) -> dict:
    result = run(["yt-dlp", "--dump-json", "--no-download", url])
    if result.returncode != 0:
        return {"error": result.stderr}
    data = json.loads(result.stdout)
    return {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "uploader": data.get("uploader"),
        "view_count": data.get("view_count"),
        "url": url,
    }


def formats(url: str) -> list[dict]:
    result = run(["yt-dlp", "--list-formats", url])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    lines = result.stdout.strip().split("\n")
    fmts = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 3:
            fmts.append(
                {
                    "format_id": parts[0],
                    "ext": parts[1],
                    "resolution": " ".join(parts[2:]),
                }
            )
    return fmts


def search(query: str) -> list[dict]:
    result = run(["yt-dlp", "ytsearch5:" + query, "--flat-playlist", "--dump-json"])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    items = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                d = json.loads(line)
                items.append(
                    {
                        "title": d.get("title"),
                        "id": d.get("id"),
                        "duration": d.get("duration"),
                    }
                )
            except json.JSONDecodeError:
                pass
    return items


def playlist(url: str) -> list[dict]:
    result = run(["yt-dlp", "--flat-playlist", "--dump-json", url])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    items = []
    for line in result.stdout.strip().split("\n"):
        if line:
            try:
                d = json.loads(line)
                items.append({"title": d.get("title"), "id": d.get("id")})
            except json.JSONDecodeError:
                pass
    return items


def subtitles(url: str) -> list[dict]:
    result = run(["yt-dlp", "--list-subs", url])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    return [{"raw": result.stdout}]
