"""
Thread helpers for listing, selecting, and backtrace operations.
"""

from __future__ import annotations

from typing import Any, Dict


def list_threads(session) -> Dict[str, Any]:
    return session.threads()


def select_thread(session, thread_id: int) -> Dict[str, Any]:
    return session.thread_select(thread_id)


def backtrace(session, limit: int = 50) -> Dict[str, Any]:
    return session.backtrace(limit=limit)
