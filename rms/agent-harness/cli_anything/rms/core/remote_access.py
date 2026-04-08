"""Remote access operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_delete


def list_sessions(token, device_id=None, limit=25, offset=0):
    params = {"limit": limit, "offset": offset}
    if device_id is not None:
        params["device_id"] = device_id
    return api_get("/device_remote_access", params=params, token=token)


def get_session(token, session_id):
    return api_get(f"/device_remote_access/{session_id}", token=token)


def create_session(token, data):
    return api_post("/device_remote_access", data=data, token=token)


def delete_session(token, session_id):
    return api_delete(f"/device_remote_access/{session_id}", token=token)
