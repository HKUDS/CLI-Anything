"""report.py — read Gatekeeper reports: saved history (server) and offline views.

Offline views work on a report JSON from `evaluate -o` or `reports get -o`,
so an agent can slice a report many times without spending a credit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cli_anything.gatekeeper.core import session
from cli_anything.gatekeeper.utils import gk_backend as gk


# ---------------------------------------------------------------------------
# Saved reports (Supabase `evaluations`, scoped to the signed-in user)
# ---------------------------------------------------------------------------

def _email(token: str) -> str:
    email = session.jwt_claims(token).get("email")
    if not email:
        email = (gk.get_user(token) or {}).get("email")
    if not email:
        raise gk.GatekeeperError("Could not determine the signed-in email.", 401)
    return email


def list_saved(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    token = session.get_token()
    rows = gk.select_evaluations(token, {
        "select": "id,completed_at,file_names,vendor_count",
        "user_email": f"eq.{_email(token)}",
        "status": "eq.complete",
        "order": "completed_at.desc,id.desc",
        "limit": str(limit), "offset": str(offset),
    })
    return {"reports": rows, "count": len(rows), "offset": offset,
            "more": len(rows) == limit, "note": "Opening a saved report uses no evaluation credits."}


def get_saved(report_id: str, output: str | None = None) -> dict[str, Any]:
    token = session.get_token()
    rows = gk.select_evaluations(token, {
        "select": "id,result,plan,model,processing_time_ms,completed_at,file_names",
        "user_email": f"eq.{_email(token)}",
        "status": "eq.complete", "id": f"eq.{report_id}",
    })
    if not rows or not isinstance((rows[0].get("result") or {}).get("vendors"), list):
        raise gk.GatekeeperError(f"Report {report_id} not found or unavailable.", 404)
    r = rows[0]
    data = {"success": True, "evaluation": r["result"], "evaluationId": r["id"],
            "plan": r.get("plan"), "model": r.get("model"),
            "processingTime": r.get("processing_time_ms"),
            "completed_at": r.get("completed_at"), "file_names": r.get("file_names")}
    if output:
        Path(output).expanduser().write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
        data["saved_to"] = str(Path(output).expanduser().resolve())
    return data


# ---------------------------------------------------------------------------
# Offline views
# ---------------------------------------------------------------------------

def load(path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (evaluation, meta) from any of the shapes we write or the API returns."""
    raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("evaluation"), dict):
        meta = {k: raw.get(k) for k in ("model", "plan", "processingTime", "evaluationId")}
        return raw["evaluation"], meta
    if isinstance(raw, dict) and isinstance(raw.get("result"), dict):
        return raw["result"], {"model": raw.get("model"), "plan": raw.get("plan")}
    if isinstance(raw, dict) and "vendors" in raw:
        return raw, {}
    raise ValueError(f"{path} is not a Gatekeeper report")


