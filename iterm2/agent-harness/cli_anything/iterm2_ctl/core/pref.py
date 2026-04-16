"""Global preferences management for iTerm2.

Read and write any of iTerm2's global preferences via the Python API.
Includes curated tmux-specific preference helpers.

All functions are async coroutines intended to be called via
cli_anything.iterm2_ctl.utils.iterm2_backend.run_iterm2().
"""
from typing import Any, Dict


def _parse_value(value: str) -> Any:
    """Parse a string value into an appropriate Python type.

    Converts "true"/"false" (case-insensitive) to bool, numeric strings to
    int or float, and leaves everything else as a string.
    """
    if isinstance(value, str):
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        try:
            as_int = int(value)
            return as_int
        except ValueError:
            pass
        try:
            as_float = float(value)
            return as_float
        except ValueError:
            pass
    return value


async def get_preference(connection, key: str) -> Dict:
    """Get a global iTerm2 preference by key.

    Args:
        key: Either a PreferenceKey enum member name (e.g. "OPEN_TMUX_WINDOWS_IN")
            or a raw preference key string (e.g. "OpenTmuxWindowsIn").

    Returns:
        Dict with 'key' and 'value'.
    """
    import iterm2

    # Try to resolve as a PreferenceKey enum name first
    pref_key = key
    try:
        pref_key = iterm2.PreferenceKey[key]
    except (KeyError, AttributeError):
        pass  # Fall through and use the raw string

    value = await iterm2.async_get_preference(connection, pref_key)
    return {
        "key": key,
        "value": value,
    }


async def set_preference(connection, key: str, value: Any) -> Dict:
    """Set a global iTerm2 preference.

    Args:
        key: Either a PreferenceKey enum member name or a raw preference key string.
        value: The value to set. Strings are parsed: "true"/"false" -> bool,
            numeric strings -> int/float, all others remain strings.

    Returns:
        Dict with 'key', 'value', and 'set': True.
    """
    import iterm2

    parsed = _parse_value(value) if isinstance(value, str) else value

    pref_key = key
    try:
        pref_key = iterm2.PreferenceKey[key]
    except (KeyError, AttributeError):
        pass

    await iterm2.async_set_preference(connection, pref_key, parsed)
    return {
        "key": key,
        "value": parsed,
        "set": True,
    }


async def get_tmux_preferences(connection) -> Dict:
    """Get all tmux-related preferences in one call.

    Returns:
        Dict with human-readable keys:
          - open_tmux_windows_in: int (0=native_windows, 1=new_window, 2=tabs_in_existing)
          - tmux_dashboard_limit: int
          - auto_hide_tmux_client_session: bool
          - use_tmux_profile: bool
    """
    import iterm2

    open_in = await iterm2.async_get_preference(
        connection, iterm2.PreferenceKey.OPEN_TMUX_WINDOWS_IN
    )
    dashboard_limit = await iterm2.async_get_preference(
        connection, iterm2.PreferenceKey.TMUX_DASHBOARD_LIMIT
    )
    auto_hide = await iterm2.async_get_preference(
        connection, iterm2.PreferenceKey.AUTO_HIDE_TMUX_CLIENT_SESSION
    )
    use_profile = await iterm2.async_get_preference(
        connection, iterm2.PreferenceKey.USE_TMUX_PROFILE
    )

    return {
        "open_tmux_windows_in": open_in,
        "open_tmux_windows_in_label": {0: "native_windows", 1: "new_window", 2: "tabs_in_existing"}.get(open_in, "unknown"),
        "tmux_dashboard_limit": dashboard_limit,
        "auto_hide_tmux_client_session": auto_hide,
        "use_tmux_profile": use_profile,
    }


async def set_tmux_preference(connection, setting: str, value: Any) -> Dict:
    """Set a tmux-specific preference by human-readable name.

    Args:
        setting: One of:
            - 'open_in': int 0=native_windows, 1=new_window, 2=tabs_in_existing
            - 'dashboard_limit': int max entries shown in the tmux dashboard
            - 'auto_hide_client': bool hide tmux client session automatically
            - 'use_profile': bool use tmux profile for new windows
        value: The value to set (parsed from string if needed).

    Returns:
        Dict with 'setting', 'key', 'value', and 'set': True.
    """
    import iterm2

    setting_map = {
        "open_in": iterm2.PreferenceKey.OPEN_TMUX_WINDOWS_IN,
        "dashboard_limit": iterm2.PreferenceKey.TMUX_DASHBOARD_LIMIT,
        "auto_hide_client": iterm2.PreferenceKey.AUTO_HIDE_TMUX_CLIENT_SESSION,
        "use_profile": iterm2.PreferenceKey.USE_TMUX_PROFILE,
    }

    if setting not in setting_map:
        available = list(setting_map.keys())
        raise ValueError(
            f"Unknown tmux setting '{setting}'. Available: {available}"
        )

    pref_key = setting_map[setting]
    parsed = _parse_value(value) if isinstance(value, str) else value

    await iterm2.async_set_preference(connection, pref_key, parsed)
    return {
        "setting": setting,
        "key": pref_key.name,
        "value": parsed,
        "set": True,
    }


async def get_theme(connection) -> Dict:
    """Get current iTerm2 theme information.

    Uses app.async_get_theme() which returns a list of theme tag strings
    such as ["dark"], ["light"], ["dark", "highContrast"], etc.

    Returns:
        Dict with 'tags' (list of strings) and 'is_dark' (bool).
    """
    import iterm2
    app = await iterm2.async_get_app(connection)
    tags = await app.async_get_theme()
    return {
        "tags": list(tags),
        "is_dark": "dark" in tags,
    }
