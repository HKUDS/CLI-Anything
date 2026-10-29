"""Unit tests — no network."""

from __future__ import annotations

import json
import os
import stat
import time

import pytest

from cli_anything.gatekeeper.core import evaluate, extract, report, session
from cli_anything.gatekeeper.tests import fixtures as fx
from cli_anything.gatekeeper.utils import gk_backend as gk


@pytest.fixture()
def tender(tmp_path):
    return fx.make_tender(tmp_path / "tender")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("GATEKEEPER_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("GATEKEEPER_TOKEN", raising=False)


# ---------------------------------------------------------------- extract

class TestExtract:
    def test_docx_paragraphs_and_tabs(self, tender):
        e = extract.extract_file(tender / "rfp.docx")
        assert "REQ-001\tDNV-ST-F119 certification\tMandatory\n" in e["content"]
        assert e["content"].startswith("RFP NCS-2026-114")
        assert e["warn"] == ""

    def test_xlsx_layout_matches_web(self, tender):
        c = extract.extract_file(tender / "alphasub_bom.xlsx")["content"]
        assert c.startswith("[Sheet 1]\nItem\tQty\tTotal NOK\n")
        assert "Umbilical 12 km\t1\t18000000\n" in c
        assert "Terminations & testing\t2\t3400000\n" in c   # entity decoded
        assert "Grand total\t\t21400000\n" in c              # inline string + empty cell
        assert "[Sheet 2]\nNotes\n" in c

    def test_pdf_text(self, tender):
        e = extract.extract_file(tender / "alphasub_bid.pdf")
        assert "DNV-ST-F119" in e["content"] and e["pages"] == 1
        assert e["warn"] == ""

    def test_txt(self, tender):
        assert "BetaMarine" in extract.extract_file(tender / "clarifications.txt")["content"]

    def test_scanned_pdf_warning(self, tmp_path):
        p = fx.make_pdf(tmp_path / "scan.pdf", ["x"])
        assert "scanned PDF" in extract.extract_file(p)["warn"]

    def test_rejects_wrong_type(self, tmp_path):
        p = tmp_path / "a.png"
        p.write_bytes(b"x")
        with pytest.raises(extract.ExtractError, match="use PDF"):
            extract.extract_file(p)

    def test_rejects_large_file(self, tmp_path):
        p = tmp_path / "big.txt"
        p.write_bytes(b"a" * (extract.MAX_BYTES + 1))
        with pytest.raises(extract.ExtractError, match="10MB"):
            extract.extract_file(p)

    def test_missing_file(self, tmp_path):
        with pytest.raises(extract.ExtractError, match="not found"):
            extract.extract_file(tmp_path / "nope.pdf")

    def test_corrupt_docx_becomes_warning(self, tmp_path):
        p = tmp_path / "bad.docx"
        p.write_bytes(b"not a zip")
        e = extract.extract_file(p)
        assert e["content"] == "" and "not a Word document" in e["warn"]

    def test_empty_txt_warns(self, tmp_path):
        p = tmp_path / "e.txt"
        p.write_text("  ")
        assert "No text" in extract.extract_file(p)["warn"]

    def test_folder_expansion_skips_unaccepted(self, tender):
        names = [os.path.basename(f) for f in extract.collect([str(tender)])]
        assert names == sorted(names) and "ignored.png" not in names and len(names) == 5

    def test_max_files(self, tmp_path):
        for i in range(11):
            (tmp_path / f"{i}.txt").write_text("x")
        with pytest.raises(extract.ExtractError, match="Up to 10"):
            extract.extract_many([str(tmp_path)])

    def test_no_inputs(self, tmp_path):
        with pytest.raises(extract.ExtractError, match="No input"):
            extract.extract_many([str(tmp_path)])

    def test_summarize_has_no_text(self, tender):
        s = extract.summarize(extract.extract_many([str(tender)]))
        assert s["ready"] and s["total_chars"] > 300
        assert all("content" not in f for f in s["files"])


# ---------------------------------------------------------------- weights / payload

class TestWeights:
    def test_none(self):
        assert evaluate.parse_weights(None) is None

    def test_defaults_return_none(self):
        assert evaluate.parse_weights("technical=25") is None

    def test_custom(self):
        w = evaluate.parse_weights("technical=30,pricing=15")
        assert w["technical"] == 30 and w["pricing"] == 15 and sum(w.values()) == 100

    def test_sum_must_be_100(self):
        with pytest.raises(ValueError, match="add up to 100"):
            evaluate.parse_weights("technical=40")

    def test_unknown_criterion(self):
        with pytest.raises(ValueError, match="Unknown criterion"):
            evaluate.parse_weights("price=20")

    def test_bad_number_and_range(self):
        with pytest.raises(ValueError):
            evaluate.parse_weights("technical=abc")
        with pytest.raises(ValueError):
            evaluate.parse_weights("technical=120")

    def test_payload_rejects_unreadable(self):
        with pytest.raises(extract.ExtractError, match="no readable text"):
            evaluate.build_payload([{"name": "a.pdf", "content": " "}])

    def test_payload_shape(self, tender):
        p = evaluate.build_payload(extract.extract_many([str(tender)]))
        assert all(set(d) == {"name", "content"} for d in p)


# ---------------------------------------------------------------- session

class TestSession:
    def test_jwt_claims(self):
        assert session.jwt_claims(fx.make_jwt("a@b.no"))["email"] == "a@b.no"
        assert session.jwt_claims("garbage") == {}

    def test_save_load_permissions(self):
        s = session.save({"access_token": fx.make_jwt(), "refresh_token": "r1"})
        assert s["email"] == "buyer@example.com" and s["expires_at"] > time.time()
        mode = stat.S_IMODE(os.stat(session.session_path()).st_mode)
        assert mode == 0o600
        assert session.load()["refresh_token"] == "r1"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("GATEKEEPER_TOKEN", "envtok")
        assert session.get_token() == "envtok"

    def test_not_signed_in(self):
        with pytest.raises(gk.GatekeeperError) as ei:
            session.get_token()
        assert ei.value.status == 401

    def test_refresh_near_expiry(self, monkeypatch):
        session.save({"access_token": fx.make_jwt(exp_in=30), "refresh_token": "r1"})
        new = fx.make_jwt(exp_in=3600)
        monkeypatch.setattr(gk, "refresh_session", lambda rt: {"access_token": new, "refresh_token": "r2"})
        assert session.get_token() == new
        assert session.load()["refresh_token"] == "r2"

    def test_expired_without_refresh(self):
        session.save({"access_token": fx.make_jwt(exp_in=10)})
        with pytest.raises(gk.GatekeeperError, match="expired"):
            session.get_token()

    def test_corrupt_session_file(self):
        session.session_path().write_text("{oops")
        assert session.load() is None

    def test_clear(self):
        session.save({"access_token": fx.make_jwt()})
        assert session.clear() and not session.clear()


# ---------------------------------------------------------------- magic link parsing

def test_fragment_tokens():
    url = "https://www.gatekeeper.blog/login?next=/evaluate#access_token=AT&refresh_token=RT&expires_at=123&type=magiclink"
    t = gk.resolve_magic_link(url)
    assert t == {"access_token": "AT", "refresh_token": "RT", "expires_at": 123}


# ---------------------------------------------------------------- report views

@pytest.fixture()
def report_file(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps(fx.api_response()))
    return p


class TestReport:
    def test_load_shapes(self, tmp_path, report_file):
        ev, meta = report.load(str(report_file))
        assert meta["model"] == "claude-opus-5" and ev["project"]["buyer"]
        raw = tmp_path / "raw.json"
        raw.write_text(json.dumps(fx.SAMPLE_EVALUATION))
        assert report.load(str(raw))[0]["vendors"]
        row = tmp_path / "row.json"
        row.write_text(json.dumps({"result": fx.SAMPLE_EVALUATION, "model": "m"}))
        assert report.load(str(row))[1]["model"] == "m"
        bad = tmp_path / "bad.json"
        bad.write_text("{}")
        with pytest.raises(ValueError):
            report.load(str(bad))

    def test_summary_sorted_and_counts(self):
        s = report.summary(fx.SAMPLE_EVALUATION)
        assert [v["name"] for v in s["vendors"]] == ["AlphaSub", "BetaMarine"]
        assert s["recommended_vendor"] == "AlphaSub"
        assert s["counts"] == {"vendors": 2, "requirements": 3, "mandatory_fail_cells": 2,
                               "risk_flags": 2, "pricing_rows": 2}

    def test_compliance_filters(self):
        assert report.compliance(fx.SAMPLE_EVALUATION)["count"] == 6
        f = report.compliance(fx.SAMPLE_EVALUATION, status="fail", mandatory_only=True)
        assert {c["id"] for c in f["cells"]} == {"REQ-001", "REQ-002"}
        assert report.compliance(fx.SAMPLE_EVALUATION, vendor="alpha")["count"] == 3

    def test_pricing_discrepancies(self):
        p = report.pricing(fx.SAMPLE_EVALUATION)
        assert [d["vendor"] for d in p["discrepancies"]] == ["BetaMarine"]

    def test_risks_include_missing_docs(self):
        r = report.risks(fx.SAMPLE_EVALUATION)["risks"]
        assert any("Missing document" in x["flag"] for x in r) and len(r) == 3

    def test_markdown(self):
        md = report.to_markdown(fx.SAMPLE_EVALUATION, {"model": "claude-opus-5", "plan": "professional"})
        assert "| 1 | AlphaSub | 90.75 | PASS | 21,400,000 |" in md
        assert "## Compliance matrix" in md and "| REQ-001 | DNV-ST-F119 certification | M | PASS | FAIL |" in md
        assert "110,000" in md and "_Model: claude-opus-5" in md

    def test_empty_report(self):
        md = report.to_markdown({"vendors": []})
        assert "No award recommended" in md


# ---------------------------------------------------------------- review fixes (PR #633)

def _xlsx(tmp_path, sheets: dict[str, str], shared=("Item", "Qty", "Total")):
    import zipfile
    p = tmp_path / "w.xlsx"
    ss = "<sst>" + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("xl/sharedStrings.xml", ss)
        for name, rows in sheets.items():
            z.writestr(f"xl/worksheets/{name}.xml", f"<worksheet><sheetData>{rows}</sheetData></worksheet>")
    return p


class TestXlsxCellReferences:
    def test_omitted_blank_cell_keeps_column(self, tmp_path):
        # A2 and C2 present, B2 omitted entirely (unformatted blank in OOXML).
        rows = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>'
                '<row r="2"><c r="A2" t="inlineStr"><is><t>Umbilical</t></is></c><c r="C2"><v>18000000</v></c></row>')
        c = extract.extract_xlsx(_xlsx(tmp_path, {"sheet1": rows}))
        assert "Item\tQty\tTotal\nUmbilical\t\t18000000\n" in c

    def test_leading_gap_and_self_closing(self, tmp_path):
        rows = '<row r="3"><c r="B3" s="1"/><c r="D3"><v>7</v></c></row>'
        assert extract.extract_xlsx(_xlsx(tmp_path, {"sheet1": rows})).endswith("\t\t\t7\n")

    def test_multi_letter_columns(self, tmp_path):
        rows = '<row r="1"><c r="A1"><v>1</v></c><c r="AA1"><v>2</v></c></row>'
        line = extract.extract_xlsx(_xlsx(tmp_path, {"sheet1": rows})).splitlines()[1]
        assert line.split("\t") == ["1"] + [""] * 25 + ["2"]

    def test_cells_without_reference_are_sequential(self, tmp_path):
        rows = '<row><c><v>1</v></c><c><v>2</v></c></row>'
        assert "1\t2\n" in extract.extract_xlsx(_xlsx(tmp_path, {"sheet1": rows}))

    def test_out_of_order_reference_does_not_overwrite(self, tmp_path):
        rows = '<row r="1"><c r="B1"><v>1</v></c><c r="A1"><v>2</v></c></row>'
        assert extract.extract_xlsx(_xlsx(tmp_path, {"sheet1": rows})).splitlines()[1] == "\t1\t2"

    def test_sheets_in_numeric_order(self, tmp_path):
        sheets = {f"sheet{i}": f'<row><c t="inlineStr"><is><t>s{i}</t></is></c></row>' for i in (1, 2, 10)}
        c = extract.extract_xlsx(_xlsx(tmp_path, sheets))
        assert c.index("[Sheet 2]") < c.index("[Sheet 10]")


