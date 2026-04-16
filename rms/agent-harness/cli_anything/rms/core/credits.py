"""Credit operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post


def list_credits(token, limit=25, offset=0):
    return api_get("/credits", params={"limit": limit, "offset": offset}, token=token)


def transfer_credits(token, data):
    return api_post("/credits", data=data, token=token)


def list_transfer_codes(token, limit=25, offset=0):
    return api_get("/credit_transfer_codes", params={"limit": limit, "offset": offset}, token=token)
