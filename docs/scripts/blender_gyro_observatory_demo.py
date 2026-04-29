#!/usr/bin/env python3
"""Compatibility wrapper for the orbital relay drone Blender demo."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    target = Path(__file__).with_name("blender_orbital_relay_drone_demo.py")
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
