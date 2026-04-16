from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cli_anything.zotero.core import analysis, catalog, discovery, experimental, imports as imports_mod, notes as notes_mod, rendering, session as session_mod
from cli_anything.zotero.tests._helpers import create_sample_environment, fake_zotero_http_server, sample_pdf_bytes
from cli_anything.zotero.utils import openai_api, zotero_http, zotero_paths, zotero_sqlite


class PathDiscoveryTests(unittest.TestCase):
    def test_build_environment_uses_active_profile_and_data_dir_pref(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = create_sample_environment(Path(tmpdir))
            runtime_env = zotero_paths.build_environment(
                explicit_profile_dir=str(env["profile_root"]),
                explicit_executable=str(env["executable"]),
            )
            self.assertEqual(runtime_env.profile_dir, env["profile_dir"])
            self.assertEqual(runtime_env.data_dir, env["data_dir"])
            self.assertEqual(runtime_env.sqlite_path, env["sqlite_path"])
            self.assertEqual(runtime_env.version, "7.0.32")

    def test_build_environment_accepts_env_profile_dir_pointing_to_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = create_sample_environment(Path(tmpdir))
            with mock.patch.dict("os.environ", {"ZOTERO_PROFILE_DIR": str(env["profile_dir"])}, clear=False):
                runtime_env = zotero_paths.build_environment(
                    explicit_executable=str(env["executable"]),
                    explicit_data_dir=str(env["data_dir"]),
                )
            self.assertEqual(runtime_env.profile_dir, env["profile_dir"])

    def test_build_environment_falls_back_to_home_zotero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_root = Path(tmpdir) / "AppData" / "Roaming" / "Zotero" / "Zotero"
            profile_dir = profile_root / "Profiles" / "test.default"
            profile_dir.mkdir(parents=True, exist_ok=True)
            (profile_root / "profiles.ini").write_text("[Profile0]\nName=default\nIsRelative=1\nPath=Profiles/test.default\nDefault=1\n", encoding="utf-8")
            (profile_dir / "prefs.js").write_text("", encoding="utf-8")
            home = Path(tmpdir) / "Home"
            (home / "Zotero").mkdir(parents=True, exist_ok=True)
            with mock.patch("cli_anything.zotero.utils.zotero_paths.Path.home", return_value=home):
                runtime_env = zotero_paths.build_environment(explicit_profile_dir=str(profile_root))
            self.assertEqual(runtime_env.data_dir, home / "Zotero")

    def test_ensure_local_api_enabled_writes_user_js(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = create_sample_environment(Path(tmpdir))
            path = zotero_paths.ensure_local_api_enabled(env["profile_dir"])
            self.assertIsNotNone(path)
            self.assertIn('extensions.zotero.httpServer.localAPI.enabled', path.read_text(encoding="utf-8"))

    def test_find_executable_returns_none_when_unresolved(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch("cli_anything.zotero.utils.zotero_paths.shutil.which", return_value=None):
                with mock.patch("pathlib.Path.exists", return_value=False):
                    self.assertIsNone(zotero_paths.find_executable(env={}))


class SQLiteInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.env = create_sample_environment(Path(self.tmpdir.name))

    def test_fetch_libraries(self):
        libraries = zotero_sqlite.fetch_libraries(self.env["sqlite_path"])
        self.assertEqual(len(libraries), 2)
        self.assertEqual([entry["type"] for entry in libraries], ["user", "group"])

    def test_fetch_collections_and_tree(self):
        collections = zotero_sqlite.fetch_collections(self.env["sqlite_path"], library_id=1)
        self.assertIn("Sample Collection", [entry["collectionName"] for entry in collections])
        tree = zotero_sqlite.build_collection_tree(collections)
        self.assertIn("Sample Collection", [entry["collectionName"] for entry in tree])

    def test_resolve_item_includes_fields_creators_tags(self):
        item = zotero_sqlite.resolve_item(self.env["sqlite_path"], "REG12345")
        self.assertEqual(item["title"], "Sample Title")
        self.assertEqual(item["fields"]["title"], "Sample Title")
        self.assertEqual(item["creators"][0]["lastName"], "Lovelace")
        self.assertEqual(item["tags"][0]["name"], "sample-tag")

    def test_fetch_item_children_and_attachments(self):
        children = zotero_sqlite.fetch_item_children(self.env["sqlite_path"], "REG12345")
        self.assertEqual(len(children), 2)
        attachments = zotero_sqlite.fetch_item_attachments(self.env["sqlite_path"], "REG12345")
        self.assertEqual(len(attachments), 1)
        resolved = zotero_sqlite.resolve_attachment_real_path(attachments[0], self.env["data_dir"])
        self.assertTrue(str(resolved).endswith("paper.pdf"))

        linked_attachments = zotero_sqlite.fetch_item_attachments(self.env["sqlite_path"], "REG67890")
        self.assertEqual(len(linked_attachments), 1)
        linked_resolved = zotero_sqlite.resolve_attachment_real_path(linked_attachments[0], self.env["data_dir"])
        self.assertEqual(linked_resolved, "C:\\Users\\Public\\linked.pdf")

    def test_duplicate_key_resolution_requires_library_context(self):
        with self.assertRaises(zotero_sqlite.AmbiguousReferenceError):
            zotero_sqlite.resolve_item(self.env["sqlite_path"], "DUPITEM1")
        with self.assertRaises(zotero_sqlite.AmbiguousReferenceError):
            zotero_sqlite.resolve_collection(self.env["sqlite_path"], "DUPCOLL1")
        with self.assertRaises(zotero_sqlite.AmbiguousReferenceError):
            zotero_sqlite.resolve_saved_search(self.env["sqlite_path"], "DUPSEARCH")

        user_item = zotero_sqlite.resolve_item(self.env["sqlite_path"], "DUPITEM1", library_id=1)
        group_item = zotero_sqlite.resolve_item(self.env["sqlite_path"], "DUPITEM1", library_id=2)
        self.assertEqual(user_item["title"], "User Duplicate Title")
        self.assertEqual(group_item["title"], "Group Duplicate Title")

        group_collection = zotero_sqlite.resolve_collection(self.env["sqlite_path"], "DUPCOLL1", library_id=2)
        self.assertEqual(group_collection["collectionName"], "Group Duplicate Collection")

        group_search = zotero_sqlite.resolve_saved_search(self.env["sqlite_path"], "DUPSEARCH", library_id=2)
        self.assertEqual(group_search["savedSearchName"], "Group Duplicate Search")

    def test_cross_library_unique_key_still_resolves_without_session_context(self):
        group_item = zotero_sqlite.resolve_item(self.env["sqlite_path"], "GROUPKEY")
        self.assertEqual(group_item["libraryID"], 2)
        group_collection = zotero_sqlite.resolve_collection(self.env["sqlite_path"], "GCOLLAAA")
        self.assertEqual(group_collection["libraryID"], 2)

    def test_fetch_saved_searches_and_tags(self):
        searches = zotero_sqlite.fetch_saved_searches(self.env["sqlite_path"], library_id=1)
        self.assertEqual(searches[0]["savedSearchName"], "Important")
        tags = zotero_sqlite.fetch_tags(self.env["sqlite_path"], library_id=1)
        self.assertEqual(tags[0]["name"], "sample-tag")
        items = zotero_sqlite.fetch_tag_items(self.env["sqlite_path"], "sample-tag", library_id=1)
        self.assertGreaterEqual(len(items), 1)

    def test_find_collections_and_items_and_notes(self):
        collections = zotero_sqlite.find_collections(self.env["sqlite_path"], "collection", library_id=1, limit=10)
        self.assertGreaterEqual(len(collections), 2)
        self.assertIn("Archive Collection", [entry["collectionName"] for entry in collections])

        fuzzy_items = zotero_sqlite.find_items_by_title(self.env["sqlite_path"], "Sample", library_id=1, limit=10)
        self.assertEqual(fuzzy_items[0]["key"], "REG12345")
        exact_items = zotero_sqlite.find_items_by_title(self.env["sqlite_path"], "Sample Title", library_id=1, exact_title=True, limit=10)
        self.assertEqual(exact_items[0]["itemID"], 1)

        notes = zotero_sqlite.fetch_item_notes(self.env["sqlite_path"], "REG12345")
        self.assertEqual(notes[0]["typeName"], "note")
        self.assertEqual(notes[0]["noteText"], "Example note")

    def test_experimental_sqlite_write_helpers(self):
        created = zotero_sqlite.create_collection_record(self.env["sqlite_path"], name="Created Here", library_id=1, parent_collection_id=1)
        self.assertEqual(created["collectionName"], "Created Here")
        self.assertTrue(Path(created["backupPath"]).exists())

        added = zotero_sqlite.add_item_to_collection_record(self.env["sqlite_path"], item_id=1, collection_id=2)
        self.assertTrue(Path(added["backupPath"]).exists())

        moved = zotero_sqlite.move_item_between_collections_record(
            self.env["sqlite_path"],
            item_id=4,
            target_collection_id=1,
            source_collection_ids=[2],
        )
        self.assertTrue(Path(moved["backupPath"]).exists())
        memberships = zotero_sqlite.fetch_item_collections(self.env["sqlite_path"], 4)
        self.assertEqual([membership["collectionID"] for membership in memberships], [1])


class SessionTests(unittest.TestCase):
    def test_save_and_load_session_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict("os.environ", {"CLI_ANYTHING_ZOTERO_STATE_DIR": tmpdir}, clear=False):
                state = session_mod.default_session_state()
                state["current_item"] = "REG12345"
                session_mod.save_session_state(state)
                loaded = session_mod.load_session_state()
                self.assertEqual(loaded["current_item"], "REG12345")

    def test_expand_repl_aliases(self):
        state = {"current_library": "1", "current_collection": "2", "current_item": "REG12345"}
        expanded = session_mod.expand_repl_aliases_with_state(["item", "get", "@item", "@collection"], state)
        self.assertEqual(expanded, ["item", "get", "REG12345", "2"])

    def test_normalize_library_ref_accepts_plain_and_tree_view_ids(self):
        self.assertEqual(zotero_sqlite.normalize_library_ref("1"), 1)
        self.assertEqual(zotero_sqlite.normalize_library_ref("L1"), 1)
        self.assertEqual(zotero_sqlite.normalize_library_ref(2), 2)


class HttpUtilityTests(unittest.TestCase):
    def test_build_runtime_context_reports_unavailable_services(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = create_sample_environment(Path(tmpdir))
            prefs_path = env["profile_dir"] / "prefs.js"
            prefs_text = prefs_path.read_text(encoding="utf-8").replace("23119", "23191")
            prefs_path.write_text(prefs_text, encoding="utf-8")
            runtime = discovery.build_runtime_context(
                data_dir=str(env["data_dir"]),
                profile_dir=str(env["profile_dir"]),
                executable=str(env["executable"]),
            )
            self.assertFalse(runtime.connector_available)
            self.assertFalse(runtime.local_api_available)

    def test_catalog_style_list_parses_csl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = create_sample_environment(Path(tmpdir))
            runtime = discovery.build_runtime_context(
                data_dir=str(env["data_dir"]),
                profile_dir=str(env["profile_dir"]),
                executable=str(env["executable"]),
            )
            styles = catalog.list_styles(runtime)
            self.assertEqual(styles[0]["title"], "Sample Style")

    def test_wait_for_endpoint_requires_explicit_ready_status(self):
        with fake_zotero_http_server(local_api_root_status=403) as server:
            ready = zotero_http.wait_for_endpoint(
                server["port"],
                "/api/",
                timeout=1,
                poll_interval=0.05,
                headers={"Zotero-API-Version": zotero_http.LOCAL_API_VERSION},
            )
        self.assertFalse(ready)

        with fake_zotero_http_server(local_api_root_status=200) as server:
            ready = zotero_http.wait_for_endpoint(
                server["port"],
                "/api/",
                timeout=1,
                poll_interval=0.05,
                headers={"Zotero-API-Version": zotero_http.LOCAL_API_VERSION},
            )
        self.assertTrue(ready)

    def test_launch_zotero_raises_when_executable_is_unresolved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = create_sample_environment(Path(tmpdir))
            runtime = discovery.build_runtime_context(
                data_dir=str(env["data_dir"]),
                profile_dir=str(env["profile_dir"]),
                executable=str(env["executable"]),
            )
            runtime.environment.executable = None
            with self.assertRaisesRegex(RuntimeError, "could not be resolved"):
                discovery.launch_zotero(runtime)


class ImportCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.env = create_sample_environment(Path(self.tmpdir.name))
        self.runtime = discovery.build_runtime_context(
            data_dir=str(self.env["data_dir"]),
            profile_dir=str(self.env["profile_dir"]),
            executable=str(self.env["executable"]),
        )

    def test_enable_local_api_reports_idempotent_state(self):
        payload = imports_mod.enable_local_api(self.runtime)
        self.assertTrue(payload["enabled"])
        self.assertFalse(payload["already_enabled"])
        self.assertTrue(Path(payload["user_js_path"]).exists())

        refreshed = discovery.build_runtime_context(
            data_dir=str(self.env["data_dir"]),
            profile_dir=str(self.env["profile_dir"]),
            executable=str(self.env["executable"]),
        )
        second = imports_mod.enable_local_api(refreshed)
        self.assertTrue(second["already_enabled"])

    def test_import_json_uses_session_collection_and_tags(self):
        json_path = Path(self.tmpdir.name) / "items.json"
        json_path.write_text('[{"itemType": "journalArticle", "title": "Imported"}]', encoding="utf-8")

        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_items") as save_items:
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session") as update_session:
                    payload = imports_mod.import_json(
                        self.runtime,
                        json_path,
                        tags=["alpha", "beta"],
                        session={"current_collection": "COLLAAAA"},
                    )

        save_items.assert_called_once()
        submitted_items = save_items.call_args.args[1]
        self.assertEqual(submitted_items[0]["title"], "Imported")
        self.assertTrue(submitted_items[0]["id"].startswith("cli-anything-zotero-"))
        update_session.assert_called_once()
        self.assertEqual(update_session.call_args.kwargs["target"], "C1")
        self.assertEqual(update_session.call_args.kwargs["tags"], ["alpha", "beta"])
        self.assertEqual(payload["submitted_count"], 1)
        self.assertEqual(payload["target"]["treeViewID"], "C1")

    def test_import_file_posts_raw_text_and_explicit_tree_view_target(self):
        ris_path = Path(self.tmpdir.name) / "sample.ris"
        ris_path.write_text("TY  - JOUR\nTI  - Imported Title\nER  - \n", encoding="utf-8")

        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.connector_import_text", return_value=[{"title": "Imported Title"}]) as import_text:
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session") as update_session:
                    payload = imports_mod.import_file(
                        self.runtime,
                        ris_path,
                        collection_ref="C99",
                        tags=["imported"],
                    )

        import_text.assert_called_once()
        self.assertIn("Imported Title", import_text.call_args.args[1])
        update_session.assert_called_once()
        self.assertEqual(update_session.call_args.kwargs["target"], "C99")
        self.assertEqual(payload["imported_count"], 1)

    def test_import_json_strips_inline_attachments_and_uploads_local_pdf(self):
        pdf_path = Path(self.tmpdir.name) / "inline.pdf"
        pdf_path.write_bytes(sample_pdf_bytes("inline"))
        json_path = Path(self.tmpdir.name) / "items.json"
        json_path.write_text(
            '[{"itemType": "journalArticle", "title": "Imported", "attachments": [{"path": "%s"}]}]' % str(pdf_path).replace("\\", "\\\\"),
            encoding="utf-8",
        )

        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_items") as save_items:
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session"):
                    with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_attachment") as save_attachment:
                        payload = imports_mod.import_json(
                            self.runtime,
                            json_path,
                            attachment_timeout=91,
                        )

        submitted_items = save_items.call_args.args[1]
        self.assertNotIn("attachments", submitted_items[0])
        self.assertEqual(payload["attachment_summary"]["created_count"], 1)
        self.assertEqual(payload["status"], "success")
        save_attachment.assert_called_once()
        self.assertEqual(save_attachment.call_args.kwargs["parent_item_id"], submitted_items[0]["id"])
        self.assertEqual(save_attachment.call_args.kwargs["timeout"], 91)
        self.assertTrue(save_attachment.call_args.kwargs["url"].startswith("file:///"))
        self.assertTrue(save_attachment.call_args.kwargs["content"].startswith(b"%PDF-"))

    def test_import_json_url_attachment_uses_delay_and_default_timeout(self):
        json_path = Path(self.tmpdir.name) / "items.json"
        with fake_zotero_http_server() as server:
            json_path.write_text(
                json.dumps(
                    [
                        {
                            "itemType": "journalArticle",
                            "title": "Imported URL",
                            "attachments": [
                                {
                                    "url": f"http://127.0.0.1:{server['port']}/downloads/wrong-content-type.pdf",
                                    "delay_ms": 10,
                                }
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch.object(self.runtime, "connector_available", True):
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_items"):
                    with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session"):
                        with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_attachment") as save_attachment:
                            with mock.patch("cli_anything.zotero.core.imports.time.sleep") as sleep:
                                payload = imports_mod.import_json(
                                    self.runtime,
                                    json_path,
                                    attachment_timeout=47,
                                )

        sleep.assert_called_once_with(0.01)
        save_attachment.assert_called_once()
        self.assertEqual(save_attachment.call_args.kwargs["timeout"], 47)
        self.assertEqual(payload["attachment_summary"]["created_count"], 1)

    def test_import_json_duplicate_inline_attachments_are_skipped(self):
        pdf_path = Path(self.tmpdir.name) / "duplicate.pdf"
        pdf_path.write_bytes(sample_pdf_bytes("duplicate"))
        json_path = Path(self.tmpdir.name) / "items.json"
        json_path.write_text(
            json.dumps(
                [
                    {
                        "itemType": "journalArticle",
                        "title": "Imported Duplicate",
                        "attachments": [
                            {"path": str(pdf_path)},
                            {"path": str(pdf_path)},
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )

        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_items"):
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session"):
                    with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_attachment") as save_attachment:
                        payload = imports_mod.import_json(self.runtime, json_path)

        save_attachment.assert_called_once()
        self.assertEqual(payload["attachment_summary"]["created_count"], 1)
        self.assertEqual(payload["attachment_summary"]["skipped_count"], 1)
        self.assertEqual(payload["attachment_results"][1]["status"], "skipped_duplicate")

    def test_import_json_rejects_invalid_inline_attachment_schema(self):
        json_path = Path(self.tmpdir.name) / "invalid-attachments.json"
        json_path.write_text(
            json.dumps(
                [
                    {
                        "itemType": "journalArticle",
                        "title": "Broken",
                        "attachments": [{"path": "a.pdf", "url": "https://example.com/a.pdf"}],
                    }
                ]
            ),
            encoding="utf-8",
        )
        with mock.patch.object(self.runtime, "connector_available", True):
            with self.assertRaises(RuntimeError):
                imports_mod.import_json(self.runtime, json_path)

    def test_import_file_manifest_partial_success_records_attachment_failures(self):
        ris_path = Path(self.tmpdir.name) / "sample.ris"
        ris_path.write_text("TY  - JOUR\nTI  - Imported Title\nER  - \n", encoding="utf-8")
        pdf_path = Path(self.tmpdir.name) / "manifest.pdf"
        pdf_path.write_bytes(sample_pdf_bytes("manifest"))
        manifest_path = Path(self.tmpdir.name) / "attachments.json"
        manifest_path.write_text(
            json.dumps(
                [
                    {
                        "index": 0,
                        "attachments": [
                            {"path": str(pdf_path)},
                            {"path": str(Path(self.tmpdir.name) / "missing.pdf")},
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )

        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch(
                "cli_anything.zotero.utils.zotero_http.connector_import_text",
                return_value=[{"id": "imported-1", "title": "Imported Title"}],
            ):
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session"):
                    with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_attachment") as save_attachment:
                        payload = imports_mod.import_file(
                            self.runtime,
                            ris_path,
                            attachments_manifest=manifest_path,
                        )

        save_attachment.assert_called_once()
        self.assertEqual(payload["status"], "partial_success")
        self.assertEqual(payload["attachment_summary"]["created_count"], 1)
        self.assertEqual(payload["attachment_summary"]["failed_count"], 1)
        self.assertIn("Attachment file not found", payload["attachment_results"][1]["error"])

    def test_import_file_manifest_title_mismatch_marks_attachment_failure(self):
        ris_path = Path(self.tmpdir.name) / "sample.ris"
        ris_path.write_text("TY  - JOUR\nTI  - Imported Title\nER  - \n", encoding="utf-8")
        pdf_path = Path(self.tmpdir.name) / "manifest.pdf"
        pdf_path.write_bytes(sample_pdf_bytes("manifest"))
        manifest_path = Path(self.tmpdir.name) / "attachments.json"
        manifest_path.write_text(
            json.dumps(
                [
                    {
                        "index": 0,
                        "expected_title": "Different Title",
                        "attachments": [{"path": str(pdf_path)}],
                    }
                ]
            ),
            encoding="utf-8",
        )

        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch(
                "cli_anything.zotero.utils.zotero_http.connector_import_text",
                return_value=[{"id": "imported-1", "title": "Imported Title"}],
            ):
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session"):
                    with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_attachment") as save_attachment:
                        payload = imports_mod.import_file(
                            self.runtime,
                            ris_path,
                            attachments_manifest=manifest_path,
                        )

        save_attachment.assert_not_called()
        self.assertEqual(payload["status"], "partial_success")
        self.assertIn("title mismatch", payload["attachment_results"][0]["error"])

    def test_import_file_manifest_index_out_of_range_and_missing_connector_id_fail_cleanly(self):
        ris_path = Path(self.tmpdir.name) / "sample.ris"
        ris_path.write_text("TY  - JOUR\nTI  - Imported Title\nER  - \n", encoding="utf-8")
        pdf_path = Path(self.tmpdir.name) / "manifest.pdf"
        pdf_path.write_bytes(sample_pdf_bytes("manifest"))
        manifest_path = Path(self.tmpdir.name) / "attachments.json"
        manifest_path.write_text(
            json.dumps(
                [
                    {"index": 1, "attachments": [{"path": str(pdf_path)}]},
                    {"index": 0, "attachments": [{"path": str(pdf_path)}]},
                ]
            ),
            encoding="utf-8",
        )

        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch(
                "cli_anything.zotero.utils.zotero_http.connector_import_text",
                return_value=[{"title": "Imported Title"}],
            ):
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_update_session"):
                    with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_attachment") as save_attachment:
                        payload = imports_mod.import_file(
                            self.runtime,
                            ris_path,
                            attachments_manifest=manifest_path,
                        )

        save_attachment.assert_not_called()
        self.assertEqual(payload["attachment_summary"]["failed_count"], 2)
        self.assertIn("index 1", payload["attachment_results"][0]["error"])
        self.assertIn("did not include a connector id", payload["attachment_results"][1]["error"])

    def test_import_json_rejects_invalid_json(self):
        json_path = Path(self.tmpdir.name) / "bad.json"
        json_path.write_text("{not-valid", encoding="utf-8")
        with mock.patch.object(self.runtime, "connector_available", True):
            with self.assertRaises(RuntimeError):
                imports_mod.import_json(self.runtime, json_path)

    def test_import_requires_connector(self):
        json_path = Path(self.tmpdir.name) / "items.json"
        json_path.write_text("[]", encoding="utf-8")
        with mock.patch.object(self.runtime, "connector_available", False):
            with self.assertRaises(RuntimeError):
                imports_mod.import_json(self.runtime, json_path)


class WorkflowCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.env = create_sample_environment(Path(self.tmpdir.name))
        self.runtime = discovery.build_runtime_context(
            data_dir=str(self.env["data_dir"]),
            profile_dir=str(self.env["profile_dir"]),
            executable=str(self.env["executable"]),
        )

    def test_collection_find_and_item_find_sqlite_fallback(self):
        collections = catalog.find_collections(self.runtime, "sample", limit=10)
        self.assertEqual(collections[0]["key"], "COLLAAAA")

        with mock.patch.object(self.runtime, "local_api_available", False):
            items = catalog.find_items(self.runtime, "Sample", limit=10, session={})
        self.assertEqual(items[0]["key"], "REG12345")

        exact = catalog.find_items(self.runtime, "Sample Title", exact_title=True, limit=10, session={})
        self.assertEqual(exact[0]["itemID"], 1)

    def test_collection_scoped_item_find_prefers_local_api(self):
        with mock.patch.object(self.runtime, "local_api_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.local_api_get_json", return_value=[{"key": "REG12345"}]) as local_api:
                items = catalog.find_items(self.runtime, "Sample", collection_ref="COLLAAAA", limit=5, session={})
        local_api.assert_called_once()
        self.assertEqual(items[0]["key"], "REG12345")

    def test_group_library_local_api_scope_and_search_routes(self):
        self.assertEqual(catalog.local_api_scope(self.runtime, 1), "/api/users/0")
        self.assertEqual(catalog.local_api_scope(self.runtime, 2), "/api/groups/2")

        with mock.patch.object(self.runtime, "local_api_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.local_api_get_json", return_value=[{"key": "GROUPKEY"}]) as local_api:
                items = catalog.find_items(
                    self.runtime,
                    "Group",
                    collection_ref="GCOLLAAA",
                    limit=5,
                    session={"current_library": 2},
                )
        self.assertEqual(items[0]["libraryID"], 2)
        self.assertIn("/api/groups/2/collections/GCOLLAAA/items/top", local_api.call_args.args[1])

        with mock.patch.object(self.runtime, "local_api_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.local_api_get_json", return_value=[{"key": "GROUPKEY"}]) as local_api:
                payload = catalog.search_items(self.runtime, "GSEARCHKEY", session={"current_library": 2})
        self.assertEqual(payload[0]["key"], "GROUPKEY")
        self.assertIn("/api/groups/2/searches/GSEARCHKEY/items", local_api.call_args.args[1])

    def test_item_notes_and_note_get(self):
        item_notes = catalog.item_notes(self.runtime, "REG12345")
        self.assertEqual(len(item_notes), 1)
        self.assertEqual(item_notes[0]["notePreview"], "Example note")

        note = notes_mod.get_note(self.runtime, "NOTEKEY")
        self.assertEqual(note["noteText"], "Example note")

    def test_note_add_builds_child_note_payload(self):
        with mock.patch.object(self.runtime, "connector_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.get_selected_collection", return_value={"libraryID": 1}):
                with mock.patch("cli_anything.zotero.utils.zotero_http.connector_save_items") as save_items:
                    payload = notes_mod.add_note(
                        self.runtime,
                        "REG12345",
                        text="# Heading\n\nA **bold** note",
                        fmt="markdown",
                    )
        save_items.assert_called_once()
        submitted = save_items.call_args.args[1][0]
        self.assertEqual(submitted["itemType"], "note")
        self.assertEqual(submitted["parentItem"], "REG12345")
        self.assertIn("<h1>", submitted["note"])
        self.assertEqual(payload["parentItemKey"], "REG12345")

    def test_item_context_aggregates_exports_and_links(self):
        with mock.patch.object(self.runtime, "local_api_available", True):
            with mock.patch("cli_anything.zotero.core.rendering.export_item", side_effect=[{"content": "@article{sample}"}, {"content": '{"id":"sample"}'}]):
                payload = analysis.build_item_context(
                    self.runtime,
                    "REG12345",
                    include_notes=True,
                    include_bibtex=True,
                    include_csljson=True,
                    include_links=True,
                )
        self.assertEqual(payload["links"]["doi_url"], "https://doi.org/10.1000/sample")
        self.assertIn("bibtex", payload["exports"])
        self.assertIn("Notes:", payload["prompt_context"])

    def test_item_analyze_requires_api_key_and_uses_openai(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                analysis.analyze_item(self.runtime, "REG12345", question="Summarize", model="gpt-test")

        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with mock.patch("cli_anything.zotero.core.analysis.build_item_context", return_value={"item": {"key": "REG12345"}, "prompt_context": "Title: Sample"}):
                with mock.patch("cli_anything.zotero.utils.openai_api.create_text_response", return_value={"response_id": "resp_123", "answer": "Analysis", "raw": {}}) as create_response:
                    payload = analysis.analyze_item(self.runtime, "REG12345", question="Summarize", model="gpt-test")
        create_response.assert_called_once()
        self.assertEqual(payload["answer"], "Analysis")

    def test_experimental_commands_require_closed_zotero_and_update_db_copy(self):
        with mock.patch.object(self.runtime, "connector_available", True):
            with self.assertRaises(RuntimeError):
                experimental.create_collection(self.runtime, "Blocked")

        with mock.patch.object(self.runtime, "connector_available", False):
            created = experimental.create_collection(self.runtime, "Created")
            self.assertEqual(created["action"], "collection_create")

            added = experimental.add_item_to_collection(self.runtime, "REG12345", "COLLBBBB")
            self.assertEqual(added["action"], "item_add_to_collection")

            moved = experimental.move_item_to_collection(
                self.runtime,
                "REG67890",
                "COLLAAAA",
                from_refs=["COLLBBBB"],
            )
        self.assertEqual(moved["action"], "item_move_to_collection")

    def test_rendering_uses_group_library_local_api_scope(self):
        with mock.patch.object(self.runtime, "local_api_available", True):
            with mock.patch("cli_anything.zotero.utils.zotero_http.local_api_get_text", return_value="TY  - JOUR\nER  - \n") as get_text:
                export_payload = rendering.export_item(self.runtime, "GROUPKEY", "ris", session={"current_library": 2})
        self.assertEqual(export_payload["libraryID"], 2)
        self.assertIn("/api/groups/2/items/GROUPKEY", get_text.call_args.args[1])


class OpenAIUtilityTests(unittest.TestCase):
    def test_extract_text_from_response_payload(self):
        payload = {
            "id": "resp_1",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Hello world"},
                    ],
                }
            ],
        }
        result = openai_api._extract_text(payload)
        self.assertEqual(result, "Hello world")
