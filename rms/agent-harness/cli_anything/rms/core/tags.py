"""Tag operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_put, api_delete


def list_tags(token, limit=25, offset=0):
    return api_get("/tags", params={"limit": limit, "offset": offset}, token=token)


def get_tag(token, tag_id):
    return api_get(f"/tags/{tag_id}", token=token)


def create_tag(token, data):
    return api_post("/tags", data=data, token=token)


def update_tag(token, tag_id, data):
    return api_put(f"/tags/{tag_id}", data=data, token=token)


def delete_tag(token, tag_id):
    return api_delete(f"/tags/{tag_id}", token=token)
