"""Backend for the Notepad GUI harness.

Constants are baked in from a live UIA capture of Windows 11 Notepad. The
actual driving lives in utils/uia_runner.py, which is self-contained.
"""

from __future__ import annotations

from pathlib import Path

TARGET_EXECUTABLE = Path(r"C://Windows//System32//notepad.exe")
TARGET_WINDOW_PROCESS = "Notepad"
TARGET_WINDOW_TITLE = ""  # empty = match any Notepad window by process class


class BackendError(Exception):
    """Raised for guard violations. CLI maps this to exit code 2."""
