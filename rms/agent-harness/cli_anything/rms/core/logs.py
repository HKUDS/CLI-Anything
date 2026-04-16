"""Device log operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_delete


def list_logs(token, device_id=None, limit=25, offset=0):
    params = {"limit": limit, "offset": offset}
    if device_id is not None:
        params["device_id"] = device_id
    return api_get("/device_logs", params=params, token=token)


def get_log(token, log_id):
    return api_get(f"/device_logs/{log_id}", token=token)


def delete_log(token, log_id):
    return api_delete(f"/device_logs/{log_id}", token=token)
