"""Conversion helpers for cli-anything-calibre."""

from __future__ import annotations

from typing import Any

from cli_anything.calibre.utils import calibre_backend as backend


PRESETS = {
    "kindle": ["--output-profile", "kindle_pw3"],
    "tablet": ["--output-profile", "tablet"],
    "generic-epub": ["--output-profile", "generic_eink"],
}


def list_formats() -> list[str]:
    return backend.detect_available_formats()


def list_presets() -> dict[str, list[str]]:
    return PRESETS


def convert_book(input_path: str, output_path: str, preset: str | None = None, extra_args: list[str] | None = None) -> dict[str, Any]:
    args = []
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset: {preset}")
        args.extend(PRESETS[preset])
    if extra_args:
        args.extend(extra_args)
    result = backend.ebook_convert(input_path, output_path, extra_args=args)
    result["preset"] = preset
    return result
