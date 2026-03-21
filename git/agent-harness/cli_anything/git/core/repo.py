import subprocess
from typing import Optional, List


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def status() -> dict:
    result = run(["git", "status", "--short"])
    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    return {"success": result.returncode == 0, "files": files, "count": len(files)}


def log(limit: int = 10) -> list[dict]:
    result = run(["git", "log", f"--max-count={limit}", "--format=%H|%an|%s|%ci"])
    if result.returncode != 0:
        return [{"error": result.stderr}]
    entries = []
    for line in result.stdout.strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 3)
            entries.append(
                {
                    "hash": parts[0][:8],
                    "author": parts[1],
                    "message": parts[2],
                    "date": parts[3],
                }
            )
    return entries


def diff() -> dict:
    result = run(["git", "diff"])
    return {
        "success": result.returncode == 0,
        "diff": result.stdout[:5000],
        "has_changes": bool(result.stdout.strip()),
    }


def branches() -> list[str]:
    result = run(["git", "branch", "--format=%(refname:short)"])
    return [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]


def checkout(branch: str) -> dict:
    result = run(["git", "checkout", branch])
    return {
        "success": result.returncode == 0,
        "branch": branch,
        "output": result.stdout.strip(),
    }


def add(files: list[str]) -> dict:
    result = run(["git", "add"] + files)
    return {
        "success": result.returncode == 0,
        "files": files,
        "output": result.stdout.strip(),
    }


def commit(message: str) -> dict:
    result = run(["git", "commit", "-m", message])
    return {
        "success": result.returncode == 0,
        "message": message,
        "output": result.stdout.strip(),
    }


def push() -> dict:
    result = run(["git", "push"])
    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip(),
        "stderr": result.stderr,
    }


def pull() -> dict:
    result = run(["git", "pull"])
    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip(),
        "stderr": result.stderr,
    }


def stash_save() -> dict:
    result = run(["git", "stash"])
    return {"success": result.returncode == 0, "output": result.stdout.strip()}


def stash_list() -> list[str]:
    result = run(["git", "stash", "list"])
    return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]


def stash_pop() -> dict:
    result = run(["git", "stash", "pop"])
    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip(),
        "stderr": result.stderr,
    }


def remotes() -> list[str]:
    result = run(["git", "remote", "-v"])
    return [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]


def tags() -> list[str]:
    result = run(["git", "tag", "--list"])
    return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
