"""Company operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_put, api_delete


def list_companies(token, limit=25, offset=0):
    return api_get("/companies", params={"limit": limit, "offset": offset}, token=token)


def get_company(token, company_id):
    return api_get(f"/companies/{company_id}", token=token)


def create_company(token, data):
    return api_post("/companies", data=data, token=token)


def update_company(token, company_id, data):
    return api_put(f"/companies/{company_id}", data=data, token=token)


def delete_company(token, company_id):
    return api_delete(f"/companies/{company_id}", token=token)
