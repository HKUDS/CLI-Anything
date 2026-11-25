"""Tests for the library-wide read-only reports (duplicates, audit, export)."""

from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from cli_anything.zotero.core import discovery, library
from cli_anything.zotero.tests._helpers import create_sample_environment
from cli_anything.zotero.tests.test_cli_entrypoint import REPO_ROOT, resolve_cli, uses_module_fallback


def add_item(conn, item_id, key, type_id, fields, creators=(), tags=(), collection_id=None):
    """Insert one regular item with fields, creators and tags into the fixture database."""
    conn.execute("INSERT INTO items VALUES (?, ?, '2026-01-01', '2026-01-02', '2026-01-02', 1, ?, 1, 1)",
                 (item_id, type_id, key))
    for name, value in fields.items():
        row = conn.execute("SELECT fieldID FROM fields WHERE fieldName = ?", (name,)).fetchone()
        field_id = row[0] if row else conn.execute("SELECT COALESCE(MAX(fieldID), 0) + 1 FROM fields").fetchone()[0]
        if not row:
            conn.execute("INSERT INTO fields VALUES (?, ?, 0)", (field_id, name))
        value_id = conn.execute("SELECT COALESCE(MAX(valueID), 0) + 1 FROM itemDataValues").fetchone()[0]
        conn.execute("INSERT INTO itemDataValues VALUES (?, ?)", (value_id, value))
        conn.execute("INSERT INTO itemData VALUES (?, ?, ?)", (item_id, field_id, value_id))
    for order, (first, last) in enumerate(creators):
        creator_id = conn.execute("SELECT COALESCE(MAX(creatorID), 0) + 1 FROM creators").fetchone()[0]
        conn.execute("INSERT INTO creators VALUES (?, ?, ?, 0)", (creator_id, first, last))
        conn.execute("INSERT INTO itemCreators VALUES (?, ?, 1, ?)", (item_id, creator_id, order))
    for tag in tags:
        row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (tag,)).fetchone()
        tag_id = row[0] if row else conn.execute("SELECT COALESCE(MAX(tagID), 0) + 1 FROM tags").fetchone()[0]
        if not row:
            conn.execute("INSERT INTO tags VALUES (?, ?)", (tag_id, tag))
        conn.execute("INSERT INTO itemTags VALUES (?, ?, 0)", (item_id, tag_id))
    if collection_id is not None:
        conn.execute("INSERT INTO collectionItems VALUES (?, ?, 0)", (collection_id, item_id))


TITLE_UNICODE = "Café Étude naïve 中文 — test"
FULL = {"date": "2017", "publicationTitle": "NeurIPS", "abstractNote": "An abstract.", "DOI": "10.5555/3295222.3295349"}


class LibraryReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = create_sample_environment(Path(self.tmp.name))
        conn = sqlite3.connect(self.env["sqlite_path"])
        try:
            conn.execute("INSERT INTO itemTypes VALUES (4, 'book', NULL, 1)")
            conn.execute("INSERT INTO itemTypes VALUES (5, 'preprint', NULL, 1)")
            conn.execute("CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY, dateDeleted TEXT)")
            add_item(conn, 20, "LIBT0020", 1, {"title": "Attention Is All You Need", **FULL},
                     creators=[("Ashish", "Vaswani")], tags=["nlp"], collection_id=1)
            add_item(conn, 21, "LIBT0021", 1,
                     {"title": "attention is all you need.", "date": "2017",
                      "DOI": "https://doi.org/10.5555/3295222.3295349"})
            add_item(conn, 22, "LIBT0022", 5, {"title": "Some Preprint Title Here", "url": "https://arxiv.org/abs/1706.03762v5"})
            add_item(conn, 23, "LIBT0023", 5, {"title": "A Totally Different Title", "extra": "arXiv: 1706.03762"})
            add_item(conn, 24, "LIBT0024", 1, {"title": "Lonely paper title"})
            add_item(conn, 25, "LIBT0025", 1, {"title": "Lonely paper title"})
            conn.execute("INSERT INTO deletedItems VALUES (25, '2026-01-03')")
            add_item(conn, 26, "LIBT0026", 1, {"title": "Intro", **FULL, "DOI": "10.1/a"}, creators=[("A", "B")])
            add_item(conn, 27, "LIBT0027", 1, {"title": "Intro", **FULL, "DOI": "10.1/b"}, creators=[("C", "D")])
            add_item(conn, 34, "LIBT0034", 1, {"title": TITLE_UNICODE, "date": "2021"},
                     creators=[("François", "Müller")])
            add_item(conn, 29, "LIBT0029", 1, {"title": "Part One Of The Series Paper", "DOI": "10.9/a"})
            add_item(conn, 30, "LIBT0030", 1, {"title": "Part One Of The Series Paper", "DOI": "10.9/b"})
            add_item(conn, 31, "LIBT0031", 1, {"title": "Another Shared Long Title", "DOI": "10.9/c"})
            add_item(conn, 32, "LIBT0032", 1, {"title": "Another Shared Long Title"})
            add_item(conn, 33, "LIBT0033", 1, {"title": "=HYPERLINK(" + chr(34) + "http://evil.example" + chr(34) + ",1)",
                                             "extra": "+cmd"}, creators=[("A", "B")], tags=["-x"])
            add_item(conn, 28, "LIBT0028", 4, {"title": "A Complete Book Entry", "date": "2020", "publisher": "MIT Press"},
                     creators=[("Ada", "Lovelace")])
            conn.commit()
        finally:
            conn.close()
        self.runtime = discovery.build_runtime_context(
            backend="sqlite", data_dir=str(self.env["data_dir"]), profile_dir=str(self.env["profile_dir"]),
            executable=str(self.env["executable"]))
        self.records = library.records(self.runtime, {})

    def keys(self):
        return {r["key"] for r in self.records}

    # -- records ------------------------------------------------------------

    def test_records_skip_attachments_notes_and_trash(self):
        self.assertNotIn("ATTACHKEY", self.keys())
        self.assertNotIn("NOTEKEY", self.keys())
        self.assertNotIn("LIBT0025", self.keys())  # trashed
        self.assertIn("LIBT0024", self.keys())

    def test_records_carry_fields_creators_tags_and_collections(self):
        item = next(r for r in self.records if r["key"] == "LIBT0020")
        self.assertEqual(item["fields"]["DOI"], "10.5555/3295222.3295349")
        self.assertEqual(item["creators"][0]["lastName"], "Vaswani")
        self.assertEqual([t["name"] for t in item["tags"]], ["nlp"])
        self.assertEqual(item["collectionKeys"], ["COLLAAAA"])

    def test_records_work_on_a_database_without_trash_table(self):
        conn = sqlite3.connect(self.env["sqlite_path"])
        conn.execute("DROP TABLE deletedItems")
        conn.commit()
        conn.close()
        self.assertIn("LIBT0025", {r["key"] for r in library.records(self.runtime, {})})

    # -- normalizers --------------------------------------------------------

    def test_normalize_doi_variants(self):
        for raw in ("10.1000/ABC", "https://doi.org/10.1000/abc", "http://dx.doi.org/10.1000/abc", "doi: 10.1000/abc"):
            self.assertEqual(library.normalize_doi(raw), "10.1000/abc")
        self.assertEqual(library.normalize_doi("not a doi"), "")
        self.assertEqual(library.normalize_doi(""), "")

    def test_arxiv_id_variants(self):
        cases = [({"url": "https://arxiv.org/abs/1706.03762v5"}, "1706.03762"),
                 ({"url": "https://arxiv.org/pdf/1706.03762"}, "1706.03762"),
                 ({"extra": "arXiv: 2101.00001"}, "2101.00001"),
                 ({"DOI": "10.48550/arXiv.1706.03762"}, "1706.03762"),
                 ({"url": "https://arxiv.org/abs/hep-th/9901001"}, "hep-th/9901001"),
                 ({"url": "https://example.com/paper"}, ""), ({}, "")]
        for fields, expected in cases:
            self.assertEqual(library.arxiv_id(fields), expected, fields)

    def test_short_titles_are_not_comparable(self):
        self.assertEqual(library.normalize_title("Intro"), "")
        self.assertEqual(library.normalize_title("Attention Is All You Need!"), "attention is all you need")

    # -- duplicates ---------------------------------------------------------

    def test_duplicates_group_by_doi_and_title(self):
        report = library.find_duplicates(self.records)
        group = next(g for g in report["groups"] if {i["key"] for i in g["items"]} >= {"LIBT0020", "LIBT0021"})
        self.assertEqual(group["reasons"], ["doi", "title"])

    def test_duplicates_group_by_arxiv_id_across_url_and_extra(self):
        report = library.find_duplicates(self.records)
        group = next(g for g in report["groups"] if "LIBT0022" in {i["key"] for i in g["items"]})
        self.assertEqual({i["key"] for i in group["items"]}, {"LIBT0022", "LIBT0023"})
        self.assertEqual(group["reasons"], ["arxiv"])

    def test_short_titles_and_trashed_items_never_form_groups(self):
        grouped = {i["key"] for g in library.find_duplicates(self.records)["groups"] for i in g["items"]}
        self.assertFalse(grouped & {"LIBT0026", "LIBT0027", "LIBT0024", "LIBT0025"})

    def test_different_dois_are_not_duplicates_however_alike_the_titles(self):
        grouped = {i["key"] for g in library.find_duplicates(self.records)["groups"] for i in g["items"]}
        self.assertFalse(grouped & {"LIBT0029", "LIBT0030"})

    def test_item_without_doi_still_matches_by_title(self):
        report = library.find_duplicates(self.records)
        group = next(g for g in report["groups"] if "LIBT0031" in {i["key"] for i in g["items"]})
        self.assertEqual({i["key"] for i in group["items"]}, {"LIBT0031", "LIBT0032"})
        self.assertEqual(group["reasons"], ["title"])

    def test_duplicates_report_counts(self):
        report = library.find_duplicates(self.records)
        self.assertEqual(report["items_scanned"], len(self.records))
        self.assertEqual(report["group_count"], len(report["groups"]))

    # -- audit --------------------------------------------------------------

    def test_audit_uses_item_type_defaults(self):
        report = library.audit_metadata(self.records)
        item = next(i for i in report["items"] if i["key"] == "LIBT0024")
        self.assertEqual(item["missing"], ["creators", "date", "identifier", "publicationTitle", "abstractNote"])
        keys = {i["key"] for i in report["items"]}
        self.assertNotIn("LIBT0028", keys)  # a complete book
        self.assertNotIn("LIBT0020", keys)  # complete journal article
        self.assertNotIn("LIBT0027", keys)  # complete journal article

    def test_audit_summary_counts_by_field(self):
        report = library.audit_metadata(self.records)
        self.assertEqual(report["incomplete"], len(report["items"]))
        self.assertGreaterEqual(report["missing_by_field"]["creators"], 1)
        counts = list(report["missing_by_field"].values())
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_audit_require_overrides_defaults(self):
        report = library.audit_metadata(self.records, ("publisher",))
        missing = {i["key"]: i["missing"] for i in report["items"]}
        self.assertEqual(missing["LIBT0024"], ["publisher"])
        self.assertNotIn("LIBT0028", missing)

    def test_audit_always_requires_a_title(self):
        item = {"key": "X", "title": "  ", "typeName": "journalArticle", "fields": {}, "creators": [], "tags": []}
        self.assertIn("title", library.audit_metadata([item], ("date",))["items"][0]["missing"])

    # -- snapshot -----------------------------------------------------------

    def test_snapshot_shape(self):
        data = library.snapshot(self.runtime, {})
        self.assertEqual(data["collections"]["COLLAAAA"], "Sample Collection")
        row = next(r for r in data["items"] if r["key"] == "LIBT0020")
        self.assertEqual(row["creators"], ["Vaswani, Ashish"])
        self.assertEqual(row["collections"], ["Sample Collection"])
        self.assertEqual(row["tags"], ["nlp"])
        self.assertEqual(row["publication"], "NeurIPS")
        self.assertEqual(row["DOI"], "10.5555/3295222.3295349")

    def test_csv_defuses_spreadsheet_formulas_but_json_keeps_the_data(self):
        data = library.snapshot(self.runtime, {})
        row = next(r for r in data["items"] if r["key"] == "LIBT0033")
        self.assertTrue(row["title"].startswith("=HYPERLINK("))  # JSON is untouched
        rows = list(csv.DictReader(io.StringIO(library.snapshot_csv(data))))
        cell = next(r for r in rows if r["key"] == "LIBT0033")
        self.assertTrue(cell["title"].startswith("'=HYPERLINK("))
        self.assertEqual((cell["extra"], cell["tags"]), ("'+cmd", "'-x"))
        self.assertEqual(next(r for r in rows if r["key"] == "LIBT0020")["date"], "2017")  # normal cells unchanged

    def test_snapshot_csv_round_trips(self):
        data = library.snapshot(self.runtime, {})
        rows = list(csv.DictReader(io.StringIO(library.snapshot_csv(data))))
        self.assertEqual(tuple(rows[0].keys()), library.CSV_COLUMNS)
        self.assertEqual(len(rows), len(data["items"]))
        self.assertEqual(next(r for r in rows if r["key"] == "LIBT0020")["creators"], "Vaswani, Ashish")


