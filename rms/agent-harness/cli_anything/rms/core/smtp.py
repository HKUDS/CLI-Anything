"""SMTP configuration operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_put, api_delete


def list_smtp_configs(token, limit=25, offset=0):
    return api_get("/smtp_configurations", params={"limit": limit, "offset": offset}, token=token)


def get_smtp_config(token, config_id):
    return api_get(f"/smtp_configurations/{config_id}", token=token)


def create_smtp_config(token, data):
    return api_post("/smtp_configurations", data=data, token=token)


def update_smtp_config(token, config_id, data):
    return api_put(f"/smtp_configurations/{config_id}", data=data, token=token)


def delete_smtp_config(token, config_id):
    return api_delete(f"/smtp_configurations/{config_id}", token=token)
