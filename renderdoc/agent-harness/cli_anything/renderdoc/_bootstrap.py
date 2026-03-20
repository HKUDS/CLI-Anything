"""
Bootstrap renderdoc native module import.

This module ensures the native renderdoc.pyd (and its dependency renderdoc.dll)
can be found by Python. It adds the ``native/`` directory to sys.path so that
``import renderdoc`` resolves to the compiled SWIG bindings built for
Python 3.10.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_NATIVE_DIR = os.path.join(_HERE, "native")


def ensure_native_on_path():
    """Add the native/ directory to sys.path (idempotent)."""
    if _NATIVE_DIR not in sys.path:
        sys.path.insert(0, _NATIVE_DIR)