class TestFractionalWeights:
    def test_fraction_rejected(self):
        with pytest.raises(ValueError, match="whole percentage"):
            evaluate.parse_weights("technical=25.9")

    def test_fraction_cannot_sneak_total_to_100(self):
        with pytest.raises(ValueError, match="whole percentage"):
            evaluate.parse_weights("technical=25.9,pricing=19.1")

    def test_integer_valued_float_accepted(self):
        assert evaluate.parse_weights("technical=25.0") is None
        assert evaluate.parse_weights("technical=30.0,pricing=15")["technical"] == 30


class TestRefreshErrorMapping:
    def _patch(self, monkeypatch, status, body):
        monkeypatch.setattr(gk, "get_config", lambda: {"supabaseUrl": "https://sb", "supabaseAnonKey": "k"})
        monkeypatch.setattr(gk, "_request", lambda *a, **k: (status, body, {}))

    @pytest.mark.parametrize("status", [400, 401, 403])
    def test_auth_rejection_is_401(self, monkeypatch, status):
        self._patch(monkeypatch, status, {"error_description": "Invalid Refresh Token"})
        with pytest.raises(gk.GatekeeperError) as ei:
            gk.refresh_session("rt")
        assert ei.value.status == 401 and "auth login" in str(ei.value)

    @pytest.mark.parametrize("status", [429, 500, 503])
    def test_transient_failure_keeps_status(self, monkeypatch, status):
        self._patch(monkeypatch, status, {"msg": "busy"})
        with pytest.raises(gk.GatekeeperError) as ei:
            gk.refresh_session("rt")
        assert ei.value.status == status and "retry" in str(ei.value)

    def test_malformed_success_is_not_auth(self, monkeypatch):
        self._patch(monkeypatch, 200, {"unexpected": True})
        with pytest.raises(gk.GatekeeperError) as ei:
            gk.refresh_session("rt")
        assert ei.value.status == 502


