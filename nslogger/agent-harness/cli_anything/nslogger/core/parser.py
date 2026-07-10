"""Parse NSLogger raw wire-protocol (.rawnsloggerdata) files."""
from __future__ import annotations
import struct
from datetime import datetime, timezone
from typing import Iterator, BinaryIO
from .message import (
    LogMessage,
    PART_KEY_MESSAGE_TYPE, PART_KEY_TIMESTAMP_S, PART_KEY_TIMESTAMP_MS,
    PART_KEY_TIMESTAMP_US, PART_KEY_THREAD_ID, PART_KEY_TAG, PART_KEY_LEVEL, PART_KEY_MESSAGE,
    PART_KEY_IMAGE_WIDTH, PART_KEY_IMAGE_HEIGHT, PART_KEY_MESSAGE_SEQ,
    PART_KEY_CLIENT_NAME, PART_KEY_CLIENT_VERSION,
    PART_KEY_OS_NAME, PART_KEY_OS_VERSION, PART_KEY_CLIENT_MODEL,
    PART_TYPE_STRING, PART_TYPE_BINARY, PART_TYPE_INT16,
    PART_TYPE_INT32, PART_TYPE_INT64, PART_TYPE_IMAGE,
    MSG_TYPE_LOG,
)


class ParseError(Exception):
    pass


