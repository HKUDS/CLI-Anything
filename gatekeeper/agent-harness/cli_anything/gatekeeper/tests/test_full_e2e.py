"""E2E tests.

1. Mock service — a local HTTP server speaking the exact Gatekeeper + Supabase
   contracts (/api/health, /api/config, /api/evaluate, /auth/v1/*, /rest/v1/
   evaluations). Drives the installed CLI as a subprocess, end to end.
2. Live service — real calls to https://www.gatekeeper.blog. These spend no
   credits. A real evaluation runs only when GATEKEEPER_LIVE_TOKEN is set.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from cli_anything.gatekeeper.tests import fixtures as fx


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    return [sys.executable, "-m", "cli_anything.gatekeeper"]


CLI = _resolve_cli("cli-anything-gatekeeper")


# ---------------------------------------------------------------------------
# Mock Gatekeeper + Supabase
# ---------------------------------------------------------------------------

class MockState:
    def __init__(self):
        self.requests: list[dict] = []
        self.evaluate_status = 200
        self.health_status = 200
        self.refresh_status = 200
        self.token = fx.make_jwt("buyer@example.com")
        self.refreshed = fx.make_jwt("buyer@example.com", exp_in=7200)


def make_handler(state: MockState, base: list[str]):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, headers=None):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"null")

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            state.requests.append({"method": "GET", "path": u.path, "query": q,
                                   "auth": self.headers.get("Authorization"),
                                   "apikey": self.headers.get("apikey")})
            if u.path == "/api/health":
                if state.health_status != 200:
                    return self._send(state.health_status, {"ok": False, "error": "model unavailable"})
                return self._send(200, {"status": "ok"})
            if u.path == "/api/config":
                return self._send(200, {"supabaseUrl": base[0], "supabaseAnonKey": "anon-key",
                                        "billingAvailable": True})
            if u.path == "/auth/v1/user":
                if self.headers.get("Authorization") in (f"Bearer {state.token}", f"Bearer {state.refreshed}"):
                    return self._send(200, {"email": "buyer@example.com"})
                return self._send(401, {"msg": "invalid JWT"})
            if u.path == "/auth/v1/verify":  # magic link click → 303 with tokens in fragment
                self.send_response(303)
                self.send_header("Location", f"{base[0]}/login?next=/evaluate#access_token={state.token}"
                                             f"&refresh_token=rt-link&expires_in=3600&type=magiclink")
                self.end_headers()
                return
            if u.path == "/rest/v1/evaluations":
                if self.headers.get("Authorization") not in (f"Bearer {state.token}", f"Bearer {state.refreshed}"):
                    return self._send(401, {"message": "JWT expired"})
                if "id" in q:
                    return self._send(200, [{"id": 7, "result": fx.SAMPLE_EVALUATION, "plan": "professional",
                                             "model": "claude-opus-5", "processing_time_ms": 81000,
                                             "completed_at": "2026-10-20T10:00:00Z",
                                             "file_names": ["rfp.docx"]}] if q["id"] == "eq.7" else [])
                return self._send(200, [{"id": 7, "completed_at": "2026-10-20T10:00:00Z",
                                         "file_names": ["rfp.docx", "alphasub_bid.pdf"], "vendor_count": 2}])
            self._send(404, {"error": "not found"})

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            body = self._body()
            state.requests.append({"method": "POST", "path": u.path, "query": dict(urllib.parse.parse_qsl(u.query)),
                                   "body": body, "auth": self.headers.get("Authorization"),
                                   "apikey": self.headers.get("apikey")})
            if u.path == "/auth/v1/otp":
                return self._send(200, {})
            if u.path == "/auth/v1/verify":
                if body.get("token") == "123456":
                    return self._send(200, {"access_token": state.token, "refresh_token": "rt-1",
                                            "expires_in": 3600, "user": {"email": body["email"]}})
                return self._send(403, {"msg": "Token has expired or is invalid"})
            if u.path == "/auth/v1/token":
                if state.refresh_status != 200:
                    return self._send(state.refresh_status, {"msg": "upstream busy"})
                return self._send(200, {"access_token": state.refreshed, "refresh_token": "rt-2"})
            if u.path == "/api/evaluate":
                if self.headers.get("Authorization") not in (f"Bearer {state.token}", f"Bearer {state.refreshed}"):
                    return self._send(401, {"error": "Sign in required"})
                if state.evaluate_status == 402:
                    return self._send(402, {"message": "You have used your free evaluation this month."})
                return self._send(200, fx.api_response())
            self._send(404, {"error": "not found"})
    return H


@pytest.fixture()
def mock(tmp_path):
    state = MockState()
    base = [""]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state, base))
    base[0] = f"http://127.0.0.1:{srv.server_port}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = {**os.environ, "GATEKEEPER_URL": base[0], "GATEKEEPER_HOME": str(tmp_path / "home")}
    env.pop("GATEKEEPER_TOKEN", None)
    yield state, base[0], env
    srv.shutdown()


def run(args, env, check=True):
    r = subprocess.run(CLI + args, capture_output=True, text=True, env=env, timeout=120)
    if check and r.returncode != 0:
        raise AssertionError(f"exit {r.returncode}\nstdout={r.stdout}\nstderr={r.stderr}")
    return r


def jrun(args, env, check=True):
    r = run(["--json"] + args, env, check)
    return r, json.loads(r.stdout)


# ---------------------------------------------------------------------------
# Mock-service workflows
# ---------------------------------------------------------------------------

class TestTenderWorkflow:
    """Simulates a buyer evaluating two umbilical bids against an NCS RFP."""

    def test_full_evaluation_pipeline(self, mock, tmp_path):
        state, base, env = mock
        tender = fx.make_tender(tmp_path / "tender")

        # 1. preview extraction
        _, ex = jrun(["extract", str(tender)], env)
        assert ex["ready"] and len(ex["files"]) == 5

        # 2. sign in with the emailed code
        jrun(["auth", "login", "buyer@example.com"], env)
        otp = next(r for r in state.requests if r["path"] == "/auth/v1/otp")
        assert otp["body"]["email"] == "buyer@example.com" and otp["apikey"] == "anon-key"
        assert otp["query"]["redirect_to"] == f"{base}/login?next=/evaluate"
        _, st = jrun(["auth", "complete", "--email", "buyer@example.com", "--code", "123456"], env)
        assert st["signed_in"] and st["refreshable"]
        sess = Path(env["GATEKEEPER_HOME"]) / "session.json"
        assert oct(sess.stat().st_mode)[-3:] == "600"

        # 3. evaluate with custom weights, save the report
        out = tmp_path / "report.json"
        _, data = jrun(["evaluate", str(tender), "-w", "technical=30,pricing=15", "-o", str(out)], env)
        call = next(r for r in state.requests if r["path"] == "/api/evaluate")
        assert call["auth"] == f"Bearer {state.token}"
        assert call["body"]["weights"]["technical"] == 30
        sent = {d["name"]: d["content"] for d in call["body"]["documents"]}
        assert set(sent) == {"rfp.docx", "alphasub_bid.pdf", "betamarine_bid.pdf",
                             "alphasub_bom.xlsx", "clarifications.txt"}
        assert "DNV-ST-F119" in sent["alphasub_bid.pdf"] and sent["alphasub_bom.xlsx"].startswith("[Sheet 1]")
        assert data["evaluation"]["recommendation"]["vendor"] == "AlphaSub"
        assert out.is_file() and out.stat().st_size > 1000
        print(f"\n  Report JSON: {out} ({out.stat().st_size:,} bytes)")

        # 4. offline views on the saved report
        _, s = jrun(["report", "summary", str(out)], env)
        assert s["recommended_vendor"] == "AlphaSub" and s["vendors"][0]["rank"] == 1
        _, c = jrun(["report", "compliance", str(out), "--status", "FAIL", "--mandatory"], env)
        assert {x["vendor"] for x in c["cells"]} == {"BetaMarine"} and c["count"] == 2
        _, p = jrun(["report", "pricing", str(out)], env)
        assert p["discrepancies"][0]["discrepancy"] == 110000
        _, rk = jrun(["report", "risks", str(out)], env)
        assert rk["count"] == 3
        md = tmp_path / "report.md"
        run(["report", "markdown", str(out), "-o", str(md)], env)
        text = md.read_text()
        assert text.startswith("# Procurement Evaluation — Subsea Umbilical Supply")
        assert "| 1 | AlphaSub | 90.75 | PASS |" in text
        print(f"  Markdown: {md} ({md.stat().st_size:,} bytes)")

    def test_default_weights_not_sent(self, mock, tmp_path):
        state, _, env = mock
        env["GATEKEEPER_TOKEN"] = state.token
        tender = fx.make_tender(tmp_path / "t")
        jrun(["evaluate", str(tender), "-w", "technical=25"], env)
        call = next(r for r in state.requests if r["path"] == "/api/evaluate")
        assert "weights" not in call["body"]

    def test_human_output(self, mock, tmp_path):
        state, _, env = mock
        env["GATEKEEPER_TOKEN"] = state.token
        r = run(["evaluate", str(fx.make_tender(tmp_path / "t"))], env)
        assert "Recommended: AlphaSub" in r.stdout and "BetaMarine" in r.stdout
        assert "Evaluating 5 documents" in r.stderr


class TestErrors:
    def test_plan_wall_exit_3(self, mock, tmp_path):
        state, base, env = mock
        state.evaluate_status = 402
        env["GATEKEEPER_TOKEN"] = state.token
        r, d = jrun(["evaluate", str(fx.make_tender(tmp_path / "t"))], env, check=False)
        assert r.returncode == 3 and d["http_status"] == 402 and f"{base}/pricing" in d["error"]

    def test_not_signed_in_exit_2(self, mock, tmp_path):
        _, _, env = mock
        r, d = jrun(["evaluate", str(fx.make_tender(tmp_path / "t"))], env, check=False)
        assert r.returncode == 2 and "auth login" in d["error"]

    def test_bad_token_exit_2(self, mock, tmp_path):
        _, _, env = mock
        env["GATEKEEPER_TOKEN"] = "nope"
        r, _ = jrun(["evaluate", str(fx.make_tender(tmp_path / "t"))], env, check=False)
        assert r.returncode == 2

    def test_bad_weights_exit_1_no_call(self, mock, tmp_path):
        state, _, env = mock
        env["GATEKEEPER_TOKEN"] = state.token
        r, d = jrun(["evaluate", str(fx.make_tender(tmp_path / "t")), "-w", "hse=50"], env, check=False)
        assert r.returncode == 1 and "100" in d["error"]
        assert not any(x["path"] == "/api/evaluate" for x in state.requests)

    def test_wrong_code(self, mock):
        _, _, env = mock
        r, d = jrun(["auth", "complete", "--email", "a@b.no", "--code", "000000"], env, check=False)
        assert r.returncode == 2 and "Code rejected" in d["error"]

    def test_dry_run_sends_nothing(self, mock, tmp_path):
        state, _, env = mock
        _, d = jrun(["evaluate", str(fx.make_tender(tmp_path / "t")), "--dry-run"], env)
        assert d["dry_run"] and d["ready"] and not d["signed_in"]
        assert not any(x["path"] == "/api/evaluate" for x in state.requests)


class TestReviewFixes:
    def test_unhealthy_json_is_one_document(self, mock):
        state, _, env = mock
        state.health_status = 503
        r = run(["--json", "health"], env, check=False)
        assert r.returncode == 1
        d = json.loads(r.stdout)  # raises if two JSON documents were printed
        assert d["ok"] is False and d["http_status"] == 503 and d["exit_code"] == 1 and d["error"]

    def test_transient_refresh_failure_is_retryable_exit_1(self, mock):
        state, _, env = mock
        state.refresh_status = 503
        jrun(["auth", "token", state.token, "--refresh-token", "rt"], env)
        p = Path(env["GATEKEEPER_HOME"]) / "session.json"
        s = json.loads(p.read_text())
        s["expires_at"] = 1
        p.write_text(json.dumps(s))
        r, d = jrun(["reports", "list"], env, check=False)
        assert r.returncode == 1 and d["http_status"] == 503 and "retry" in d["error"]
        assert json.loads(p.read_text())["refresh_token"] == "rt"  # session kept for the retry

    def test_fractional_weight_rejected_before_any_call(self, mock, tmp_path):
        state, _, env = mock
        env["GATEKEEPER_TOKEN"] = state.token
        r, d = jrun(["evaluate", str(fx.make_tender(tmp_path / "t")), "-w", "technical=25.9"], env, check=False)
        assert r.returncode == 1 and "whole percentage" in d["error"]
        assert not any(x["path"] == "/api/evaluate" for x in state.requests)


class TestSessionLifecycle:
    def test_magic_link_and_refresh(self, mock):
        state, base, env = mock
        link = f"{base}/auth/v1/verify?token=abc&type=magiclink&redirect_to={base}/login"
        _, st = jrun(["auth", "complete", "--link", link], env)
        assert st["signed_in"] and st["email"] == "buyer@example.com"
        # Force near-expiry → next authenticated call must refresh first.
        p = Path(env["GATEKEEPER_HOME"]) / "session.json"
        s = json.loads(p.read_text())
        s["expires_at"] = 1
        p.write_text(json.dumps(s))
        jrun(["reports", "list"], env)
        assert any(r["path"] == "/auth/v1/token" and r["body"]["refresh_token"] == "rt-link"
                   for r in state.requests)
        assert json.loads(p.read_text())["access_token"] == state.refreshed

    def test_status_verify_logout(self, mock):
        state, _, env = mock
        jrun(["auth", "token", state.token], env)
        _, st = jrun(["auth", "status", "--verify"], env)
        assert st["verified"] and st["email"] == "buyer@example.com"
        _, lo = jrun(["auth", "logout"], env)
        assert lo["removed_session_file"]
        _, st = jrun(["auth", "status"], env)
        assert not st["signed_in"]


class TestSavedReports:
    def test_list_and_get(self, mock, tmp_path):
        state, _, env = mock
        env["GATEKEEPER_TOKEN"] = state.token
        _, lst = jrun(["reports", "list", "--limit", "5"], env)
        assert lst["reports"][0]["id"] == 7
        q = next(r for r in state.requests if r["path"] == "/rest/v1/evaluations")["query"]
        assert q["user_email"] == "eq.buyer@example.com" and q["status"] == "eq.complete"
        assert q["order"] == "completed_at.desc,id.desc" and q["limit"] == "5"
        out = tmp_path / "saved.json"
        _, got = jrun(["reports", "get", "7", "-o", str(out)], env)
        assert got["evaluationId"] == 7 and out.is_file()
        _, s = jrun(["report", "summary", str(out)], env)       # saved report reloads offline
        assert s["recommended_vendor"] == "AlphaSub"
        r, d = jrun(["reports", "get", "999"], env, check=False)
        assert r.returncode == 1 and "not found" in d["error"]


class TestCLIBasics:
    def test_help_and_version(self):
        assert "evaluate" in run(["--help"], os.environ.copy()).stdout
        assert "1.0.0" in run(["--version"], os.environ.copy()).stdout

    def test_real_excel_blank_styled_cells(self, mock, tmp_path):
        """openpyxl-written workbook with a formatted blank cell keeps columns aligned."""
        openpyxl = pytest.importorskip("openpyxl")
        from openpyxl.styles import Font
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Item", "Discount", "Total"])
        ws.append(["Umbilical", None, 18000000])
        ws["B2"].font = Font(bold=True)  # styled but empty → <c r="B2" s="1"/>
        p = tmp_path / "bom.xlsx"
        wb.save(p)
        _, env = mock[0], mock[2]
        _, d = jrun(["extract", str(p), "--text"], env)
        assert "Umbilical\t\t18000000" in d["documents"][0]["content"]


# ---------------------------------------------------------------------------
# Live production service (no credits spent)
# ---------------------------------------------------------------------------

LIVE = {**os.environ}
LIVE.pop("GATEKEEPER_URL", None)
LIVE.pop("GATEKEEPER_TOKEN", None)


class TestLive:
    def test_live_health(self):
        _, d = jrun(["health"], LIVE)
        assert d["ok"] and d["http_status"] == 200 and d["url"] == "https://www.gatekeeper.blog"
        print(f"\n  Live health: {d['response']}  billing_available={d['billing_available']}")

    def test_live_invalid_token_is_401(self, tmp_path):
        env = {**LIVE, "GATEKEEPER_TOKEN": "invalid.jwt.token", "GATEKEEPER_HOME": str(tmp_path)}
        p = tmp_path / "rfp.txt"
        p.write_text("RFP test — nothing will be evaluated because the token is invalid.")
        r, d = jrun(["evaluate", str(p)], env, check=False)
        assert r.returncode == 2 and d["http_status"] == 401

    def test_live_supabase_auth_reachable(self, tmp_path):
        r, d = jrun(["auth", "login", "not-an-email"], {**LIVE, "GATEKEEPER_HOME": str(tmp_path)}, check=False)
        assert r.returncode == 1 and "email" in d["error"].lower()

    @pytest.mark.skipif(not os.environ.get("GATEKEEPER_LIVE_TOKEN"),
                        reason="set GATEKEEPER_LIVE_TOKEN to run a real (credit-consuming) evaluation")
    def test_live_real_evaluation(self, tmp_path):
        env = {**LIVE, "GATEKEEPER_TOKEN": os.environ["GATEKEEPER_LIVE_TOKEN"], "GATEKEEPER_HOME": str(tmp_path)}
        out = tmp_path / "live.json"
        _, d = jrun(["evaluate", str(fx.make_tender(tmp_path / "t")), "-o", str(out)], env)
        assert d["success"] and len(d["evaluation"]["vendors"]) >= 2
        print(f"\n  Live report: {out} ({out.stat().st_size:,} bytes), model {d.get('model')}")
