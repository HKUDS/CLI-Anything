"""
LLDB backend helpers: import and environment discovery for lldb Python bindings.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _install_hint() -> str:
    return (
        "LLDB not found. Install LLDB:\n"
        "  macOS:  xcode-select --install\n"
        "  Ubuntu: sudo apt install lldb python3-lldb\n"
        "  Windows: winget install LLVM.LLVM\n"
        "Then ensure 'lldb' is on PATH."
    )


def ensure_lldb_importable():
    """Ensure ``lldb`` Python module can be imported.

    Strategy:
    1) Try regular ``import lldb``
    2) Fallback to ``lldb -P`` to discover LLDB's Python module path
    """
    try:
        import lldb  # type: ignore

        return lldb
    except ImportError:
        pass

    try:
        result = subprocess.run(
            ["lldb", "-P"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(_install_hint()) from exc
    except Exception as exc:  # pragma: no cover - defensive path
        raise RuntimeError(f"Failed to probe LLDB Python path: {exc}") from exc

    lldb_python_path = result.stdout.strip()
    if lldb_python_path and os.path.isdir(lldb_python_path):
        if lldb_python_path not in sys.path:
            sys.path.insert(0, lldb_python_path)
        try:
            import lldb  # type: ignore

            return lldb
        except ImportError as exc:
            raise RuntimeError(
                "LLDB was found but Python bindings could not be imported from:\n"
                f"  {lldb_python_path}\n"
                "Check your LLDB installation and Python version compatibility."
            ) from exc

    stderr = result.stderr.strip()
    detail = f"\nProbe stderr: {stderr}" if stderr else ""
    raise RuntimeError(_install_hint() + detail)
