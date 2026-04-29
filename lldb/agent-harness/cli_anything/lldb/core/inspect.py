"""
Inspection helpers for variables, expressions, and memory.
"""

from __future__ import annotations

from typing import Any, Dict


def list_locals(session) -> Dict[str, Any]:
    return session.locals()


def evaluate_expression(session, expression: str) -> Dict[str, Any]:
    return session.evaluate(expression)


def read_memory(session, address: int, size: int) -> Dict[str, Any]:
    return session.read_memory(address, size)
