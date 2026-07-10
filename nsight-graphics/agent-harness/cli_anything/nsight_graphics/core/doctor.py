"""Doctor commands."""

from __future__ import annotations

from cli_anything.nsight_graphics.utils import nsight_graphics_backend as backend


def get_installation_report(nsight_path: str | None = None) -> dict:
    """Return the current Nsight Graphics installation report."""
    return backend.probe_installation(nsight_path=nsight_path)


def list_installations(nsight_path: str | None = None) -> dict:
    """Return all detected Nsight Graphics installations."""
    return backend.list_installations(nsight_path=nsight_path)
