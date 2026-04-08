"""Device hotspot operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_put, api_delete


def list_hotspots(token, device_id=None, limit=25, offset=0):
    params = {"limit": limit, "offset": offset}
    if device_id is not None:
        params["device_id"] = device_id
    return api_get("/device_hotspots", params=params, token=token)


def get_hotspot(token, hotspot_id):
    return api_get(f"/device_hotspots/{hotspot_id}", token=token)


def create_hotspot(token, data):
    return api_post("/device_hotspots", data=data, token=token)


def update_hotspot(token, hotspot_id, data):
    return api_put(f"/device_hotspots/{hotspot_id}", data=data, token=token)


def delete_hotspot(token, hotspot_id):
    return api_delete(f"/device_hotspots/{hotspot_id}", token=token)
