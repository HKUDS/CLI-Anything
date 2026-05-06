"""Block structure analysis for NSLogger files."""
from __future__ import annotations
from typing import Iterator, List, Dict, Any
from .message import LogMessage, MSG_TYPE_BLOCK_START, MSG_TYPE_BLOCK_END, MSG_TYPE_CLIENT_INFO


def iter_block_tree(messages: Iterator[LogMessage]):
    """Yield (depth, msg) tuples representing the block-indented structure."""
    depth = 0
    for msg in messages:
        if msg.message_type == MSG_TYPE_BLOCK_END:
            depth = max(0, depth - 1)
        yield depth, msg
        if msg.message_type == MSG_TYPE_BLOCK_START:
            depth += 1


def extract_clients(messages: Iterator[LogMessage]) -> List[Dict[str, Any]]:
    """Return a list of dicts for every client_info message in the stream."""
    clients = []
    for msg in messages:
        if msg.message_type == MSG_TYPE_CLIENT_INFO:
            clients.append({
                "sequence": msg.sequence,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "client_name": msg.client_name,
                "client_version": msg.client_version,
                "os_name": msg.os_name,
                "os_version": msg.os_version,
                "machine": msg.machine,
            })
    return clients


def merge_files(paths: List[str]) -> List[LogMessage]:
    """Load multiple rawnsloggerdata files and return messages sorted by timestamp."""
    from ..core.parser import parse_file
    all_msgs: List[LogMessage] = []
    for path in paths:
        all_msgs.extend(parse_file(path))
    all_msgs.sort(key=lambda m: (m.timestamp or __import__("datetime").datetime.min, m.sequence))
    return all_msgs
