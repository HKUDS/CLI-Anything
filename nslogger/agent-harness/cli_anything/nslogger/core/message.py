"""NSLogger message model and constants."""
from __future__ import annotations
import dataclasses
from datetime import datetime
from typing import Optional

# Message type constants (wire protocol)
MSG_TYPE_LOG = 0
MSG_TYPE_BLOCK_START = 1
MSG_TYPE_BLOCK_END = 2
MSG_TYPE_CLIENT_INFO = 3
MSG_TYPE_DISCONNECT = 4
MSG_TYPE_MARKER = 255

# Part key constants from the official NSLogger wire protocol.
PART_KEY_MESSAGE_TYPE = 0
PART_KEY_TIMESTAMP_S = 1
PART_KEY_TIMESTAMP_MS = 2
PART_KEY_TIMESTAMP_US = 3
PART_KEY_THREAD_ID = 4
PART_KEY_TAG = 5
PART_KEY_LEVEL = 6
PART_KEY_MESSAGE = 7
PART_KEY_IMAGE_WIDTH = 8
PART_KEY_IMAGE_HEIGHT = 9
PART_KEY_MESSAGE_SEQ = 10
PART_KEY_FILENAME = 11
PART_KEY_LINENUMBER = 12
PART_KEY_FUNCTIONNAME = 13
PART_KEY_CLIENT_NAME = 20
PART_KEY_CLIENT_VERSION = 21
PART_KEY_OS_NAME = 22
PART_KEY_OS_VERSION = 23
PART_KEY_CLIENT_MODEL = 24
PART_KEY_UNIQUEID = 25

# Part type constants
PART_TYPE_STRING = 0
PART_TYPE_BINARY = 1
PART_TYPE_INT16 = 2
PART_TYPE_INT32 = 3
PART_TYPE_INT64 = 4
PART_TYPE_IMAGE = 5

LEVEL_NAMES = {
    0: "ERROR",
    1: "WARNING",
    2: "INFO",
    3: "DEBUG",
    4: "VERBOSE",
    5: "NOISE",
}


@dataclasses.dataclass
class LogMessage:
    sequence: int = 0
    timestamp: Optional[datetime] = None
    timestamp_ms: int = 0
    thread_id: str = ""
    tag: str = ""
    level: int = 2
    message_type: int = MSG_TYPE_LOG
    text: str = ""
    image_width: int = 0
    image_height: int = 0
    image_data: Optional[bytes] = None
    binary_data: Optional[bytes] = None
    client_name: str = ""
    client_version: str = ""
    os_name: str = ""
    os_version: str = ""
    machine: str = ""

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, f"LEVEL{self.level}")

    @property
    def type_name(self) -> str:
        if self.message_type == MSG_TYPE_LOG:
            if self.image_data:
                return "image"
            if self.binary_data:
                return "data"
            return "text"
        type_map = {
            MSG_TYPE_BLOCK_START: "block_start",
            MSG_TYPE_BLOCK_END: "block_end",
            MSG_TYPE_CLIENT_INFO: "client_info",
            MSG_TYPE_DISCONNECT: "disconnect",
            MSG_TYPE_MARKER: "marker",
        }
        return type_map.get(self.message_type, f"type_{self.message_type}")

    def to_dict(self) -> dict:
        ts = self.timestamp.isoformat() if self.timestamp else None
        return {
            "sequence": self.sequence,
            "timestamp": ts,
            "timestamp_ms": self.timestamp_ms,
            "thread_id": self.thread_id,
            "tag": self.tag,
            "level": self.level,
            "level_name": self.level_name,
            "type": self.type_name,
            "text": self.text,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "client_name": self.client_name,
            "client_version": self.client_version,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "machine": self.machine,
        }

    def to_text_line(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S.") + f"{self.timestamp_ms:03d}" if self.timestamp else "??:??:??.???"
        tag_part = f"[{self.tag}] " if self.tag else ""
        thread_part = f"({self.thread_id}) " if self.thread_id else ""
        level_part = f"{self.level_name:<7} "
        if self.type_name == "image":
            content = f"<image {self.image_width}x{self.image_height}>"
        elif self.type_name == "data":
            size = len(self.binary_data) if self.binary_data else 0
            content = f"<binary data {size} bytes>"
        elif self.message_type == MSG_TYPE_CLIENT_INFO:
            content = f"CLIENT: {self.client_name} {self.client_version} on {self.os_name} {self.os_version} ({self.machine})"
        elif self.message_type == MSG_TYPE_BLOCK_START:
            content = f">>> {self.text}"
        elif self.message_type == MSG_TYPE_BLOCK_END:
            content = f"<<< {self.text}"
        else:
            content = self.text
        return f"{ts} {level_part}{thread_part}{tag_part}{content}"
