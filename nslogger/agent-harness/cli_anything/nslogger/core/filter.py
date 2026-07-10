"""Message filtering logic for NSLogger CLI."""
from __future__ import annotations
import re
from datetime import datetime
from typing import Iterator, Optional, List
from .message import LogMessage


def filter_messages(
    messages: Iterator[LogMessage],
    max_level: Optional[int] = None,
    min_level: Optional[int] = None,
    tags: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    text_search: Optional[str] = None,
    text_regex: Optional[str] = None,
    msg_types: Optional[List[str]] = None,
    limit: Optional[int] = None,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    from_seq: Optional[int] = None,
    to_seq: Optional[int] = None,
) -> Iterator[LogMessage]:
    """Yield messages matching all specified criteria."""
    pattern = re.compile(text_regex, re.IGNORECASE) if text_regex else None
    tag_set = {t.lower() for t in tags} if tags else None
    type_set = set(msg_types) if msg_types else None
    count = 0

    for msg in messages:
        if max_level is not None and msg.level > max_level:
            continue
        if min_level is not None and msg.level < min_level:
            continue
        if tag_set and msg.tag.lower() not in tag_set:
            continue
        if thread_id and msg.thread_id != thread_id:
            continue
        if text_search and text_search.lower() not in msg.text.lower():
            continue
        if pattern and not pattern.search(msg.text):
            continue
        if type_set and msg.type_name not in type_set:
            continue
        if after is not None and (msg.timestamp is None or msg.timestamp < after):
            continue
        if before is not None and (msg.timestamp is None or msg.timestamp > before):
            continue
        if from_seq is not None and msg.sequence < from_seq:
            continue
        if to_seq is not None and msg.sequence > to_seq:
            continue
        yield msg
        count += 1
        if limit is not None and count >= limit:
            break
