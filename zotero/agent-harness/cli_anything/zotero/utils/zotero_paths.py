from __future__ import annotations

import configparser
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Optional


DATA_DIR_PREF = "extensions.zotero.dataDir"
USE_DATA_DIR_PREF = "extensions.zotero.useDataDir"
LOCAL_API_PREF = "extensions.zotero.httpServer.localAPI.enabled"
HTTP_PORT_PREF = "extensions.zotero.httpServer.port"


@dataclass
class ZoteroEnvironment:
    executable: Optional[Path]
    executable_exists: bool
    install_dir: Optional[Path]
    version: str
    profile_root: Path
    profile_dir: Optional[Path]
    data_dir: Path
    data_dir_exists: bool
    sqlite_path: Path
    sqlite_exists: bool
    styles_dir: Path
    styles_exists: bool
    storage_dir: Path
    storage_exists: bool
    translators_dir: Path
    translators_exists: bool
    port: int
    local_api_enabled_configured: bool

    def to_dict(self) -> dict:
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, Path):
                data[key] = str(value)
        return data


def candidate_profile_roots(env: Mapping[str, str] | None = None, home: Path | None = None) -> list[Path]:
    env = env or os.environ
    home = home or Path.home()
    candidates: list[Path] = []

    def add(path: Path | str | None) -> None:
        if not path:
            return
        candidate = Path(path).expanduser()
        if candidate not in candidates:
            candidates.append(candidate)

    appdata = env.get("APPDATA")
    if appdata:
        add(Path(appdata) / "Zotero" / "Zotero")
    add(home / "AppData" / "Roaming" / "Zotero" / "Zotero")
    add(home / "Library" / "Application Support" / "Zotero")
    add(home / ".zotero" / "zotero")
    return candidates


