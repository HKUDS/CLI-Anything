import subprocess, os
from typing import Optional


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def info(file: str) -> dict:
    result = run(["exiftool", "-j", file])
    if result.returncode != 0:
        return {"error": result.stderr}
    import json

    try:
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except:
        return {"raw": result.stdout[:2000]}


def set_tag(file: str, tag: str, value: str) -> dict:
    result = run(["exiftool", f"-{tag}={value}", file])
    return {
        "success": result.returncode == 0,
        "file": file,
        "tag": tag,
        "value": value,
        "output": result.stdout.strip(),
    }


def remove(file: str) -> dict:
    result = run(["exiftool", "-all=", file])
    return {
        "success": result.returncode == 0,
        "file": file,
        "output": result.stdout.strip(),
    }


def gps(file: str) -> dict:
    result = run(
        ["exiftool", "-gpslatitude", "-gpslongitude", "-gpsaltitude", "-j", file]
    )
    if result.returncode != 0:
        return {"error": result.stderr}
    import json

    try:
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except:
        return {"raw": result.stdout}


def dates(file: str) -> dict:
    result = run(
        ["exiftool", "-createdate", "-modifydate", "-filemodifydate", "-j", file]
    )
    if result.returncode != 0:
        return {"error": result.stderr}
    import json

    try:
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except:
        return {"raw": result.stdout}


def copy(src: str, dst: str) -> dict:
    result = run(["exiftool", "-TagsFromFile", src, dst])
    return {
        "success": result.returncode == 0,
        "src": src,
        "dst": dst,
        "output": result.stdout.strip(),
    }
