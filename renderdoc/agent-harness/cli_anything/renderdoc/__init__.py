"""RenderDoc CLI harness - command-line interface for RenderDoc graphics debugger."""

__version__ = "0.1.0"

# Ensure the native renderdoc.pyd / renderdoc.dll are importable
from cli_anything.renderdoc._bootstrap import ensure_native_on_path as _ensure
_ensure()
del _ensure
