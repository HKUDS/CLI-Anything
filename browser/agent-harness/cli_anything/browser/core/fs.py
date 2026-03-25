"""Filesystem commands for browser automation.

DOMShell exposes the Accessibility Tree as a virtual filesystem.
These commands provide filesystem-like navigation:
- ls: List elements at a path
- cd: Change working directory
- cat: Read element content
- grep: Search for text pattern
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cli_anything.browser.core.session import Session

from cli_anything.browser.utils import domshell_backend as backend


def list_elements(session: "Session", path: str = "") -> dict:
    """List elements at a path in the accessibility tree.

    Args:
        session: Current browser session
        path: Path to list (empty string uses current working_dir)

    Returns:
        Dict with list of accessible elements

    Example:
        >>> list_elements(session, "/main")
        {"path": "/main", "entries": [{"name": "button", "role": "button", ...}]}
    """
    target_path = path if path else session.working_dir
    use_daemon = session.daemon_mode
    return backend.ls(target_path, use_daemon=use_daemon)


def change_directory(session: "Session", path: str) -> dict:
    """Change working directory in the accessibility tree.

    Args:
        session: Current browser session
        path: New path (can be relative or absolute)

    Returns:
        Dict with new path confirmation

    Example:
        >>> change_directory(session, "/main/div[0]")
        {"path": "/main/div[0]", "working_dir": "/main/div[0]"}
    """
    # Resolve relative paths
    if path == "..":
        # Go up one level
        current = session.working_dir
        if current == "/":
            return {"error": "Already at root"}
        parts = current.rstrip("/").split("/")
        new_path = "/".join(parts[:-1]) or "/"
        path = new_path
    elif path == ".":
        # Stay in current directory
        path = session.working_dir
    elif not path.startswith("/"):
        # Relative path: append to current working_dir
        if session.working_dir == "/":
            path = "/" + path
        else:
            path = session.working_dir.rstrip("/") + "/" + path

    use_daemon = session.daemon_mode
    result = backend.cd(path, use_daemon=use_daemon)
    # Only update working_dir if backend succeeded
    if isinstance(result, dict) and "error" not in result:
        new_working_dir = result.get("path", path)
        session.set_working_dir(new_working_dir)
    return result


def read_element(session: "Session", path: str = "") -> dict:
    """Read element content from the accessibility tree.

    Args:
        session: Current browser session
        path: Path to element (empty string uses current working_dir)

    Returns:
        Dict with element details

    Example:
        >>> read_element(session, "/main/button[0]")
        {"name": "Submit", "role": "button", "text": "Submit", ...}
    """
    target_path = path if path else session.working_dir
    use_daemon = session.daemon_mode
    return backend.cat(target_path, use_daemon=use_daemon)


def grep_elements(session: "Session", pattern: str, path: str = "") -> dict:
    """Search for pattern in accessibility tree.

    Args:
        session: Current browser session
        pattern: Text pattern to search for
        path: Root path for search (empty string uses current working_dir)

    Returns:
        Dict with matching elements

    Example:
        >>> grep_elements(session, "Login")
        {"matches": ["/main/button[0]", "/main/link[1]"]}
    """
    target_path = path if path else session.working_dir
    use_daemon = session.daemon_mode

    # DOMShell's grep searches from the server-side CWD. To root the search
    # at the requested path, cd there first, grep, then restore.
    if target_path and target_path != "/":
        cd_result = backend.cd(target_path, use_daemon=use_daemon)
        if hasattr(cd_result, 'isError') and cd_result.isError:
            return cd_result

    try:
        return backend.grep(pattern, use_daemon=use_daemon)
    finally:
        if target_path and target_path != "/":
            backend.cd(session.working_dir or "/", use_daemon=use_daemon)