def summary(ev: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    project = ev.get("project") or {}
    vendors = sorted(ev.get("vendors") or [], key=lambda v: (v.get("rank") or 999))
    rec = ev.get("recommendation") or {}
    reqs = (ev.get("compliance_matrix") or {}).get("requirements") or []
    mandatory_fails = sum(1 for r in reqs if r.get("mandatory")
                          for c in (r.get("vendors") or []) if c.get("status") == "FAIL")
    return {
        "project": {k: project.get(k) for k in ("name", "rfp_number", "buyer", "currency")},
        "recommended_vendor": rec.get("vendor") or None,
        "rationale": rec.get("rationale"),
        "savings_flagged": rec.get("savings_flagged"),
        "conditions": rec.get("conditions") or [],
        "vendors": [{k: v.get(k) for k in ("rank", "name", "total_score", "status",
                                            "bid_amount", "delivery_weeks", "confidence",
                                            "fail_reason")} for v in vendors],
        "counts": {"vendors": len(vendors), "requirements": len(reqs),
                   "mandatory_fail_cells": mandatory_fails,
                   "risk_flags": sum(len(v.get("risk_flags") or []) for v in vendors),
                   "pricing_rows": len(ev.get("pricing_analysis") or [])},
        "platform_adjustments": ev.get("platform_adjustments") or [],
        "weights_used": ev.get("weights_used"),
        "meta": meta or {},
    }


def compliance(ev: dict[str, Any], status: str | None = None, mandatory_only: bool = False,
               vendor: str | None = None) -> dict[str, Any]:
    rows = []
    for r in (ev.get("compliance_matrix") or {}).get("requirements") or []:
        if mandatory_only and not r.get("mandatory"):
            continue
        for c in r.get("vendors") or []:
            if status and (c.get("status") or "").upper() != status.upper():
                continue
            if vendor and vendor.lower() not in (c.get("vendor") or "").lower():
                continue
            rows.append({"id": r.get("id"), "requirement": r.get("requirement"),
                         "mandatory": bool(r.get("mandatory")), "vendor": c.get("vendor"),
                         "status": c.get("status"), "evidence": c.get("evidence")})
    return {"cells": rows, "count": len(rows)}


def pricing(ev: dict[str, Any]) -> dict[str, Any]:
    rows = ev.get("pricing_analysis") or []
    return {"rows": rows, "count": len(rows),
            "discrepancies": [r for r in rows if r.get("discrepancy") not in (None, 0, "", "0", "none")]}


def risks(ev: dict[str, Any]) -> dict[str, Any]:
    out = []
    for v in ev.get("vendors") or []:
        for f in v.get("risk_flags") or []:
            item = dict(f) if isinstance(f, dict) else {"flag": f}
            item["vendor"] = v.get("name")
            out.append(item)
        for m in v.get("missing_documents") or []:
            out.append({"vendor": v.get("name"), "flag": f"Missing document: {m}",
                        "severity": "missing_document"})
    return {"risks": out, "count": len(out)}


def _fmt(n: Any) -> str:
    if n is None or n == "":
        return "—"
    try:
        return f"{float(n):,.0f}"
    except (TypeError, ValueError):
        return str(n)


def to_markdown(ev: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    s = summary(ev, meta)
    p, cur = s["project"], (s["project"].get("currency") or "")
    L = [f"# Procurement Evaluation — {p.get('name') or 'Evaluation'}", "",
         f"- **RFP:** {p.get('rfp_number') or '—'}  ",
         f"- **Buyer:** {p.get('buyer') or '—'}  ",
         f"- **Recommended:** {s['recommended_vendor'] or 'No award recommended'}", ""]
    if s["rationale"]:
        L += ["## Recommendation", "", s["rationale"], ""]
        if s["savings_flagged"]:
            L += [f"**Savings flagged:** {s['savings_flagged']}", ""]
        L += [f"- {c}" for c in s["conditions"]] + ([""] if s["conditions"] else [])
    L += ["## Vendor ranking", "", f"| Rank | Vendor | Score | Status | Bid ({cur}) | Delivery (wks) | Fail reason |",
          "|---|---|---|---|---|---|---|"]
    for v in s["vendors"]:
        L.append(f"| {v['rank'] or '—'} | {v['name']} | {v['total_score'] if v['total_score'] is not None else '—'} "
                 f"| {v['status'] or '—'} | {_fmt(v['bid_amount'])} | {v['delivery_weeks'] or '—'} "
                 f"| {v['fail_reason'] or ''} |")
    cells = compliance(ev)["cells"]
    if cells:
        names = [v["name"] for v in s["vendors"]]
        L += ["", "## Compliance matrix", "", "| Req | Requirement | M | " + " | ".join(names) + " |",
              "|---|---|---|" + "---|" * len(names)]
        for r in (ev.get("compliance_matrix") or {}).get("requirements") or []:
            st = {c.get("vendor"): c.get("status") for c in r.get("vendors") or []}
            L.append(f"| {r.get('id')} | {r.get('requirement')} | {'M' if r.get('mandatory') else ''} | "
                     + " | ".join(st.get(n) or "—" for n in names) + " |")
    pr = pricing(ev)["rows"]
    if pr:
        L += ["", "## Pricing analysis", "", "| Vendor | Quoted total | Line-item sum | Discrepancy | Payment terms | Validity (days) |",
              "|---|---|---|---|---|---|"]
        for r in pr:
            L.append(f"| {r.get('vendor')} | {_fmt(r.get('quoted_total'))} | {_fmt(r.get('line_item_sum'))} "
                     f"| {_fmt(r.get('discrepancy'))} | {r.get('payment_terms') or '—'} | {r.get('validity_days') or '—'} |")
    rk = risks(ev)["risks"]
    if rk:
        L += ["", "## Risk flags", ""]
        for r in rk:
            sev = r.get("severity") or r.get("level") or ""
            L.append(f"- **{r['vendor']}**{f' ({sev})' if sev else ''}: "
                     f"{r.get('flag') or r.get('description') or r.get('risk') or json.dumps(r)}")
    if ev.get("evaluation_summary"):
        L += ["", "## Executive summary", "", ev["evaluation_summary"]]
    if s["platform_adjustments"]:
        L += ["", "## Platform adjustments", ""] + [f"- {json.dumps(a, ensure_ascii=False)}"
                                                   for a in s["platform_adjustments"]]
    if meta and meta.get("model"):
        L += ["", f"_Model: {meta['model']} · plan: {meta.get('plan') or '—'}_"]
    return "\n".join(L) + "\n"
