#!/usr/bin/env python3
"""Update registry-dates.json with meaningful per-CLI update dates."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_AGENT = "CLI-Anything registry date updater"
GITHUB_REPO_RE = re.compile(r"https://github\.com/([^/]+/[^/#?]+?)(?:\.git)?(?:[/?#].*)?$")
GIT_URL_RE = re.compile(r"https://github\.com/[^\s#]+")
SUBDIRECTORY_RE = re.compile(r"#subdirectory=([^\s]+)")


def _fetch_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _fetch_last_modified(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            last_modified = resp.headers.get("Last-Modified")
            if not last_modified:
                return None
            return parsedate_to_datetime(last_modified).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def _git_log_timestamp(target_path: Path, excluded_globs: tuple[str, ...] = ()) -> int | None:
    try:
        relative_target = target_path.relative_to(REPO_ROOT).as_posix()
        cmd = ["git", "log", "-1", "--format=%ct", "--", relative_target]
        cmd.extend(f":(exclude,glob){pattern}" for pattern in excluded_globs)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def get_last_modified(target_path: Path) -> str | None:
    """Get the most recent git commit date for CLI-specific files in a repo path."""
    relative_target = target_path.relative_to(REPO_ROOT).as_posix()
    shared_file_globs = (
        f"{relative_target}/cli_anything/**/utils/repl_skin.py",
        f"{relative_target}/cli_anything/**/skills/SKILL.md",
        f"{relative_target}/cli_anything/**/SKILL.md",
    )

    timestamp = _git_log_timestamp(target_path, excluded_globs=shared_file_globs)
    if timestamp is None:
        timestamp = _git_log_timestamp(target_path)
    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def get_github_repo_date(source_url: str) -> str | None:
    """Get the last push date from a GitHub repo via the API."""
    match = GITHUB_REPO_RE.match(source_url)
    if not match:
        return None
    repo_slug = match.group(1)
    data = _fetch_json(f"https://api.github.com/repos/{repo_slug}")
    if not data:
        return None
    pushed_at = data.get("pushed_at")
    return pushed_at[:10] if pushed_at else None


def _extract_pypi_package(install_cmd: str) -> str | None:
    if not install_cmd:
        return None
    try:
        tokens = shlex.split(install_cmd)
    except ValueError:
        return None

    if not tokens:
        return None

    install_index = None
    if tokens[:3] == ["python3", "-m", "pip"]:
        install_index = 3
    elif tokens[0] in {"pip", "pip3"}:
        install_index = 1

    if install_index is None or install_index >= len(tokens) or tokens[install_index] != "install":
        return None

    for token in tokens[install_index + 1 :]:
        if token.startswith("-"):
            continue
        if "://" in token or token.startswith("git+"):
            return None
        return token
    return None


def get_pypi_date(install_cmd: str) -> str | None:
    """Get the last release date from PyPI for a pip-installable package."""
    package = _extract_pypi_package(install_cmd)
    if not package:
        return None
    data = _fetch_json(f"https://pypi.org/pypi/{package}/json")
    if not data:
        return None
    latest = data.get("info", {}).get("version")
    releases = data.get("releases", {})
    release_files = releases.get(latest or "", [])
    if not release_files:
        return None
    upload_time = release_files[0].get("upload_time") or release_files[0].get("upload_time_iso_8601")
    return upload_time[:10] if upload_time else None


def _extract_npm_package(cli: dict) -> str | None:
    package = cli.get("npm_package")
    if package:
        return package

    install_cmd = cli.get("install_cmd", "")
    match = re.search(r"npm install -g (\S+)", install_cmd)
    return match.group(1) if match else None


def get_npm_date(cli: dict) -> str | None:
    """Get the latest publish date from the npm registry."""
    package = _extract_npm_package(cli)
    if not package:
        return None
    encoded = urllib.parse.quote(package, safe="")
    data = _fetch_json(f"https://registry.npmjs.org/{encoded}")
    if not data:
        return None
    latest = data.get("dist-tags", {}).get("latest")
    published = data.get("time", {}).get(latest or "")
    return published[:10] if published else None


def _extract_install_subdirectory(cli: dict) -> str | None:
    install_cmd = cli.get("install_cmd") or ""
    match = SUBDIRECTORY_RE.search(install_cmd)
    return match.group(1) if match else None


def _extract_skill_subdirectory(cli: dict) -> str | None:
    skill_md = cli.get("skill_md")
    if not skill_md or skill_md.startswith("http"):
        return None
    marker = "/agent-harness/"
    if marker not in skill_md:
        return None
    return skill_md.split(marker, 1)[0] + marker.rstrip("/")


def resolve_harness_path(cli: dict, repo_root: Path) -> Path | None:
    """Resolve the on-disk harness path for an in-repo CLI entry."""
    for relative in (_extract_install_subdirectory(cli), _extract_skill_subdirectory(cli)):
        if relative:
            candidate = repo_root / relative
            if candidate.exists():
                return candidate

    candidate_dirs = []
    for name in (cli.get("name"), cli.get("name", "").replace("-", "_"), cli.get("name", "").replace("_", "-")):
        if name and name not in candidate_dirs:
            candidate_dirs.append(name)

    for directory in candidate_dirs:
        candidate = repo_root / directory / "agent-harness"
        if candidate.exists():
            return candidate
    return None


def extract_external_source_url(cli: dict) -> str | None:
    """Best-effort source URL discovery for third-party CLIs."""
    source_url = cli.get("source_url")
    if source_url:
        return source_url

    install_cmd = cli.get("install_cmd") or ""
    git_match = GIT_URL_RE.search(install_cmd)
    if git_match:
        return git_match.group(0).removesuffix(".git")

    for field in ("homepage", "docs_url"):
        value = cli.get(field)
        if value and "github.com/" in value:
            return value
    return None


def get_external_date(cli: dict) -> str | None:
    """Get a useful update date for external/public CLIs."""
    source_url = extract_external_source_url(cli)
    if source_url:
        date = get_github_repo_date(source_url)
        if date:
            return date

    package_manager = (cli.get("package_manager") or "").lower()
    if package_manager == "npm":
        date = get_npm_date(cli)
        if date:
            return date

    date = get_pypi_date(cli.get("install_cmd", ""))
    if date:
        return date

    for field in ("homepage", "docs_url"):
        url = cli.get(field)
        if url:
            date = _fetch_last_modified(url)
            if date:
                return date
    return None


def get_cli_date(cli: dict, repo_root: Path) -> str | None:
    harness_path = resolve_harness_path(cli, repo_root)
    if harness_path:
        return get_last_modified(harness_path)
    return get_external_date(cli)


def _load_registry(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)["clis"]


def main() -> None:
    dates_path = REPO_ROOT / "docs" / "hub" / "registry-dates.json"
    all_clis = _load_registry(REPO_ROOT / "registry.json") + _load_registry(REPO_ROOT / "public_registry.json")

    dates = {cli["name"]: get_cli_date(cli, REPO_ROOT) for cli in all_clis}

    with dates_path.open("w", encoding="utf-8") as f:
        json.dump(dates, f, indent=2)

    print(f"Updated dates for {len(dates)} CLI entries")


if __name__ == "__main__":
    main()
