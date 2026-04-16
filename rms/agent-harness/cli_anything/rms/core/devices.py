"""Device operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_put, api_delete


def list_devices(token, status=None, tag=None, limit=25, offset=0, sort=None):
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    if tag:
        params["tag"] = ",".join(tag) if isinstance(tag, (list, tuple)) else tag
    if sort:
        params["sort"] = sort
    return api_get("/devices", params=params, token=token)


def get_device(token, device_id):
    return api_get(f"/devices/{device_id}", token=token)


def update_device(token, device_id, data):
    return api_put(f"/devices/{device_id}", data=data, token=token)


def delete_device(token, device_id):
    return api_delete(f"/devices/{device_id}", token=token)