class TestSessionConcurrency:
    def test_reader_never_sees_partial_file(self):
        import threading
        session.save({"access_token": fx.make_jwt(), "refresh_token": "r0"})
        stop, misses = threading.Event(), []

        def writer():
            i = 0
            while not stop.is_set():
                session.save({"access_token": fx.make_jwt(), "refresh_token": f"r{i}" * 200})
                i += 1

        t = threading.Thread(target=writer)
        t.start()
        try:
            for _ in range(3000):
                if session.load() is None:
                    misses.append(1)
        finally:
            stop.set()
            t.join()
        assert not misses
        assert not list(session.home().glob(".session-*"))  # no temp files left behind

    def test_concurrent_refresh_spends_token_once(self, monkeypatch):
        import threading
        session.save({"access_token": fx.make_jwt(exp_in=30), "refresh_token": "r1"})
        calls, new = [], fx.make_jwt(exp_in=3600)

        def refresh(rt):
            calls.append(rt)
            time.sleep(0.2)
            return {"access_token": new, "refresh_token": "r2"}

        monkeypatch.setattr(gk, "refresh_session", refresh)
        out = []
        threads = [threading.Thread(target=lambda: out.append(session.get_token())) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert calls == ["r1"] and out == [new] * 4

    def test_session_file_mode_after_atomic_write(self):
        import stat as _stat
        session.save({"access_token": fx.make_jwt()})
        session.save({"access_token": fx.make_jwt()})
        assert _stat.S_IMODE(os.stat(session.session_path()).st_mode) == 0o600
