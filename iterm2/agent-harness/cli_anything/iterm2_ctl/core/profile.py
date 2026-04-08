"""Profile operations for iTerm2.

Profiles define terminal appearance, behavior, keyboard mappings, etc.
All functions are async coroutines.
"""
from typing import Any, Dict, List, Optional


async def list_profiles(connection, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all available profiles.

    Args:
        name_filter: Optional substring filter on profile name.

    Returns:
        List of dicts with profile name and GUID.
    """
    import iterm2
    profiles = await iterm2.PartialProfile.async_query(connection)
    result = []
    for p in profiles:
        name = p.name or "(unnamed)"
        if name_filter and name_filter.lower() not in name.lower():
            continue
        result.append({
            "name": name,
            "guid": p.guid,
        })
    return result


async def get_profile_detail(connection, guid: str) -> Dict[str, Any]:
    """Get detailed settings for a profile by GUID.

    Returns a subset of the most useful profile properties.
    """
    import iterm2
    profiles = await iterm2.PartialProfile.async_query(connection)
    for p in profiles:
        if p.guid == guid:
            full = await p.async_get_full_profile()
            return {
                "name": full.name,
                "guid": full.guid,
                "badge_text": full.badge_text,
            }
    raise ValueError(f"Profile with GUID '{guid}' not found.")


async def apply_color_preset(
    connection, session_id: str, preset_name: str
) -> Dict[str, Any]:
    """Apply a named color preset to a session's profile.

    Args:
        session_id: Target session.
        preset_name: Name of the color preset (e.g., 'Solarized Dark').

    Returns:
        Dict confirming the applied preset.
    """
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session
    session = await async_find_session(connection, session_id)

    preset = await iterm2.ColorPreset.async_get(connection, preset_name)
    profile = await session.async_get_profile()
    await profile.async_set_color_preset(preset)
    await session.async_set_profile(profile)
    return {
        "session_id": session_id,
        "preset_applied": preset_name,
    }


async def list_color_presets(connection) -> List[str]:
    """List all available color presets."""
    import iterm2
    presets = await iterm2.ColorPreset.async_get_list(connection)
    return sorted(presets)
