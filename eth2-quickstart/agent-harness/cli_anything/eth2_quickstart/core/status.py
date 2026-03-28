"""Status and health helpers."""

from __future__ import annotations

import json


def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def health_check(backend) -> dict:
    result = backend.run_wrapper("doctor", "--json")
    parsed = _try_parse_json(result.get("stdout", ""))
    return {
        "repo_root": str(backend.repo_root),
        "command_result": result,
        "doctor": parsed,
        "ok": result["ok"],
    }


def status(backend) -> dict:
    doctor_result = backend.run_wrapper("doctor", "--json")
    plan_result = backend.run_wrapper("plan", "--json")
    stats_result = backend.run_wrapper("stats")
    return {
        "repo_root": str(backend.repo_root),
        "doctor": _try_parse_json(doctor_result.get("stdout", "")),
        "plan": _try_parse_json(plan_result.get("stdout", "")),
        "stats_raw": stats_result.get("stdout", ""),
        "commands": {
            "doctor": doctor_result,
            "plan": plan_result,
            "stats": stats_result,
        },
        "ok": doctor_result["ok"] and plan_result["ok"] and stats_result["ok"],
    }

