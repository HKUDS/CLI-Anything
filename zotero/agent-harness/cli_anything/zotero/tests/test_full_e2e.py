from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
import uuid
from pathlib import Path

from cli_anything.zotero.core import discovery
from cli_anything.zotero.tests._helpers import sample_pdf_bytes
from cli_anything.zotero.utils import zotero_paths, zotero_sqlite


REPO_ROOT = Path(__file__).resolve().parents[4]


def resolve_cli() -> list[str]:
    force_installed = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    installed = shutil.which("cli-anything-zotero")
    if installed:
        return [installed]
    scripts_dir = Path(sysconfig.get_path("scripts"))
    for candidate in (scripts_dir / "cli-anything-zotero.exe", scripts_dir / "cli-anything-zotero"):
        if candidate.exists():
            return [str(candidate)]
    if force_installed:
        raise RuntimeError("cli-anything-zotero not found in PATH. Install it with: py -m pip install -e .")
    return [sys.executable, "-m", "cli_anything.zotero"]


def uses_module_fallback(cli_base: list[str]) -> bool:
    return len(cli_base) >= 3 and cli_base[1] == "-m"


ENVIRONMENT = zotero_paths.build_environment()
HAS_LOCAL_DATA = ENVIRONMENT.sqlite_exists


def choose_regular_item() -> dict | None:
    if not HAS_LOCAL_DATA:
        return None
    items = zotero_sqlite.fetch_items(ENVIRONMENT.sqlite_path, library_id=zotero_sqlite.default_library_id(ENVIRONMENT.sqlite_path), limit=50)
    for item in items:
        if item["typeName"] not in {"attachment", "note"} and item.get("title"):
            return item
    return None


def choose_item_with_attachment() -> dict | None:
    if not HAS_LOCAL_DATA:
        return None
    library_id = zotero_sqlite.default_library_id(ENVIRONMENT.sqlite_path)
    items = zotero_sqlite.fetch_items(ENVIRONMENT.sqlite_path, library_id=library_id, limit=100)
    for item in items:
        if item["typeName"] in {"attachment", "note", "annotation"}:
            continue
        attachments = zotero_sqlite.fetch_item_attachments(ENVIRONMENT.sqlite_path, item["itemID"])
        if attachments:
            return item
    return None


def choose_item_with_note() -> dict | None:
    if not HAS_LOCAL_DATA:
        return None
    library_id = zotero_sqlite.default_library_id(ENVIRONMENT.sqlite_path)
    items = zotero_sqlite.fetch_items(ENVIRONMENT.sqlite_path, library_id=library_id, limit=100)
    for item in items:
        if item["typeName"] in {"attachment", "note", "annotation"}:
            continue
        notes = zotero_sqlite.fetch_item_notes(ENVIRONMENT.sqlite_path, item["itemID"])
        if notes:
            return item
    return None


SAMPLE_ITEM = choose_regular_item()
ATTACHMENT_SAMPLE_ITEM = choose_item_with_attachment()
NOTE_SAMPLE_ITEM = choose_item_with_note()


def choose_collection() -> dict | None:
    if not HAS_LOCAL_DATA:
        return None
    collections = zotero_sqlite.fetch_collections(ENVIRONMENT.sqlite_path, library_id=zotero_sqlite.default_library_id(ENVIRONMENT.sqlite_path))
    return collections[0] if collections else None


def choose_tag_name() -> str | None:
    if not HAS_LOCAL_DATA:
        return None
    tags = zotero_sqlite.fetch_tags(ENVIRONMENT.sqlite_path, library_id=zotero_sqlite.default_library_id(ENVIRONMENT.sqlite_path))
    return tags[0]["name"] if tags else None


SAMPLE_COLLECTION = choose_collection()
SAMPLE_TAG = choose_tag_name()
SEARCHES = zotero_sqlite.fetch_saved_searches(ENVIRONMENT.sqlite_path, library_id=zotero_sqlite.default_library_id(ENVIRONMENT.sqlite_path)) if HAS_LOCAL_DATA else []
SAMPLE_SEARCH = SEARCHES[0] if SEARCHES else None


