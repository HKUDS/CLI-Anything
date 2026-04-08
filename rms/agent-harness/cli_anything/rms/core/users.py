"""User operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_put, api_delete


def list_users(token, limit=25, offset=0):
    return api_get("/users", params={"limit": limit, "offset": offset}, token=token)


def get_user(token, user_id):
    return api_get(f"/users/{user_id}", token=token)


def invite_user(token, data):
    return api_post("/user_invitations", data=data, token=token)


def update_user(token, user_id, data):
    return api_put(f"/users/{user_id}", data=data, token=token)


def delete_user(token, user_id):
    return api_delete(f"/users/{user_id}", token=token)
