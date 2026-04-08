"""Device configuration operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_put


def list_configs(token, device_id=None, limit=25, offset=0):
    params = {"limit": limit, "offset": offset}
    if device_id is not None:
        params["device_id"] = device_id
    return api_get("/device_configurations", params=params, token=token)


def get_config(token, config_id):
    return api_get(f"/device_configurations/{config_id}", token=token)


def update_config(token, config_id, data):
    return api_put(f"/device_configurations/{config_id}", data=data, token=token)
