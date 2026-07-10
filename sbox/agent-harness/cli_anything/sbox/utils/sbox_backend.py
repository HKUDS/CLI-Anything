"""Backend module for finding and invoking s&box executables."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


# Common s&box installation paths (Windows)
# Non-standard locations should be supplied via the SBOX_PATH env var (see find_sbox_installation below).
SBOX_SEARCH_PATHS: List[str] = [
    r"C:\Program Files (x86)\Steam\steamapps\common\sbox",
    r"C:\Program Files\Steam\steamapps\common\sbox",
    r"D:\SteamLibrary\steamapps\common\sbox",
    r"E:\SteamLibrary\steamapps\common\sbox",
]

# Executable names relative to the s&box installation root
EXECUTABLES: Dict[str, str] = {
    "sbox-dev": "sbox-dev.exe",
    "sbox-server": "sbox-server.exe",
    "sbox-standalone": "sbox-standalone.exe",
    "resourcecompiler": os.path.join( "bin", "win64", "resourcecompiler.exe" ),
}


def find_sbox_installation() -> str:
    """Find the s&box installation directory.

    Checks (in order):
    1. SBOX_PATH environment variable
    2. Common Steam library paths
    3. sbox-dev.exe in PATH

    Returns:
        Absolute path to the s&box installation directory.

    Raises:
        RuntimeError: If no installation is found, with install instructions.
    """
    # 1. Environment variable
    env_path = os.environ.get( "SBOX_PATH" )
    if env_path and os.path.isdir( env_path ):
        dev_exe = os.path.join( env_path, "sbox-dev.exe" )
        if os.path.isfile( dev_exe ):
            return os.path.normpath( env_path )

    # 2. Common search paths
    for candidate in SBOX_SEARCH_PATHS:
        if os.path.isdir( candidate ):
            dev_exe = os.path.join( candidate, "sbox-dev.exe" )
            if os.path.isfile( dev_exe ):
                return os.path.normpath( candidate )

    # 3. sbox-dev.exe on PATH
    found = shutil.which( "sbox-dev" ) or shutil.which( "sbox-dev.exe" )
    if found:
        install_dir = os.path.dirname( os.path.realpath( found ) )
        return os.path.normpath( install_dir )

    raise RuntimeError(
        "Could not find s&box installation. "
        "Please do one of the following:\n"
        "  - Set the SBOX_PATH environment variable to your s&box install directory\n"
        "  - Install s&box via Steam (it will appear in a standard Steam library)\n"
        "  - Add the s&box directory to your system PATH"
    )


def find_executable( name: str ) -> str:
    """Find a specific s&box executable by short name.

    Args:
        name: Executable short name - one of 'sbox-dev', 'sbox-server',
              'sbox-standalone', or 'resourcecompiler'.

    Returns:
        Full absolute path to the executable.

    Raises:
        RuntimeError: If the executable is not found.
    """
    if name not in EXECUTABLES:
        raise RuntimeError(
            f"Unknown executable '{name}'. "
            f"Valid names: {', '.join( sorted( EXECUTABLES.keys() ) )}"
        )

    sbox_dir = find_sbox_installation()
    exe_path = os.path.join( sbox_dir, EXECUTABLES[name] )

    if not os.path.isfile( exe_path ):
        raise RuntimeError(
            f"Executable not found at expected path: {exe_path}\n"
            f"Your s&box installation at {sbox_dir} may be incomplete or corrupted."
        )

    return os.path.normpath( exe_path )


def get_sbox_version() -> Dict[str, Any]:
    """Read s&box version from the .version file in the installation directory.

    Returns:
        Dict with version info. Keys depend on file contents but typically
        include 'version', 'branch', and 'revision'. If the file is plain
        text, returns {"version": <text>}. If JSON, returns parsed dict.
        On any failure, returns {"version": "unknown", "error": <message>}.
    """
    try:
        sbox_dir = find_sbox_installation()
    except RuntimeError as exc:
        return {"version": "unknown", "error": str( exc )}

    version_file = os.path.join( sbox_dir, ".version" )
    if not os.path.isfile( version_file ):
        return {
            "version": "unknown",
            "sbox_path": sbox_dir,
            "error": f".version file not found at {version_file}",
        }

    try:
        with open( version_file, "r", encoding="utf-8" ) as f:
            content = f.read().strip()
    except OSError as exc:
        return {"version": "unknown", "error": str( exc )}

    # Try JSON first
    try:
        data = json.loads( content )
        if isinstance( data, dict ):
            data["sbox_path"] = sbox_dir
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Fall back to plain text
    return {"version": content, "sbox_path": sbox_dir}


def launch_editor( project_path: Optional[str] = None ) -> subprocess.Popen:
    """Launch sbox-dev.exe (the s&box editor), optionally opening a project.

    Args:
        project_path: Path to a .sbproj file or project directory.
                      If None, the editor opens without a project.

    Returns:
        subprocess.Popen object for the launched process.

    Raises:
        RuntimeError: If sbox-dev.exe cannot be found.
        FileNotFoundError: If the given project_path does not exist.
    """
    exe = find_executable( "sbox-dev" )
    cmd: List[str] = [exe]

    if project_path is not None:
        resolved = os.path.abspath( project_path )
        if not os.path.exists( resolved ):
            raise FileNotFoundError(
                f"Project path does not exist: {resolved}"
            )
        cmd.append( resolved )

    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def launch_server(
    game_ident: str,
    map_ident: Optional[str] = None,
) -> subprocess.Popen:
    """Launch sbox-server.exe (dedicated server) with a game.

    Args:
        game_ident: Game identifier string (e.g. 'org.gamename').
        map_ident: Optional map identifier to load.

    Returns:
        subprocess.Popen object for the launched server process.

    Raises:
        RuntimeError: If sbox-server.exe cannot be found.
    """
    exe = find_executable( "sbox-server" )
    cmd: List[str] = [exe, "-game", game_ident]

    if map_ident is not None:
        cmd.extend( ["-map", map_ident] )

    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_resource_compiler(
    asset_path: str,
    sbox_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run resourcecompiler.exe on an asset file.

    Args:
        asset_path: Path to the asset file to compile.
        sbox_path: Optional explicit s&box installation path.
                   If None, auto-detected.

    Returns:
        Dict with keys:
        - 'success': bool
        - 'return_code': int
        - 'stdout': str
        - 'stderr': str
        - 'asset_path': str (absolute path of the input asset)
        - 'compiler_path': str (path of the compiler used)
    """
    if sbox_path is not None:
        compiler = os.path.join(
            sbox_path, EXECUTABLES["resourcecompiler"]
        )
        if not os.path.isfile( compiler ):
            raise RuntimeError(
                f"Resource compiler not found at {compiler}"
            )
    else:
        compiler = find_executable( "resourcecompiler" )

    resolved_asset = os.path.abspath( asset_path )
    if not os.path.isfile( resolved_asset ):
        raise FileNotFoundError(
            f"Asset file does not exist: {resolved_asset}"
        )

    result = subprocess.run(
        [compiler, resolved_asset],
        capture_output=True,
        text=True,
        timeout=120,
    )

    return {
        "success": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "asset_path": resolved_asset,
        "compiler_path": compiler,
    }
