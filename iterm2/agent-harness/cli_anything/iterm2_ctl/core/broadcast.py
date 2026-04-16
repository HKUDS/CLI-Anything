"""Broadcast domain management for iTerm2.

Broadcast domains control which sessions receive keyboard input simultaneously.
All sessions in the same domain receive every keystroke typed in any of them.

All functions are async coroutines intended to be called via
cli_anything.iterm2_ctl.utils.iterm2_backend.run_iterm2().
"""
from typing import Dict, List, Optional


async def get_broadcast_domains(connection) -> List[Dict]:
    """Return current broadcast domains.

    Refreshes the domain list from iTerm2 before returning.

    Returns:
        List of dicts, each with a 'sessions' key containing a list of
        session_id strings belonging to that domain.
    """
    import iterm2
    app = await iterm2.async_get_app(connection)
    await app.async_refresh_broadcast_domains()
    result = []
    for domain in app.broadcast_domains:
        result.append({
            "sessions": [s.session_id for s in domain.sessions],
        })
    return result


async def set_broadcast_domains(connection, domain_groups: List[List[str]]) -> Dict:
    """Set broadcast domains from a list of session ID groups.

    Replaces all existing broadcast domains with the ones specified.

    Args:
        domain_groups: e.g. [["sess1", "sess2"], ["sess3", "sess4"]].
            Each inner list becomes one BroadcastDomain.
            Pass an empty list to clear all broadcasting.

    Returns:
        Dict with 'domains' — the resulting list of session ID groups.
    """
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session

    domains = []
    for group in domain_groups:
        domain = iterm2.BroadcastDomain()
        for session_id in group:
            session = await async_find_session(connection, session_id)
            domain.add_session(session)
        domains.append(domain)

    await iterm2.async_set_broadcast_domains(connection, domains)
    return {
        "domains": domain_groups,
        "domain_count": len(domains),
    }


async def add_to_broadcast(connection, session_ids: List[str]) -> Dict:
    """Add sessions to a single new broadcast domain.

    Creates a new broadcast domain containing exactly the given sessions.
    Any existing domains are preserved alongside the new one.

    Args:
        session_ids: List of session IDs to group into one broadcast domain.

    Returns:
        Dict with the updated full domain list.
    """
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session

    app = await iterm2.async_get_app(connection)
    await app.async_refresh_broadcast_domains()

    # Collect existing domains as lists of IDs
    existing_groups = [
        [s.session_id for s in domain.sessions]
        for domain in app.broadcast_domains
    ]

    # Append new group
    existing_groups.append(session_ids)

    # Rebuild and apply all domains
    domains = []
    for group in existing_groups:
        domain = iterm2.BroadcastDomain()
        for sid in group:
            session = await async_find_session(connection, sid)
            domain.add_session(session)
        domains.append(domain)

    await iterm2.async_set_broadcast_domains(connection, domains)
    return {
        "domains": existing_groups,
        "domain_count": len(domains),
        "added_sessions": session_ids,
    }


async def clear_broadcast(connection) -> Dict:
    """Clear all broadcast domains, stopping all input broadcasting.

    Returns:
        Dict confirming the clear with 'domains' set to an empty list.
    """
    import iterm2
    await iterm2.async_set_broadcast_domains(connection, [])
    return {
        "domains": [],
        "domain_count": 0,
        "cleared": True,
    }


async def broadcast_all_panes(
    connection,
    window_id: Optional[str] = None,
) -> Dict:
    """Add all sessions in a window (or all windows) to a single broadcast domain.

    Args:
        window_id: If given, only collect sessions from that window.
            If None, collect sessions from every window.

    Returns:
        Dict with the session IDs added to the domain.
    """
    import iterm2
    from cli_anything.iterm2_ctl.utils.iterm2_backend import async_find_session

    app = await iterm2.async_get_app(connection)
    session_ids = []

    for window in app.windows:
        if window_id is not None and window.window_id != window_id:
            continue
        for tab in window.tabs:
            for session in tab.sessions:
                session_ids.append(session.session_id)

    if not session_ids:
        raise ValueError(
            f"No sessions found"
            + (f" in window '{window_id}'" if window_id else "")
        )

    domain = iterm2.BroadcastDomain()
    for sid in session_ids:
        session = await async_find_session(connection, sid)
        domain.add_session(session)

    await iterm2.async_set_broadcast_domains(connection, [domain])
    return {
        "domains": [session_ids],
        "domain_count": 1,
        "session_count": len(session_ids),
        "window_id": window_id,
    }