def find_profile_root(explicit_profile_dir: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    env = env or os.environ
    if explicit_profile_dir:
        explicit = Path(explicit_profile_dir).expanduser()
        if explicit.name == "profiles.ini":
            return explicit.parent
        if (explicit / "profiles.ini").exists():
            return explicit
        if (explicit.parent / "profiles.ini").exists():
            return explicit.parent
        return explicit

    env_profile = env.get("ZOTERO_PROFILE_DIR", "").strip()
    if env_profile:
        return find_profile_root(env_profile, env=env)

    for candidate in candidate_profile_roots(env=env):
        if (candidate / "profiles.ini").exists():
            return candidate
    return candidate_profile_roots(env=env)[0]


def read_profiles_ini(profile_root: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    path = profile_root / "profiles.ini"
    if path.exists():
        config.read(path, encoding="utf-8")
    return config


def find_active_profile(profile_root: Path) -> Optional[Path]:
    config = read_profiles_ini(profile_root)
    ordered_sections = [section for section in config.sections() if section.lower().startswith("profile")]
    for section in ordered_sections:
        if config.get(section, "Default", fallback="0").strip() != "1":
            continue
        return _profile_path_from_section(profile_root, config, section)
    for section in ordered_sections:
        candidate = _profile_path_from_section(profile_root, config, section)
        if candidate is not None:
            return candidate
    return None


def _profile_path_from_section(profile_root: Path, config: configparser.ConfigParser, section: str) -> Optional[Path]:
    path_value = config.get(section, "Path", fallback="").strip()
    if not path_value:
        return None
    is_relative = config.get(section, "IsRelative", fallback="1").strip() == "1"
    return (profile_root / path_value).resolve() if is_relative else Path(path_value).expanduser()


def _read_pref_file(path: Path) -> str:
    if not path.exists():
        return ""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def _decode_pref_string(raw: str) -> str:
    return raw.replace("\\\\", "\\").replace('\\"', '"')


def read_pref(profile_dir: Path | None, pref_name: str) -> Optional[str]:
    if profile_dir is None:
        return None
    pattern = re.compile(rf'user_pref\("{re.escape(pref_name)}",\s*(.+?)\);')
    for filename in ("user.js", "prefs.js"):
        text = _read_pref_file(profile_dir / filename)
        for line in text.splitlines():
            match = pattern.search(line)
            if not match:
                continue
            raw = match.group(1).strip()
            if raw in {"true", "false"}:
                return raw
            if raw.startswith('"') and raw.endswith('"'):
                return _decode_pref_string(raw[1:-1])
            return raw
    return None


def find_data_dir(profile_dir: Path | None, explicit_data_dir: str | None = None, env: Mapping[str, str] | None = None) -> Path:
    env = env or os.environ
    if explicit_data_dir:
        return Path(explicit_data_dir).expanduser()

    env_data_dir = env.get("ZOTERO_DATA_DIR", "").strip()
    if env_data_dir:
        return Path(env_data_dir).expanduser()

    if profile_dir is not None:
        use_data_dir = read_pref(profile_dir, USE_DATA_DIR_PREF)
        pref_data_dir = read_pref(profile_dir, DATA_DIR_PREF)
        if use_data_dir == "true" and pref_data_dir:
            candidate = Path(pref_data_dir).expanduser()
            if candidate.exists():
                return candidate

    return Path.home() / "Zotero"


def find_executable(explicit_executable: str | None = None, env: Mapping[str, str] | None = None) -> Optional[Path]:
    env = env or os.environ
    if explicit_executable:
        return Path(explicit_executable).expanduser()

    env_executable = env.get("ZOTERO_EXECUTABLE", "").strip()
    if env_executable:
        return Path(env_executable).expanduser()

    for name in ("zotero", "zotero.exe"):
        path = shutil.which(name)
        if path:
            return Path(path)

    candidates = [
        Path(r"C:\Program Files\Zotero\zotero.exe"),
        Path(r"C:\Program Files (x86)\Zotero\zotero.exe"),
        Path("/Applications/Zotero.app/Contents/MacOS/zotero"),
        Path("/usr/lib/zotero/zotero"),
        Path("/usr/local/bin/zotero"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_install_dir(executable: Optional[Path]) -> Optional[Path]:
    if executable is None:
        return None
    return executable.parent


def get_version(install_dir: Optional[Path]) -> str:
    if install_dir is None:
        return "unknown"
    candidates = [install_dir / "app" / "application.ini", install_dir / "application.ini"]
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = _read_pref_file(candidate)
        match = re.search(r"^Version=(.+)$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return "unknown"


def get_http_port(profile_dir: Path | None, env: Mapping[str, str] | None = None) -> int:
    env = env or os.environ
    env_port = env.get("ZOTERO_HTTP_PORT", "").strip()
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    pref_port = read_pref(profile_dir, HTTP_PORT_PREF)
    if pref_port:
        try:
            return int(pref_port)
        except ValueError:
            pass
    return 23119


def is_local_api_enabled(profile_dir: Path | None) -> bool:
    return read_pref(profile_dir, LOCAL_API_PREF) == "true"


def build_environment(
    explicit_data_dir: str | None = None,
    explicit_profile_dir: str | None = None,
    explicit_executable: str | None = None,
    env: Mapping[str, str] | None = None,
) -> ZoteroEnvironment:
    env = env or os.environ
    profile_root = find_profile_root(explicit_profile_dir=explicit_profile_dir, env=env)
    env_profile_dir = env.get("ZOTERO_PROFILE_DIR", "").strip()
    explicit_or_env_profile = explicit_profile_dir or env_profile_dir or None
    profile_dir = (
        Path(explicit_or_env_profile).expanduser()
        if explicit_or_env_profile and (Path(explicit_or_env_profile) / "prefs.js").exists()
        else find_active_profile(profile_root)
    )
    executable = find_executable(explicit_executable=explicit_executable, env=env)
    install_dir = find_install_dir(executable)
    data_dir = find_data_dir(profile_dir, explicit_data_dir=explicit_data_dir, env=env)
    sqlite_path = data_dir / "zotero.sqlite"
    styles_dir = data_dir / "styles"
    storage_dir = data_dir / "storage"
    translators_dir = data_dir / "translators"
    return ZoteroEnvironment(
        executable=executable,
        executable_exists=bool(executable and executable.exists()),
        install_dir=install_dir,
        version=get_version(install_dir),
        profile_root=profile_root,
        profile_dir=profile_dir,
        data_dir=data_dir,
        data_dir_exists=data_dir.exists(),
        sqlite_path=sqlite_path,
        sqlite_exists=sqlite_path.exists(),
        styles_dir=styles_dir,
        styles_exists=styles_dir.exists(),
        storage_dir=storage_dir,
        storage_exists=storage_dir.exists(),
        translators_dir=translators_dir,
        translators_exists=translators_dir.exists(),
        port=get_http_port(profile_dir, env=env),
        local_api_enabled_configured=is_local_api_enabled(profile_dir),
    )


def ensure_local_api_enabled(profile_dir: Path | None) -> Optional[Path]:
    if profile_dir is None:
        return None
    user_js = profile_dir / "user.js"
    existing = _read_pref_file(user_js)
    line = 'user_pref("extensions.zotero.httpServer.localAPI.enabled", true);'
    if line not in existing:
        content = existing.rstrip()
        if content:
            content += "\n"
        content += line + "\n"
        user_js.write_text(content, encoding="utf-8")
    return user_js
