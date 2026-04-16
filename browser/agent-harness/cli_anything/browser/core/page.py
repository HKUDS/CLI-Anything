"""Page-level commands for browser automation.

Handles navigation and page operations:
- open: Navigate to a URL
- reload: Reload the current page
- back: Navigate back in history
- forward: Navigate forward in history
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cli_anything.browser.core.session import Session

from cli_anything.browser.utils import domshell_backend as backend


def open_page(session: "Session", url: str) -> dict:
    """Open a URL in Chrome.

    Args:
        session: Current browser session
        url: URL to navigate to

    Returns:
        Result dict with URL and status

    Example:
        >>> open_page(session, "https://example.com")
        {"url": "https://example.com", "status": "loaded"}
    """
    use_daemon = session.daemon_mode
    result = backend.open_url(url, use_daemon=use_daemon)
    session.set_url(url)
    session.set_working_dir("/")  # Reset to root on new page
    return result


def reload_page(session: "Session") -> dict:
    """Reload the current page.

    Args:
        session: Current browser session

    Returns:
        Result dict with reload status

    Example:
        >>> reload_page(session)
        {"status": "reloaded", "url": "https://example.com"}
    """
    use_daemon = session.daemon_mode
    result = backend.reload(use_daemon=use_daemon)
    return result


def go_back(session: "Session") -> dict:
    """Navigate back in history.

    Args:
        session: Current browser session

    Returns:
        Result dict with previous URL, or error if no history

    Example:
        >>> go_back(session)
        {"url": "https://previous.com", "status": "navigated"}
    """
    use_daemon = session.daemon_mode
    result = backend.back(use_daemon=use_daemon)

    # Update session state if backend returned a URL
    if isinstance(result, dict) and "url" in result:
        session.set_url(result["url"], record_history=False)

    return result


def go_forward(session: "Session") -> dict:
    """Navigate forward in history.

    Args:
        session: Current browser session

    Returns:
        Result dict with next URL, or error if no forward history

    Example:
        >>> go_forward(session)
        {"url": "https://next.com", "status": "navigated"}
    """
    use_daemon = session.daemon_mode
    result = backend.forward(use_daemon=use_daemon)

    # Update session state if backend returned a URL
    if isinstance(result, dict) and "url" in result:
        session.set_url(result["url"], record_history=False)

    return result


def get_page_info(session: "Session") -> dict:
    """Get information about the current page.

    Args:
        session: Current browser session

    Returns:
        Dict with page information
    """
    return {
        "url": session.current_url or "(no page loaded)",
        "working_dir": session.working_dir,
    }
