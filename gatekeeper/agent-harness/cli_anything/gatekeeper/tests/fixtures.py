"""Shared test fixtures: a synthetic NCS tender and a realistic Gatekeeper report."""

from __future__ import annotations

import base64
import json
import time
import zipfile
from pathlib import Path


def make_jwt(email: str = "buyer@example.com", exp_in: int = 3600) -> str:
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': 'HS256'})}.{b64({'email': email, 'exp': int(time.time()) + exp_in, 'sub': 'u1'})}.sig"


def make_docx(path: Path, paragraphs: list[str]) -> Path:
    body = "".join(f"<w:p><w:r><w:t>{p.replace(chr(9), '</w:t><w:tab/><w:t>')}</w:t></w:r></w:p>"
                   for p in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml",
                   f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   f"<w:body>{body}</w:body></w:document>")
    return path


def make_xlsx(path: Path) -> Path:
    shared = ["Item", "Qty", "Total NOK", "Umbilical 12 km", "Terminations &amp; testing"]
    ss = "<sst>" + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>"
    sheet = ('<worksheet><sheetData>'
             '<row r="1"><c t="s"><v>0</v></c><c t="s"><v>1</v></c><c t="s"><v>2</v></c></row>'
             '<row r="2"><c t="s"><v>3</v></c><c><v>1</v></c><c><v>18000000</v></c></row>'
             '<row r="3"><c t="s"><v>4</v></c><c><v>2</v></c><c><v>3400000</v></c></row>'
             '<row r="4"><c t="inlineStr"><is><t>Grand total</t></is></c><c/><c><v>21400000</v></c></row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", ss)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/worksheets/sheet2.xml", "<worksheet><sheetData><row><c t=\"inlineStr\"><is><t>Notes</t></is></c></row></sheetData></worksheet>")
    return path


def make_pdf(path: Path, lines: list[str]) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.save()
    return path


def make_tender(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    make_docx(root / "rfp.docx", [
        "RFP NCS-2026-114 — Subsea Umbilical Supply",
        "Buyer: Nordhav Energy ASA. Currency: NOK.",
        "REQ-001\tDNV-ST-F119 certification\tMandatory",
        "REQ-002\tDelivery within 30 weeks\tMandatory",
        "REQ-003\tLocal content above 20%\tDesirable",
    ])
    make_pdf(root / "alphasub_bid.pdf", [
        "AlphaSub AS — Technical and Commercial Proposal",
        "We hold DNV-ST-F119 certification (certificate 22-1180).",
        "Delivery: 28 weeks ARO. Quoted total NOK 21,400,000.",
        "Payment terms 30/40/30 milestones. Validity 90 days. Local content 24%.",
    ])
    make_pdf(root / "betamarine_bid.pdf", [
        "BetaMarine Ltd — Proposal",
        "DNV-ST-F119 certification in progress, expected Q3.",
        "Delivery 34 weeks. Quoted total NOK 19,900,000. Validity 60 days.",
    ])
    make_xlsx(root / "alphasub_bom.xlsx")
    (root / "clarifications.txt").write_text("BetaMarine to confirm certification timeline.\n")
    (root / "ignored.png").write_bytes(b"\x89PNG")  # not an accepted type; folder scan skips it
    return root


SAMPLE_EVALUATION = {
    "project": {"name": "Subsea Umbilical Supply", "rfp_number": "NCS-2026-114",
                "buyer": "Nordhav Energy ASA", "currency": "NOK"},
    "vendors": [
        {"name": "BetaMarine", "rank": 2, "total_score": 60, "status": "FAIL",
         "bid_amount": 19900000, "delivery_weeks": 34, "confidence": 0.82,
         "fail_reason": "Missing mandatory DNV-ST-F119 certification",
         "risk_flags": [{"flag": "Certification not yet issued", "severity": "high"}],
         "missing_documents": ["DNV-ST-F119 certificate"], "strengths": [], "weaknesses": []},
        {"name": "AlphaSub", "rank": 1, "total_score": 90.75, "status": "PASS",
         "bid_amount": 21400000, "delivery_weeks": 28, "confidence": 0.91, "fail_reason": None,
         "risk_flags": [{"flag": "Milestone payment front-loaded", "severity": "medium"}],
         "missing_documents": []},
    ],
    "compliance_matrix": {"requirements": [
        {"id": "REQ-001", "requirement": "DNV-ST-F119 certification", "mandatory": True, "vendors": [
            {"vendor": "AlphaSub", "status": "PASS", "evidence": "certificate 22-1180"},
            {"vendor": "BetaMarine", "status": "FAIL", "evidence": "certification in progress"}]},
        {"id": "REQ-002", "requirement": "Delivery within 30 weeks", "mandatory": True, "vendors": [
            {"vendor": "AlphaSub", "status": "PASS", "evidence": "28 weeks ARO"},
            {"vendor": "BetaMarine", "status": "FAIL", "evidence": "34 weeks"}]},
        {"id": "REQ-003", "requirement": "Local content above 20%", "mandatory": False, "vendors": [
            {"vendor": "AlphaSub", "status": "PASS", "evidence": "24%"},
            {"vendor": "BetaMarine", "status": "N/A", "evidence": "not stated"}]},
    ]},
    "pricing_analysis": [
        {"vendor": "AlphaSub", "quoted_total": 21400000, "line_item_sum": 21400000, "discrepancy": 0,
         "payment_terms": "30/40/30", "validity_days": 90},
        {"vendor": "BetaMarine", "quoted_total": 19900000, "line_item_sum": 20010000, "discrepancy": 110000,
         "payment_terms": "Net 30", "validity_days": 60},
    ],
    "recommendation": {"vendor": "AlphaSub", "rationale": "Only fully compliant bid.",
                       "savings_flagged": "NOK 110,000 arithmetic gap in BetaMarine bid",
                       "conditions": ["Confirm validity extension to 120 days"]},
    "evaluation_summary": "AlphaSub is the only compliant bidder.\nBetaMarine fails REQ-001.",
    "weights_used": {"technical": 25, "pricing": 20, "delivery": 15, "hse": 15, "experience": 10, "commercial": 15},
    "platform_adjustments": [],
}


def api_response(evaluation=None):
    return {"success": True, "evaluation": evaluation or SAMPLE_EVALUATION,
            "processingTime": 82900, "plan": "professional", "model": "claude-opus-5",
            "evaluationId": "ev_123"}