@unittest.skipUnless(HAS_LOCAL_DATA, "Local Zotero data directory not found")
class ZoteroFullE2E(unittest.TestCase):
    CLI_BASE = resolve_cli()

    @classmethod
    def setUpClass(cls) -> None:
        discovery.ensure_live_api_enabled()
        runtime = discovery.build_runtime_context()
        if not runtime.connector_available:
            discovery.launch_zotero(runtime, wait_timeout=45)
        cls.runtime = discovery.build_runtime_context()

    def run_cli(self, args):
        env = os.environ.copy()
        if uses_module_fallback(self.CLI_BASE):
            env["PYTHONPATH"] = str(REPO_ROOT / "zotero" / "agent-harness") + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(self.CLI_BASE + args, capture_output=True, text=True, env=env, timeout=60)

    def run_cli_with_retry(self, args, retries: int = 2):
        last = None
        for _ in range(retries):
            last = self.run_cli(args)
            if last.returncode == 0:
                return last
        return last

    def test_sqlite_inventory_commands(self):
        result = self.run_cli(["--json", "collection", "list"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("collectionName", result.stdout)

        result = self.run_cli(["--json", "item", "list"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("itemID", result.stdout)

        result = self.run_cli(["--json", "style", "list"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("title", result.stdout)

        result = self.run_cli(["--json", "search", "list"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    @unittest.skipUnless(SAMPLE_ITEM is not None, "No regular Zotero item found")
    def test_item_find_and_context_commands(self):
        assert SAMPLE_ITEM is not None
        title = zotero_sqlite.resolve_item(ENVIRONMENT.sqlite_path, SAMPLE_ITEM["itemID"])["title"]
        query = title.split()[0]

        item_find = self.run_cli(["--json", "item", "find", query, "--limit", "5"])
        self.assertEqual(item_find.returncode, 0, msg=item_find.stderr)
        self.assertIn(SAMPLE_ITEM["key"], item_find.stdout)

        exact_find = self.run_cli(["--json", "item", "find", title, "--exact-title"])
        self.assertEqual(exact_find.returncode, 0, msg=exact_find.stderr)
        self.assertIn(SAMPLE_ITEM["key"], exact_find.stdout)

        context_result = self.run_cli(["--json", "item", "context", str(SAMPLE_ITEM["itemID"]), "--include-links"])
        self.assertEqual(context_result.returncode, 0, msg=context_result.stderr)
        self.assertIn('"prompt_context"', context_result.stdout)

    @unittest.skipUnless(ATTACHMENT_SAMPLE_ITEM is not None, "No Zotero item with attachments found")
    def test_attachment_inventory_commands(self):
        assert ATTACHMENT_SAMPLE_ITEM is not None
        attachments = self.run_cli(["--json", "item", "attachments", str(ATTACHMENT_SAMPLE_ITEM["itemID"])])
        self.assertEqual(attachments.returncode, 0, msg=attachments.stderr)
        attachment_data = json.loads(attachments.stdout)
        self.assertTrue(attachment_data)
        self.assertTrue(attachment_data[0].get("resolvedPath"))

        item_file = self.run_cli(["--json", "item", "file", str(ATTACHMENT_SAMPLE_ITEM["itemID"])])
        self.assertEqual(item_file.returncode, 0, msg=item_file.stderr)
        item_file_data = json.loads(item_file.stdout)
        self.assertTrue(item_file_data.get("exists"))
        self.assertTrue(item_file_data.get("resolvedPath"))

    @unittest.skipUnless(NOTE_SAMPLE_ITEM is not None, "No Zotero item with notes found")
    def test_note_inventory_commands(self):
        assert NOTE_SAMPLE_ITEM is not None
        item_notes = self.run_cli(["--json", "item", "notes", str(NOTE_SAMPLE_ITEM["itemID"])])
        self.assertEqual(item_notes.returncode, 0, msg=item_notes.stderr)
        item_notes_data = json.loads(item_notes.stdout)
        self.assertTrue(item_notes_data)
        note_key = item_notes_data[0]["key"]

        note_get = self.run_cli(["--json", "note", "get", note_key])
        self.assertEqual(note_get.returncode, 0, msg=note_get.stderr)
        self.assertIn(note_key, note_get.stdout)

    def test_connector_ping(self):
        result = self.run_cli(["--json", "app", "ping"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('"connector_available": true', result.stdout)

    def test_collection_use_selected(self):
        result = self.run_cli(["--json", "collection", "use-selected"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("libraryID", result.stdout)

    @unittest.skipUnless(SAMPLE_COLLECTION is not None, "No Zotero collection found")
    def test_collection_detail_commands(self):
        collection_key = SAMPLE_COLLECTION["key"]

        tree = self.run_cli(["--json", "collection", "tree"])
        self.assertEqual(tree.returncode, 0, msg=tree.stderr)
        self.assertIn("children", tree.stdout)

        collection_get = self.run_cli(["--json", "collection", "get", collection_key])
        self.assertEqual(collection_get.returncode, 0, msg=collection_get.stderr)
        self.assertIn(collection_key, collection_get.stdout)

        collection_items = self.run_cli(["--json", "collection", "items", collection_key])
        self.assertEqual(collection_items.returncode, 0, msg=collection_items.stderr)

    @unittest.skipUnless(SAMPLE_TAG is not None, "No Zotero tag found")
    def test_tag_and_session_commands(self):
        tag_items = self.run_cli(["--json", "tag", "items", SAMPLE_TAG])
        self.assertEqual(tag_items.returncode, 0, msg=tag_items.stderr)
        self.assertIn("itemID", tag_items.stdout)

        if SAMPLE_COLLECTION is not None:
            session_collection = self.run_cli(["--json", "session", "use-collection", SAMPLE_COLLECTION["key"]])
            self.assertEqual(session_collection.returncode, 0, msg=session_collection.stderr)
            self.assertIn('"current_collection"', session_collection.stdout)

        if SAMPLE_ITEM is not None:
            session_item = self.run_cli(["--json", "session", "use-item", str(SAMPLE_ITEM["itemID"])])
            self.assertEqual(session_item.returncode, 0, msg=session_item.stderr)
            self.assertIn(f'"current_item": "{SAMPLE_ITEM["itemID"]}"', session_item.stdout)

    @unittest.skipUnless(SAMPLE_SEARCH is not None, "No Zotero saved search found")
    def test_search_detail_commands(self):
        assert SAMPLE_SEARCH is not None
        search_get = self.run_cli(["--json", "search", "get", str(SAMPLE_SEARCH["savedSearchID"])])
        self.assertEqual(search_get.returncode, 0, msg=search_get.stderr)
        self.assertIn(SAMPLE_SEARCH["key"], search_get.stdout)

        search_items = self.run_cli(["--json", "search", "items", str(SAMPLE_SEARCH["savedSearchID"])])
        self.assertEqual(search_items.returncode, 0, msg=search_items.stderr)

    @unittest.skipUnless(os.environ.get("CLI_ANYTHING_ZOTERO_ENABLE_WRITE_E2E") == "1", "Write E2E disabled")
    def test_opt_in_write_import_commands(self):
        target = os.environ.get("CLI_ANYTHING_ZOTERO_IMPORT_TARGET", "").strip()
        self.assertTrue(target, "CLI_ANYTHING_ZOTERO_IMPORT_TARGET must be set when write E2E is enabled")

        with tempfile.TemporaryDirectory() as tmpdir:
            ris_path = Path(tmpdir) / "import.ris"
            ris_path.write_text("TY  - JOUR\nTI  - CLI Anything Write E2E RIS\nER  - \n", encoding="utf-8")
            ris_result = self.run_cli(["--json", "import", "file", str(ris_path), "--collection", target, "--tag", "cli-anything-e2e"])
            self.assertEqual(ris_result.returncode, 0, msg=ris_result.stderr)
            self.assertIn('"action": "import_file"', ris_result.stdout)

            json_path = Path(tmpdir) / "import.json"
            json_path.write_text(
                json.dumps([{"itemType": "journalArticle", "title": "CLI Anything Write E2E JSON"}], ensure_ascii=False),
                encoding="utf-8",
            )
            json_result = self.run_cli(["--json", "import", "json", str(json_path), "--collection", target, "--tag", "cli-anything-e2e"])
            self.assertEqual(json_result.returncode, 0, msg=json_result.stderr)
            self.assertIn('"action": "import_json"', json_result.stdout)

    @unittest.skipUnless(os.environ.get("CLI_ANYTHING_ZOTERO_ENABLE_WRITE_E2E") == "1", "Write E2E disabled")
    def test_opt_in_import_json_with_inline_attachment(self):
        target = os.environ.get("CLI_ANYTHING_ZOTERO_IMPORT_TARGET", "").strip()
        self.assertTrue(target, "CLI_ANYTHING_ZOTERO_IMPORT_TARGET must be set when write E2E is enabled")

        with tempfile.TemporaryDirectory() as tmpdir:
            title = f"CLI Anything Attachment E2E {uuid.uuid4().hex[:8]}"
            pdf_path = Path(tmpdir) / "inline-e2e.pdf"
            pdf_path.write_bytes(sample_pdf_bytes("live-e2e"))
            json_path = Path(tmpdir) / "import-attachment.json"
            json_path.write_text(
                json.dumps(
                    [
                        {
                            "itemType": "journalArticle",
                            "title": title,
                            "attachments": [{"path": str(pdf_path)}],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            import_result = self.run_cli(
                ["--json", "import", "json", str(json_path), "--collection", target, "--tag", "cli-anything-e2e"]
            )
            self.assertEqual(import_result.returncode, 0, msg=import_result.stderr)
            self.assertIn('"created_count": 1', import_result.stdout)

            find_result = self.run_cli_with_retry(["--json", "item", "find", title, "--exact-title"], retries=4)
            self.assertEqual(find_result.returncode, 0, msg=find_result.stderr)
            imported_items = json.loads(find_result.stdout)
            self.assertTrue(imported_items)
            imported_item_id = str(imported_items[0]["itemID"])

            attachments_result = self.run_cli_with_retry(["--json", "item", "attachments", imported_item_id], retries=4)
            self.assertEqual(attachments_result.returncode, 0, msg=attachments_result.stderr)
            attachments = json.loads(attachments_result.stdout)
            self.assertTrue(attachments)
            self.assertTrue(any((attachment.get("resolvedPath") or "").lower().endswith(".pdf") for attachment in attachments))

            item_file_result = self.run_cli_with_retry(["--json", "item", "file", imported_item_id], retries=4)
            self.assertEqual(item_file_result.returncode, 0, msg=item_file_result.stderr)
            item_file = json.loads(item_file_result.stdout)
            self.assertTrue(item_file.get("exists"))
            self.assertTrue((item_file.get("resolvedPath") or "").lower().endswith(".pdf"))

    @unittest.skipUnless(os.environ.get("CLI_ANYTHING_ZOTERO_ENABLE_WRITE_E2E") == "1", "Write E2E disabled")
    @unittest.skipUnless(SAMPLE_ITEM is not None, "No regular Zotero item found")
    def test_opt_in_note_add_command(self):
        assert SAMPLE_ITEM is not None
        result = self.run_cli(["--json", "note", "add", str(SAMPLE_ITEM["itemID"]), "--text", "CLI Anything write note"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn('"action": "note_add"', result.stdout)

    @unittest.skipUnless(SAMPLE_ITEM is not None, "No regular Zotero item found for export/citation tests")
    def test_item_citation_bibliography_and_exports(self):
        assert SAMPLE_ITEM is not None
        item_ref = str(SAMPLE_ITEM["itemID"])
        citation = self.run_cli_with_retry(["--json", "item", "citation", item_ref, "--style", "apa", "--locale", "en-US"])
        self.assertEqual(citation.returncode, 0, msg=citation.stderr)
        citation_data = json.loads(citation.stdout)
        self.assertTrue(citation_data.get("citation"))

        bibliography = self.run_cli_with_retry(["--json", "item", "bibliography", item_ref, "--style", "apa", "--locale", "en-US"])
        self.assertEqual(bibliography.returncode, 0, msg=bibliography.stderr)
        bibliography_data = json.loads(bibliography.stdout)
        self.assertTrue(bibliography_data.get("bibliography"))

        ris = self.run_cli_with_retry(["--json", "item", "export", item_ref, "--format", "ris"])
        self.assertEqual(ris.returncode, 0, msg=ris.stderr)
        ris_data = json.loads(ris.stdout)
        self.assertIn("TY  -", ris_data["content"])

        bibtex = self.run_cli_with_retry(["--json", "item", "export", item_ref, "--format", "bibtex"])
        self.assertEqual(bibtex.returncode, 0, msg=bibtex.stderr)
        bibtex_data = json.loads(bibtex.stdout)
        self.assertIn("@", bibtex_data["content"])

        csljson = self.run_cli_with_retry(["--json", "item", "export", item_ref, "--format", "csljson"])
        self.assertEqual(csljson.returncode, 0, msg=csljson.stderr)
        csljson_data = json.loads(csljson.stdout)
        parsed = json.loads(csljson_data["content"])
        self.assertTrue(parsed)
