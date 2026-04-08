"""Main menu invocation for iTerm2.

Allows invoking any iTerm2 menu item by its identifier string.

All functions are async coroutines intended to be called via
cli_anything.iterm2_ctl.utils.iterm2_backend.run_iterm2().
"""
from typing import Dict, List


async def select_menu_item(connection, identifier: str) -> Dict:
    """Invoke a menu item by its identifier string.

    Args:
        identifier: The menu item identifier, e.g.
            "New Window", "Shell/Split Vertically with Current Profile",
            "View/Show Tabs in Fullscreen". Use list_common_menu_items()
            for a reference list of available identifiers.

    Returns:
        Dict with 'identifier' and 'invoked': True.
    """
    import iterm2
    await iterm2.MainMenu.async_select_menu_item(connection, identifier)
    return {
        "identifier": identifier,
        "invoked": True,
    }


async def get_menu_item_state(connection, identifier: str) -> Dict:
    """Get the state (checked, enabled) of a menu item.

    Args:
        identifier: The menu item identifier string.

    Returns:
        Dict with 'identifier', 'checked' (bool), and 'enabled' (bool).
    """
    import iterm2
    state = await iterm2.MainMenu.async_get_menu_item_state(connection, identifier)
    return {
        "identifier": identifier,
        "checked": state.checked,
        "enabled": state.enabled,
    }


async def list_common_menu_items(connection) -> List[Dict]:
    """Return a curated reference list of useful menu item identifiers.

    Does not query iTerm2 — returns a hardcoded list of the most commonly
    useful identifiers drawn from the MainMenu enum.

    Returns:
        List of dicts, each with 'identifier' and 'description' keys.
    """
    return [
        # iTerm2 application menu
        {
            "identifier": "iTerm2/Preferences...",
            "description": "Open iTerm2 Preferences window",
        },
        {
            "identifier": "iTerm2/Toggle Debug Logging",
            "description": "Toggle debug logging on/off",
        },
        # Shell menu — window / session creation
        {
            "identifier": "Shell/New Window",
            "description": "Open a new iTerm2 window",
        },
        {
            "identifier": "Shell/New Window with Current Profile",
            "description": "Open a new window using the current profile",
        },
        {
            "identifier": "Shell/New Tab",
            "description": "Open a new tab in the current window",
        },
        {
            "identifier": "Shell/New Tab with Current Profile",
            "description": "Open a new tab using the current profile",
        },
        {
            "identifier": "Shell/Split Vertically with Current Profile",
            "description": "Split the current pane vertically (side by side)",
        },
        {
            "identifier": "Shell/Split Horizontally with Current Profile",
            "description": "Split the current pane horizontally (top/bottom)",
        },
        {
            "identifier": "Shell/Close",
            "description": "Close the current session/pane",
        },
        {
            "identifier": "Shell/Close Window",
            "description": "Close the current window",
        },
        # View menu
        {
            "identifier": "View/Show Tabs in Fullscreen",
            "description": "Show the tab bar when in fullscreen mode",
        },
        {
            "identifier": "View/Hide Tab Bar",
            "description": "Toggle the tab bar visibility",
        },
        {
            "identifier": "View/Enter Full Screen",
            "description": "Enter fullscreen mode",
        },
        {
            "identifier": "View/Exit Full Screen",
            "description": "Exit fullscreen mode",
        },
        {
            "identifier": "View/Show/Hide Command History",
            "description": "Toggle the command history tool",
        },
        {
            "identifier": "View/Show/Hide Recent Directories",
            "description": "Toggle the recent directories tool",
        },
        # Edit / Find
        {
            "identifier": "Find/Find...",
            "description": "Open the find bar in the current session",
        },
        {
            "identifier": "Find/Find Next",
            "description": "Find next match",
        },
        {
            "identifier": "Find/Find Previous",
            "description": "Find previous match",
        },
        # Window menu
        {
            "identifier": "Window/Minimize",
            "description": "Minimize the current window",
        },
        {
            "identifier": "Window/Zoom",
            "description": "Zoom the current window",
        },
        {
            "identifier": "Window/Arrange Windows Horizontally",
            "description": "Tile all iTerm2 windows horizontally",
        },
        {
            "identifier": "Window/Bring All to Front",
            "description": "Bring all iTerm2 windows to the front",
        },
    ]
