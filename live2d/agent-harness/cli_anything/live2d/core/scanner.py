"""Scan directories for Live2D models."""

from pathlib import Path
from typing import Optional

from .parser import ModelInfo, load_model


def scan_directory(directory: Path, recursive: bool = True) -> list[ModelInfo]:
    """Find and parse all .model3.json files in a directory."""
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pattern = "**/*.model3.json" if recursive else "*.model3.json"
    model_files = sorted(directory.glob(pattern))

    models = []
    errors = []
    for mf in model_files:
        try:
            models.append(load_model(mf))
        except Exception as e:
            errors.append({"file": str(mf), "error": str(e)})

    return models


def find_model_files(directory: Path, recursive: bool = True) -> list[Path]:
    """Find all .model3.json paths without parsing."""
    if not directory.exists():
        return []
    pattern = "**/*.model3.json" if recursive else "*.model3.json"
    return sorted(directory.glob(pattern))