class LibraryCliTests(unittest.TestCase):
    CLI_BASE = resolve_cli()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env_paths = create_sample_environment(Path(self.tmp.name))
        conn = sqlite3.connect(self.env_paths["sqlite_path"])
        try:
            add_item(conn, 34, "LIBT0034", 1, {"title": TITLE_UNICODE, "date": "2021"}, creators=[("François", "Müller")])
            conn.commit()
        finally:
            conn.close()

    def run_cli(self, args):
        env = os.environ.copy()
        if uses_module_fallback(self.CLI_BASE):
            env["PYTHONPATH"] = str(REPO_ROOT / "zotero" / "agent-harness") + os.pathsep + env.get("PYTHONPATH", "")
        env.update({"ZOTERO_PROFILE_DIR": str(self.env_paths["profile_dir"]),
                    "ZOTERO_DATA_DIR": str(self.env_paths["data_dir"]),
                    "ZOTERO_EXECUTABLE": str(self.env_paths["executable"]),
                    "CLI_ANYTHING_ZOTERO_STATE_DIR": str(Path(self.tmp.name) / "state")})
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True, encoding="utf-8", env=env)

    def test_help_lists_library_group(self):
        result = self.run_cli(["--help"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("library", result.stdout)

    def test_duplicates_json(self):
        result = self.run_cli(["--backend", "sqlite", "--json", "library", "duplicates"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("groups", payload)
        self.assertGreaterEqual(payload["items_scanned"], 1)

    def test_audit_json_and_require(self):
        result = self.run_cli(["--backend", "sqlite", "--json", "library", "audit", "--require", "publisher"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload["missing_by_field"]), {"publisher"})

    def test_export_to_a_pipe_is_utf8_not_the_console_codepage(self):
        as_json = json.loads(self.run_cli(["--backend", "sqlite", "library", "export"]).stdout)
        row = next(r for r in as_json["items"] if r["key"] == "LIBT0034")
        self.assertEqual(row["title"], TITLE_UNICODE)
        self.assertEqual(row["creators"], ["Müller, François"])
        out = self.run_cli(["--backend", "sqlite", "library", "export", "--format", "csv"]).stdout
        rows = list(csv.DictReader(io.StringIO(out)))
        self.assertEqual(next(r for r in rows if r["key"] == "LIBT0034")["title"], TITLE_UNICODE)

    def test_export_json_and_csv_to_stdout(self):
        as_json = json.loads(self.run_cli(["--backend", "sqlite", "library", "export"]).stdout)
        self.assertIn("Sample Collection", as_json["collections"].values())
        as_csv = self.run_cli(["--backend", "sqlite", "library", "export", "--format", "csv"]).stdout
        self.assertTrue(as_csv.startswith("key,itemType,title,creators,"))

    def test_export_refuses_to_write_inside_the_zotero_data_dir_even_with_force(self):
        inside = self.env_paths["data_dir"] / "snapshot.json"
        result = self.run_cli(["--backend", "sqlite", "library", "export", "--output", str(inside), "--force"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("data directory", result.stderr)
        self.assertFalse(inside.exists())

    def test_export_output_file_refuses_overwrite_without_force(self):
        target = Path(self.tmp.name) / "snapshot.json"
        first = self.run_cli(["--backend", "sqlite", "--json", "library", "export", "--output", str(target)])
        self.assertEqual(first.returncode, 0, msg=first.stderr)
        self.assertEqual(json.loads(first.stdout)["written"], str(target))
        self.assertTrue(json.loads(target.read_text(encoding="utf-8"))["items"])
        again = self.run_cli(["--backend", "sqlite", "library", "export", "--output", str(target)])
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("--force", again.stderr)
        forced = self.run_cli(["--backend", "sqlite", "library", "export", "--output", str(target), "--force"])
        self.assertEqual(forced.returncode, 0, msg=forced.stderr)


if __name__ == "__main__":
    unittest.main()
