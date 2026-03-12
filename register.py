#!/usr/bin/env python3
"""Convenience entrypoint for unified CLI-Anything registration.

Allows running from repository root:
    python3 register.py <command> [options]
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "scripts" / "register.py"

if not SCRIPT.is_file():
    sys.exit(f"error: missing script: {SCRIPT}")

os.environ.setdefault("CLI_ANYTHING_REGISTER_CMD", "python3 register.py")
runpy.run_path(str(SCRIPT), run_name="__main__")
