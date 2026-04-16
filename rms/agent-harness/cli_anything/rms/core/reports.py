"""Report operations for RMS API."""
from __future__ import annotations
from cli_anything.rms.utils.rms_backend import api_get, api_post, api_put, api_delete


def list_reports(token, limit=25, offset=0):
    return api_get("/reports", params={"limit": limit, "offset": offset}, token=token)


def get_report(token, report_id):
    return api_get(f"/reports/{report_id}", token=token)


def create_report(token, data):
    return api_post("/reports", data=data, token=token)


def delete_report(token, report_id):
    return api_delete(f"/reports/{report_id}", token=token)


def list_templates(token, limit=25, offset=0):
    return api_get("/report_templates", params={"limit": limit, "offset": offset}, token=token)


def get_template(token, template_id):
    return api_get(f"/report_templates/{template_id}", token=token)


def create_template(token, data):
    return api_post("/report_templates", data=data, token=token)


def update_template(token, template_id, data):
    return api_put(f"/report_templates/{template_id}", data=data, token=token)


def delete_template(token, template_id):
    return api_delete(f"/report_templates/{template_id}", token=token)
