"""Device location operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get


def get_location(token, device_id):
    return api_get(f"/device_location/{device_id}", token=token)


def list_location_history(token, device_id, limit=25, offset=0):
    return api_get(
        f"/device_location/{device_id}/history",
        params={"limit": limit, "offset": offset},
        token=token,
    )
