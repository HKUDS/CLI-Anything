"""
Higher-level breakpoint helpers built on LLDBSession.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def set_breakpoint(
    session,
    file: Optional[str] = None,
    line: Optional[int] = None,
    function: Optional[str] = None,
    condition: Optional[str] = None,
    allow_pending: bool = False,
) -> Dict[str, Any]:
    return session.breakpoint_set(
        file=file,
        line=line,
        function=function,
        condition=condition,
        allow_pending=allow_pending,
    )


def list_breakpoints(session) -> Dict[str, Any]:
    return session.breakpoint_list()


def delete_breakpoint(session, bp_id: int) -> Dict[str, Any]:
    return session.breakpoint_delete(bp_id)


def set_enabled(session, bp_id: int, enabled: bool) -> Dict[str, Any]:
    return session.breakpoint_enable(bp_id, enabled=enabled)