def _read_exactly(f: BinaryIO, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise ParseError(f"Expected {n} bytes, got {len(data)}")
    return data


def _decode_part_value(part_type: int, data: bytes):
    if part_type == PART_TYPE_STRING:
        return data.decode("utf-8", errors="replace")
    if part_type == PART_TYPE_INT16:
        if len(data) != 2:
            raise ParseError(f"Expected 2 bytes for int16, got {len(data)}")
        return struct.unpack(">H", data)[0]
    if part_type == PART_TYPE_INT32:
        if len(data) != 4:
            raise ParseError(f"Expected 4 bytes for int32, got {len(data)}")
        return struct.unpack(">I", data)[0]
    if part_type == PART_TYPE_INT64:
        if len(data) != 8:
            raise ParseError(f"Expected 8 bytes for int64, got {len(data)}")
        return struct.unpack(">Q", data)[0]
    if part_type in (PART_TYPE_BINARY, PART_TYPE_IMAGE):
        return data
    return data


def _part_data(raw: bytes, offset: int, part_type: int, *, implicit_int_sizes: bool) -> tuple[bytes, int]:
    if implicit_int_sizes and part_type in (PART_TYPE_INT16, PART_TYPE_INT32, PART_TYPE_INT64):
        part_len = {PART_TYPE_INT16: 2, PART_TYPE_INT32: 4, PART_TYPE_INT64: 8}[part_type]
        if offset + part_len > len(raw):
            raise ParseError("Truncated integer part")
        return raw[offset:offset + part_len], offset + part_len

    if offset + 4 > len(raw):
        raise ParseError("Truncated variable-length part")
    part_len = struct.unpack(">I", raw[offset:offset + 4])[0]
    offset += 4
    if offset + part_len > len(raw):
        raise ParseError("Truncated part data")
    return raw[offset:offset + part_len], offset + part_len


MESSAGE_TEXT_KEYS = {PART_KEY_MESSAGE, 6}
IMAGE_WIDTH_KEYS = {PART_KEY_IMAGE_WIDTH, 7}
IMAGE_HEIGHT_KEYS = {PART_KEY_IMAGE_HEIGHT, 8}
CLIENT_NAME_KEYS = {PART_KEY_CLIENT_NAME, 9}
CLIENT_VERSION_KEYS = {PART_KEY_CLIENT_VERSION, 10}
OS_NAME_KEYS = {PART_KEY_OS_NAME, 11}
OS_VERSION_KEYS = {PART_KEY_OS_VERSION, 12}
CLIENT_MODEL_KEYS = {PART_KEY_CLIENT_MODEL, 13}


def _is_int_value(value) -> bool:
    return isinstance(value, int)


def _is_text_value(part_type: int) -> bool:
    return part_type in (PART_TYPE_STRING, PART_TYPE_BINARY, PART_TYPE_IMAGE)


def _parse_message_payload(
    raw: bytes,
    offset: int,
    *,
    initial_sequence: int = 0,
    implicit_int_sizes: bool = True,
) -> LogMessage:
    """Parse a message payload starting at `offset`, where the payload begins with part_count."""
    if len(raw) - offset < 2:
        raise ParseError("Message too short")

    part_count = struct.unpack(">H", raw[offset:offset + 2])[0]
    msg = LogMessage(sequence=initial_sequence, message_type=MSG_TYPE_LOG)
    ts_s = None
    ts_ms = 0
    offset += 2

    for _ in range(part_count):
        if offset + 2 > len(raw):
            raise ParseError("Truncated part header")
        part_key = raw[offset]
        part_type = raw[offset + 1]
        offset += 2
        part_data, offset = _part_data(raw, offset, part_type, implicit_int_sizes=implicit_int_sizes)

        value = _decode_part_value(part_type, part_data)

        if part_key == PART_KEY_MESSAGE_TYPE:
            msg.message_type = value if isinstance(value, int) else int.from_bytes(part_data, "big")
        elif part_key == PART_KEY_TIMESTAMP_S:
            ts_s = value
        elif part_key == PART_KEY_TIMESTAMP_MS:
            ts_ms = value if isinstance(value, int) else 0
        elif part_key == PART_KEY_TIMESTAMP_US:
            ts_ms = (value // 1000) if isinstance(value, int) else 0
        elif part_key == PART_KEY_THREAD_ID:
            msg.thread_id = str(value) if not isinstance(value, str) else value
        elif part_key == PART_KEY_TAG:
            msg.tag = str(value) if not isinstance(value, str) else value
        elif part_key == PART_KEY_LEVEL:
            msg.level = value if isinstance(value, int) else 0
        elif part_key in MESSAGE_TEXT_KEYS and _is_text_value(part_type):
            if isinstance(value, bytes) and part_type in (PART_TYPE_BINARY, PART_TYPE_IMAGE):
                msg.image_data = value
            else:
                msg.text = str(value)
        elif part_key in IMAGE_WIDTH_KEYS and _is_int_value(value):
            msg.image_width = value
        elif part_key in IMAGE_HEIGHT_KEYS and _is_int_value(value):
            msg.image_height = value
        elif part_key == PART_KEY_MESSAGE_SEQ and _is_int_value(value):
            msg.sequence = value
        elif part_key in CLIENT_NAME_KEYS and part_type == PART_TYPE_STRING:
            msg.client_name = str(value)
        elif part_key in CLIENT_VERSION_KEYS and part_type == PART_TYPE_STRING:
            msg.client_version = str(value)
        elif part_key in OS_NAME_KEYS and part_type == PART_TYPE_STRING:
            msg.os_name = str(value)
        elif part_key in OS_VERSION_KEYS and part_type == PART_TYPE_STRING:
            msg.os_version = str(value)
        elif part_key in CLIENT_MODEL_KEYS and part_type == PART_TYPE_STRING:
            msg.machine = str(value)

    if ts_s is not None:
        ts_s_int = ts_s if isinstance(ts_s, int) else int(ts_s)
        msg.timestamp = datetime.fromtimestamp(ts_s_int, tz=timezone.utc)
        msg.timestamp_ms = ts_ms if isinstance(ts_ms, int) else 0

    # Detect binary data vs image
    if msg.image_data and not (msg.image_width or msg.image_height):
        msg.binary_data = msg.image_data
        msg.image_data = None

    return msg


def _parse_message(raw: bytes) -> LogMessage:
    """Parse a single wire-protocol message from raw bytes.

    NSLogger's native wire format is:
    [partCount][parts...]

    Older local test fixtures in this repo used:
    [sequence][partCount][parts...]
    We keep a best-effort fallback for those fixtures.
    """
    if len(raw) < 2:
        raise ParseError("Message too short")

    # Native NSLogger format: payload begins with partCount.
    try:
        msg = _parse_message_payload(raw, 0, implicit_int_sizes=True)
        if msg.message_type != MSG_TYPE_LOG or msg.text or msg.client_name or msg.image_data or msg.binary_data:
            return msg
    except ParseError:
        pass

    # Older generated fixtures used official part keys but still wrote a
    # redundant 4-byte size before integer values.
    try:
        msg = _parse_message_payload(raw, 0, implicit_int_sizes=False)
        if msg.message_type != MSG_TYPE_LOG or msg.text or msg.client_name or msg.image_data or msg.binary_data:
            return msg
    except ParseError:
        pass

    # Backward-compatible fallback for historical local fixtures.
    if len(raw) < 6:
        raise ParseError("Message too short")
    seq = struct.unpack(">I", raw[0:4])[0]
    try:
        return _parse_message_payload(raw, 4, initial_sequence=seq, implicit_int_sizes=False)
    except ParseError:
        return _parse_message_payload(raw, 4, initial_sequence=seq, implicit_int_sizes=True)


def parse_raw_file(path: str) -> Iterator[LogMessage]:
    """Yield LogMessage objects from a .rawnsloggerdata file."""
    with open(path, "rb") as f:
        while True:
            header = f.read(4)
            if not header:
                break
            if len(header) < 4:
                raise ParseError(f"Truncated file: got {len(header)} bytes in length header")
            msg_len = struct.unpack(">I", header)[0]
            if msg_len == 0:
                continue
            raw = f.read(msg_len)
            if len(raw) < msg_len:
                break
            try:
                yield _parse_message(raw)
            except ParseError:
                continue


def parse_file(path: str) -> Iterator[LogMessage]:
    """Auto-detect format and parse .rawnsloggerdata or .nsloggerdata files."""
    if path.endswith(".rawnsloggerdata"):
        yield from parse_raw_file(path)
    else:
        # .nsloggerdata is a binary plist wrapping archived messages
        # Fall back to raw parser which handles both (raw starts with length)
        yield from _parse_nsloggerdata(path)


def _parse_nsloggerdata(path: str) -> Iterator[LogMessage]:
    """Parse .nsloggerdata binary plist files via Python plistlib."""
    import plistlib
    try:
        with open(path, "rb") as f:
            data = plistlib.load(f)
        # NSLogger saves as a plist dict with 'messages' array
        messages = data if isinstance(data, list) else data.get("messages", [])
        for i, m in enumerate(messages):
            if not isinstance(m, dict):
                continue
            msg = LogMessage(sequence=i)
            ts = m.get("timestamp")
            if ts is not None:
                try:
                    msg.timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                    frac = float(ts) - int(float(ts))
                    msg.timestamp_ms = int(frac * 1000)
                except (TypeError, ValueError):
                    pass
            msg.tag = str(m.get("tag", ""))
            msg.level = int(m.get("level", 2))
            msg.thread_id = str(m.get("threadID", ""))
            msg.text = str(m.get("message", m.get("messageText", "")))
            yield msg
    except Exception:
        # Try raw protocol as fallback
        yield from parse_raw_file(path)
