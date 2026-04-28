"""Compute statistics over a sequence of LogMessages."""
from __future__ import annotations
from collections import Counter
from typing import Iterator, Dict, Any
from .message import LogMessage, LEVEL_NAMES


def compute_stats(messages: Iterator[LogMessage]) -> Dict[str, Any]:
    msgs = list(messages)
    if not msgs:
        return {"total": 0}

    level_counts: Counter = Counter()
    tag_counts: Counter = Counter()
    thread_counts: Counter = Counter()
    type_counts: Counter = Counter()
    client_names: set = set()

    first_ts = None
    last_ts = None

    for m in msgs:
        level_counts[m.level] += 1
        if m.tag:
            tag_counts[m.tag] += 1
        if m.thread_id:
            thread_counts[m.thread_id] += 1
        type_counts[m.type_name] += 1
        if m.client_name:
            client_names.add(m.client_name)
        if m.timestamp:
            if first_ts is None or m.timestamp < first_ts:
                first_ts = m.timestamp
            if last_ts is None or m.timestamp > last_ts:
                last_ts = m.timestamp

    duration_s = None
    if first_ts and last_ts:
        duration_s = (last_ts - first_ts).total_seconds()

    return {
        "total": len(msgs),
        "by_level": {
            LEVEL_NAMES.get(k, f"level_{k}"): v
            for k, v in sorted(level_counts.items())
        },
        "by_tag": dict(tag_counts.most_common(20)),
        "by_thread": dict(thread_counts.most_common(10)),
        "by_type": dict(type_counts),
        "clients": sorted(client_names),
        "first_timestamp": first_ts.isoformat() if first_ts else None,
        "last_timestamp": last_ts.isoformat() if last_ts else None,
        "duration_seconds": duration_s,
    }
