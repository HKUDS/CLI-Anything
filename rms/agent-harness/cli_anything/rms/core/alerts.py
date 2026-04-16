"""Alert operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_put, api_delete


def list_alerts(token, device_id=None, limit=25, offset=0):
    params = {"limit": limit, "offset": offset}
    if device_id is not None:
        params["device_id"] = device_id
    return api_get("/device_alerts", params=params, token=token)


def get_alert(token, alert_id):
    return api_get(f"/device_alerts/{alert_id}", token=token)


def delete_alert(token, alert_id):
    return api_delete(f"/device_alerts/{alert_id}", token=token)


def list_alert_configs(token, limit=25, offset=0):
    return api_get("/device_alert_configurations", params={"limit": limit, "offset": offset}, token=token)


def get_alert_config(token, config_id):
    return api_get(f"/device_alert_configurations/{config_id}", token=token)


def create_alert_config(token, data):
    return api_post("/device_alert_configurations", data=data, token=token)


def update_alert_config(token, config_id, data):
    return api_put(f"/device_alert_configurations/{config_id}", data=data, token=token)


def delete_alert_config(token, config_id):
    return api_delete(f"/device_alert_configurations/{config_id}", token=token)
