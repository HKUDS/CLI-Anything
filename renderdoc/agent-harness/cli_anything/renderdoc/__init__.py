"""RenderDoc CLI harness - command-line interface for RenderDoc graphics debugger."""

__version__ = "0.1.0"

# Ensure the native renderdoc.pyd / renderdoc.dll are importable.
# Try the system-installed renderdoc first; fall back to the bundled native/ copy.
try:
    import renderdoc as _rd_probe  # noqa: F401
    del _rd_probe
except ImportError:
    from cli_anything.renderdoc._bootstrap import ensure_native_on_path as _ensure
    _ensure()
    del _ensure
