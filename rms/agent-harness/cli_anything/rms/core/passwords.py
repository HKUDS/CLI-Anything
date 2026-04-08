"""Device password operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_put


def get_password(token, device_id):
    return api_get(f"/device_passwords/{device_id}", token=token)


def update_password(token, device_id, data):
    return api_put(f"/device_passwords/{device_id}", data=data, token=token)
