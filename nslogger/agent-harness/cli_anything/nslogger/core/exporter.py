"""Export LogMessages to various formats."""
from __future__ import annotations
import csv
import io
import json
from typing import Iterator, List
from .message import LogMessage


def export_text(messages: List[LogMessage]) -> str:
    lines = [m.to_text_line() for m in messages]
    return "\n".join(lines)


def export_json(messages: List[LogMessage]) -> str:
    return json.dumps([m.to_dict() for m in messages], indent=2, default=str)


def export_csv(messages: List[LogMessage]) -> str:
    buf = io.StringIO()
    fields = ["sequence", "timestamp", "level", "level_name", "tag", "thread_id", "type", "text"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for m in messages:
        d = m.to_dict()
        writer.writerow({f: d.get(f, "") for f in fields})
    return buf.getvalue()


def export_messages(messages: Iterator[LogMessage], fmt: str = "text") -> str:
    msgs = list(messages)
    if fmt == "json":
        return export_json(msgs)
    if fmt == "csv":
        return export_csv(msgs)
    return export_text(msgs)
