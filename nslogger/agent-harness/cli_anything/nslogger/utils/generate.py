"""Generate sample .rawnsloggerdata files for testing."""
from __future__ import annotations
import struct
import time
from typing import List, Optional

from ..core.message import (
    PART_KEY_MESSAGE_TYPE, PART_KEY_TIMESTAMP_S, PART_KEY_TIMESTAMP_MS,
    PART_KEY_THREAD_ID, PART_KEY_TAG, PART_KEY_LEVEL, PART_KEY_MESSAGE,
    PART_KEY_IMAGE_WIDTH, PART_KEY_IMAGE_HEIGHT, PART_KEY_MESSAGE_SEQ,
    PART_KEY_CLIENT_NAME, PART_KEY_CLIENT_VERSION,
    PART_KEY_OS_NAME, PART_KEY_OS_VERSION, PART_KEY_CLIENT_MODEL,
    PART_TYPE_STRING, PART_TYPE_INT16, PART_TYPE_INT32,
)


def _encode_string_part(key: int, value: str) -> bytes:
    encoded = value.encode("utf-8")
    return bytes([key, PART_TYPE_STRING]) + struct.pack(">I", len(encoded)) + encoded


def _encode_int32_part(key: int, value: int) -> bytes:
    return bytes([key, PART_TYPE_INT32]) + struct.pack(">I", value & 0xFFFFFFFF)


def _encode_int16_part(key: int, value: int) -> bytes:
    return bytes([key, PART_TYPE_INT16]) + struct.pack(">H", value & 0xFFFF)


def encode_message(
    sequence: int,
    msg_type: int = 0,
    timestamp: Optional[float] = None,
    thread_id: str = "main",
    tag: str = "",
    level: int = 2,
    text: str = "",
    client_name: str = "",
    client_version: str = "",
    os_name: str = "",
    os_version: str = "",
    machine: str = "",
) -> bytes:
    if timestamp is None:
        timestamp = time.time()

    parts = b""
    parts += _encode_int32_part(PART_KEY_MESSAGE_TYPE, msg_type)           # message type
    parts += _encode_int32_part(PART_KEY_TIMESTAMP_S, int(timestamp))     # timestamp seconds
    ms = int((timestamp - int(timestamp)) * 1000)
    parts += _encode_int16_part(PART_KEY_TIMESTAMP_MS, ms)                 # timestamp ms
    if thread_id:
        parts += _encode_string_part(PART_KEY_THREAD_ID, thread_id)
    if tag:
        parts += _encode_string_part(PART_KEY_TAG, tag)
    parts += _encode_int16_part(PART_KEY_LEVEL, level)              # level
    parts += _encode_int32_part(PART_KEY_MESSAGE_SEQ, sequence)
    if text:
        parts += _encode_string_part(PART_KEY_MESSAGE, text)
    if client_name:
        parts += _encode_string_part(PART_KEY_CLIENT_NAME, client_name)
    if client_version:
        parts += _encode_string_part(PART_KEY_CLIENT_VERSION, client_version)
    if os_name:
        parts += _encode_string_part(PART_KEY_OS_NAME, os_name)
    if os_version:
        parts += _encode_string_part(PART_KEY_OS_VERSION, os_version)
    if machine:
        parts += _encode_string_part(PART_KEY_CLIENT_MODEL, machine)

    # Count parts actually encoded. Integer part sizes are implicit in the
    # official NSLogger protocol, variable-size parts carry a 4-byte length.
    part_count = 0
    offset = 0
    temp = parts
    while offset < len(temp):
        if offset + 2 > len(temp):
            break
        part_type = temp[offset + 1]
        offset += 2
        if part_type == PART_TYPE_INT16:
            offset += 2
        elif part_type == PART_TYPE_INT32:
            offset += 4
        else:
            if offset + 4 > len(temp):
                break
            part_len = struct.unpack(">I", temp[offset:offset + 4])[0]
            offset += 4 + part_len
        part_count += 1

    body = struct.pack(">H", part_count) + parts
    return struct.pack(">I", len(body)) + body


def generate_sample_file(path: str, count: int = 20):
    """Write a sample .rawnsloggerdata file with synthetic messages."""
    import random

    tags = ["Network", "UI", "Database", "Auth", "Cache", ""]
    levels = [0, 0, 1, 1, 2, 2, 2, 3, 3, 4]
    threads = ["main", "main", "background", "network-queue", "io-queue"]
    base_ts = time.time() - count

    messages_text = [
        "Starting application",
        "Fetching user data from API",
        "User authenticated successfully",
        "Cache miss for key: user_profile",
        "Database query took 45ms",
        "Network request failed: timeout",
        "Retry attempt 1/3",
        "View did appear: HomeViewController",
        "Decoding JSON response",
        "Background sync completed",
        "Memory warning received",
        "Connection pool exhausted",
        "SSL handshake completed",
        "Pushing notification",
        "Saving to CoreData",
        "Failed to parse response body",
        "Token refreshed successfully",
        "WebSocket connected",
        "User tapped login button",
        "App did enter background",
    ]

    with open(path, "wb") as f:
        # Write client info message first
        f.write(encode_message(
            sequence=0,
            msg_type=3,  # client info
            timestamp=base_ts,
            client_name="SampleApp",
            client_version="1.0.0",
            os_name="iOS",
            os_version="17.0",
            machine="iPhone15,2",
        ))
        for i in range(1, count + 1):
            ts = base_ts + i * 0.5 + random.uniform(0, 0.4)
            text = messages_text[i % len(messages_text)]
            f.write(encode_message(
                sequence=i,
                msg_type=0,
                timestamp=ts,
                thread_id=random.choice(threads),
                tag=random.choice(tags),
                level=random.choice(levels),
                text=text,
            ))
