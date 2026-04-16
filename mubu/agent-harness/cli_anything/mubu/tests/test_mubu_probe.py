import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mubu_probe import (
    build_api_headers,
    build_create_child_request,
    build_delete_node_request,
    build_text_update_request,
    choose_current_daily_document,
    document_links,
    extract_doc_links,
    extract_plain_text,
    folder_documents,
    latest_doc_member_context,
    list_document_nodes,
    load_latest_backups,
    looks_like_daily_title,
    main,
    node_path_to_api_path,
    normalize_document_meta_record,
    normalize_folder_record,
    normalize_user_record,
    parent_context_for_path,
    parse_client_sync_line,
    resolve_document_reference,
    search_documents,
    show_document_by_reference,
)


class ExtractPlainTextTests(unittest.TestCase):
    def test_extract_plain_text_handles_html_and_segment_lists(self):
        self.assertEqual(extract_plain_text("<span>简历做一下</span>"), "简历做一下")
        self.assertEqual(
            extract_plain_text(
                [
                    {"type": 1, "text": "简历"},
                    {"type": 1, "text": "更新"},
                ]
            ),
            "简历更新",
        )


class BackupLoadingTests(unittest.TestCase):
    def test_load_latest_backups_picks_newest_file_per_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            doc_dir = root / "docA"
            doc_dir.mkdir()

            older = doc_dir / "2026-03-01 10'00.json"
            newer = doc_dir / "2026-03-01 11'00.json"
            older.write_text(json.dumps({"nodes": [{"text": "<span>旧</span>", "children": []}]}))
            newer.write_text(json.dumps({"nodes": [{"text": "<span>新</span>", "children": []}]}))

            older.touch()
            newer.touch()

            docs = load_latest_backups(root)
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["doc_id"], "docA")
            self.assertTrue(docs[0]["backup_file"].endswith("11'00.json"))
            self.assertEqual(docs[0]["title"], "新")


class SearchTests(unittest.TestCase):
    def test_search_documents_finds_text_and_note(self):
        docs = [
            {
                "doc_id": "docA",
                "backup_file": "/tmp/docA.json",
                "title": "项目计划",
                "data": {
                    "nodes": [
                        {
                            "id": "n1",
                            "text": "<span>简历做一下更新</span>",
                            "note": "<span>今天处理</span>",
                            "children": [],
                        }
                    ]
                },
            }
        ]

        hits = search_documents(docs, "简历")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["doc_id"], "docA")
        self.assertEqual(hits[0]["node_id"], "n1")
        self.assertEqual(hits[0]["text"], "简历做一下更新")


class ClientSyncParsingTests(unittest.TestCase):
    def test_parse_client_sync_line_extracts_change_request(self):
        line = (
            '[2026-03-17T17:18:40.006] [INFO] clientSync - Info:  Net request 45715 '
            '{"pathname":"/v3/api/colla/events","data":{"memberId":"7992964417993318",'
            '"type":"CHANGE","version":209,"documentId":"doc-demo-01","events":[{"name":"create"}]},'
            '"method":"POST"}'
        )

        parsed = parse_client_sync_line(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["timestamp"], "2026-03-17T17:18:40.006")
        self.assertEqual(parsed["kind"], "change_request")
        self.assertEqual(parsed["document_id"], "doc-demo-01")
        self.assertEqual(parsed["event_type"], "CHANGE")
        self.assertEqual(parsed["version"], 209)


class FolderNormalizationTests(unittest.TestCase):
    def test_normalize_folder_record_extracts_parent_children_and_timestamps(self):
        raw = {
            "id": "folder-root-01",
            "|o": "Workspace",
            "|h": "0",
            "|p": '[{"id":"doc-link-001","type":"doc"},{"id":"folder-daily-01","type":"folder"}]',
            "|d": 1753841934779,
            "|n": 1773313495971,
            "|t": 1773313495971,
            "|v": 1773313495971,
            "_rev": "2792-d896b5c6a897c7c7b5e61487029f29ad",
        }

        normalized = normalize_folder_record(raw)
        self.assertEqual(normalized["folder_id"], "folder-root-01")
        self.assertEqual(normalized["name"], "Workspace")
        self.assertEqual(normalized["parent_id"], "0")
        self.assertEqual(normalized["created_at"], 1753841934779)
        self.assertEqual(normalized["updated_at"], 1773313495971)
        self.assertEqual(normalized["children"][0]["id"], "doc-link-001")
        self.assertEqual(normalized["children"][1]["type"], "folder")


class DocumentMetaNormalizationTests(unittest.TestCase):
    def test_normalize_document_meta_record_extracts_folder_title_and_times(self):
        raw = {
            "id": "1kapleatfQ0",
            "|h": "folder-daily-01",
            "|n": "11.24",
            "|e": 1763865805160,
            "|z": 1764003928841,
            "|B": 1764003934105,
            "|m": 1764003934105,
            "|j": 48,
            "|d": "NewSyncApp",
            "_rev": "915-ca5340b309a22ea63f8990f806765fbc",
        }

        normalized = normalize_document_meta_record(raw)
        self.assertEqual(normalized["doc_id"], "1kapleatfQ0")
        self.assertEqual(normalized["folder_id"], "folder-daily-01")
        self.assertEqual(normalized["title"], "11.24")
        self.assertEqual(normalized["created_at"], 1763865805160)
        self.assertEqual(normalized["updated_at"], 1764003934105)
        self.assertEqual(normalized["word_count"], 48)
        self.assertEqual(normalized["source"], "NewSyncApp")


class LinkExtractionTests(unittest.TestCase):
    def test_extract_doc_links_finds_mubu_doc_mentions(self):
        markup = (
            '<span>参考</span>'
            '<a class="mention mm-iconfont" href="https://mubu.com/docdoc-link-001" '
            'data-token="doc-link-001">DDL表(To Do List)</a>'
        )

        links = extract_doc_links(markup)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["target_doc_id"], "doc-link-001")
        self.assertEqual(links[0]["label"], "DDL表(To Do List)")


class PathResolutionTests(unittest.TestCase):
    def setUp(self):
        self.folders = [
            {"folder_id": "rootA", "name": "Workspace", "parent_id": "0"},
            {"folder_id": "dailyA", "name": "Daily tasks", "parent_id": "rootA"},
            {"folder_id": "rootB", "name": "Archive", "parent_id": "0"},
            {"folder_id": "dailyB", "name": "Daily tasks", "parent_id": "rootB"},
        ]
        self.document_metas = [
            {"doc_id": "docA", "folder_id": "dailyA", "title": "26.03.16", "updated_at": 20},
            {"doc_id": "docA2", "folder_id": "dailyA", "title": "26.03.16", "updated_at": 25},
            {"doc_id": "docB", "folder_id": "dailyA", "title": "26.3.15", "updated_at": 10},
            {"doc_id": "docC", "folder_id": "dailyB", "title": "26.03.16", "updated_at": 30},
        ]
        self.backups = [
            {
                "doc_id": "docA2",
                "title": "today root",
                "backup_file": "/tmp/docA2.json",
                "modified_at": 123.0,
                "data": {"viewType": "OUTLINE", "nodes": [{"id": "n1", "text": "<span>today</span>", "children": []}]},
            }
        ]

    def test_folder_documents_supports_full_folder_path(self):
        docs, folder, ambiguous = folder_documents(self.document_metas, self.folders, "Workspace/Daily tasks")
        self.assertEqual(ambiguous, [])
        self.assertEqual(folder["folder_id"], "dailyA")
        self.assertEqual([doc["doc_id"] for doc in docs], ["docA2", "docB"])
        self.assertEqual(docs[0]["doc_path"], "Workspace/Daily tasks/26.03.16")

    def test_folder_documents_detects_ambiguous_folder_name(self):
        docs, folder, ambiguous = folder_documents(self.document_metas, self.folders, "Daily tasks")
        self.assertEqual(docs, [])
        self.assertIsNone(folder)
        self.assertEqual(len(ambiguous), 2)

    def test_resolve_document_reference_supports_full_doc_path(self):
        doc, ambiguous = resolve_document_reference(self.document_metas, self.folders, "Workspace/Daily tasks/26.03.16")
        self.assertEqual(ambiguous, [])
        self.assertEqual(doc["doc_id"], "docA2")
        self.assertEqual(doc["doc_path"], "Workspace/Daily tasks/26.03.16")

    def test_resolve_document_reference_detects_ambiguous_title(self):
        doc, ambiguous = resolve_document_reference(self.document_metas, self.folders, "26.03.16")
        self.assertIsNone(doc)
        self.assertEqual(len(ambiguous), 2)
        self.assertEqual({item["doc_id"] for item in ambiguous}, {"docA2", "docC"})

    def test_resolve_document_reference_collapses_same_path_duplicates_for_title(self):
        folders = [
            {"folder_id": "rootA", "name": "Workspace", "parent_id": "0"},
            {"folder_id": "dailyA", "name": "Daily tasks", "parent_id": "rootA"},
        ]
        metas = [
            {"doc_id": "old", "folder_id": "dailyA", "title": "26.03.18", "updated_at": 10},
            {"doc_id": "new", "folder_id": "dailyA", "title": "26.03.18", "updated_at": 20},
        ]

        doc, ambiguous = resolve_document_reference(metas, folders, "26.03.18")

        self.assertEqual(ambiguous, [])
        self.assertEqual(doc["doc_id"], "new")

    def test_resolve_document_reference_prefers_newer_timestamp_over_higher_revision_across_doc_ids(self):
        folders = [
            {"folder_id": "rootA", "name": "Workspace", "parent_id": "0"},
            {"folder_id": "dailyA", "name": "Daily tasks", "parent_id": "rootA"},
        ]
        metas = [
            {
                "doc_id": "old-high-rev",
                "folder_id": "dailyA",
                "title": "26.03.19",
                "updated_at": 10,
                "_rev": "999-older",
            },
            {
                "doc_id": "new-low-rev",
                "folder_id": "dailyA",
                "title": "26.03.19",
                "updated_at": 20,
                "_rev": "1-newer",
            },
        ]

        doc, ambiguous = resolve_document_reference(metas, folders, "Workspace/Daily tasks/26.03.19")

        self.assertEqual(ambiguous, [])
        self.assertEqual(doc["doc_id"], "new-low-rev")

    def test_show_document_by_reference_uses_resolved_path(self):
        payload, ambiguous = show_document_by_reference(
            self.backups,
            self.document_metas,
            self.folders,
            "Workspace/Daily tasks/26.03.16",
        )
        self.assertEqual(ambiguous, [])
        self.assertEqual(payload["doc_id"], "docA2")
        self.assertEqual(payload["title"], "26.03.16")
        self.assertEqual(payload["folder_path"], "Workspace/Daily tasks")
        self.assertEqual(payload["doc_path"], "Workspace/Daily tasks/26.03.16")
        self.assertEqual(payload["nodes"][0]["text"], "today")


class DocumentMetadataOverlayTests(unittest.TestCase):
    def test_document_links_prefers_metadata_title_for_source_document(self):
        links = document_links(
            [
                {
                    "doc_id": "docA",
                    "title": "root node title",
                    "data": {
                        "nodes": [
                            {
                                "id": "n1",
                                "text": (
                                    '<a class="mention mm-iconfont" '
                                    'href="https://mubu.com/docdoc-target-1" '
                                    'data-token="doc-target-1">Target Doc</a>'
                                ),
                                "children": [],
                            }
                        ]
                    },
                }
            ],
            "docA",
            title_lookup={"docA": "26.03.18", "doc-target-1": "Target Doc"},
        )

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["source_doc_title"], "26.03.18")

    def test_show_command_prefers_metadata_title_and_path_when_available(self):
        backups = [
            {
                "doc_id": "docA",
                "title": "root node title",
                "backup_file": "/tmp/docA.json",
                "modified_at": 123.0,
                "data": {
                    "viewType": "OUTLINE",
                    "nodes": [{"id": "n1", "text": "<span>today</span>", "children": []}],
                },
            }
        ]
        metas = [{"doc_id": "docA", "folder_id": "dailyA", "title": "26.03.18", "updated_at": 20}]
        folders = [
            {"folder_id": "rootA", "name": "Workspace", "parent_id": "0"},
            {"folder_id": "dailyA", "name": "Daily tasks", "parent_id": "rootA"},
        ]

        stdout = io.StringIO()
        with (
            mock.patch("mubu_probe.load_latest_backups", return_value=backups),
            mock.patch("mubu_probe.load_document_metas", return_value=metas),
            mock.patch("mubu_probe.load_folders", return_value=folders),
            contextlib.redirect_stdout(stdout),
        ):
            result = main(["show", "docA", "--json"])

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["title"], "26.03.18")
        self.assertEqual(payload["folder_path"], "Workspace/Daily tasks")
        self.assertEqual(payload["doc_path"], "Workspace/Daily tasks/26.03.18")


class DocumentNodeListingTests(unittest.TestCase):
    def test_list_document_nodes_flattens_tree_for_agent_targeting(self):
        data = {
            "nodes": [
                {
                    "id": "root-1",
                    "text": "<span>日志流</span>",
                    "note": "<span>顶层</span>",
                    "modified": 10,
                    "children": [
                        {
                            "id": "child-1",
                            "text": "<span>简历做一下</span>",
                            "note": "",
                            "modified": 20,
                            "children": [],
                        }
                    ],
                }
            ]
        }

        nodes = list_document_nodes(data)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]["node_id"], "root-1")
        self.assertEqual(nodes[0]["path"], ["nodes", 0])
        self.assertEqual(nodes[0]["depth"], 0)
        self.assertEqual(nodes[0]["text"], "日志流")
        self.assertEqual(nodes[1]["node_id"], "child-1")
        self.assertEqual(nodes[1]["path"], ["nodes", 0, 0])
        self.assertEqual(nodes[1]["depth"], 1)
        self.assertEqual(nodes[1]["text"], "简历做一下")

    def test_list_document_nodes_supports_query_and_max_depth(self):
        data = {
            "nodes": [
                {
                    "id": "root-1",
                    "text": "<span>日志流</span>",
                    "note": "",
                    "modified": 10,
                    "children": [
                        {
                            "id": "child-1",
                            "text": "<span>简历做一下</span>",
                            "note": "",
                            "modified": 20,
                            "children": [],
                        }
                    ],
                }
            ]
        }

        only_root = list_document_nodes(data, max_depth=0)
        self.assertEqual([item["node_id"] for item in only_root], ["root-1"])

        queried = list_document_nodes(data, query="简历")
        self.assertEqual([item["node_id"] for item in queried], ["child-1"])


class DailySelectionTests(unittest.TestCase):
    def test_looks_like_daily_title_accepts_date_titles_and_rejects_templates(self):
        self.assertTrue(looks_like_daily_title("26.03.16"))
        self.assertTrue(looks_like_daily_title("26.3.8-3.9"))
        self.assertTrue(looks_like_daily_title("2026-03-18"))
        self.assertTrue(looks_like_daily_title("2026年3月18日"))
        self.assertFalse(looks_like_daily_title("DDL表"))
        self.assertFalse(looks_like_daily_title("26.2.22模板更新"))

    def test_choose_current_daily_document_prefers_latest_date_titled_doc(self):
        docs = [
            {"doc_id": "template", "title": "26.2.22模板更新", "updated_at": 90},
            {"doc_id": "ddl", "title": "DDL表", "updated_at": 100},
            {"doc_id": "today", "title": "26.03.16", "updated_at": 120},
            {"doc_id": "yesterday", "title": "26.3.15", "updated_at": 110},
        ]

        selected, candidates = choose_current_daily_document(docs)
        self.assertEqual(selected["doc_id"], "today")
        self.assertEqual([item["doc_id"] for item in candidates], ["today", "yesterday"])

    def test_choose_current_daily_document_accepts_full_year_and_cn_date_titles(self):
        docs = [
            {"doc_id": "older", "title": "2026年3月17日", "updated_at": 90},
            {"doc_id": "latest", "title": "2026-03-18", "updated_at": 120},
            {"doc_id": "other", "title": "项目看板", "updated_at": 130},
        ]

        selected, candidates = choose_current_daily_document(docs)
        self.assertEqual(selected["doc_id"], "latest")
        self.assertEqual([item["doc_id"] for item in candidates], ["latest", "older"])

    def test_choose_current_daily_document_can_fallback_to_any_title(self):
        docs = [
            {"doc_id": "ddl", "title": "DDL表", "updated_at": 100},
            {"doc_id": "template", "title": "模板更新", "updated_at": 90},
        ]

        selected, candidates = choose_current_daily_document(docs, allow_non_daily_titles=True)
        self.assertEqual(selected["doc_id"], "ddl")
        self.assertEqual([item["doc_id"] for item in candidates], ["ddl", "template"])


class WritePathTests(unittest.TestCase):
    def test_node_path_to_api_path_expands_child_hops(self):
        self.assertEqual(node_path_to_api_path(("nodes", 3)), ["nodes", 3])
        self.assertEqual(
            node_path_to_api_path(("nodes", 3, 0, 2)),
            ["nodes", 3, "children", 0, "children", 2],
        )

    def test_normalize_user_record_extracts_auth_and_profile_fields(self):
        raw = {
            "id": 16166162,
            "|u": "jwt-token-value",
            "|i": "Example User",
            "|n": "15500000000",
            "|o": "https://document-image.mubu.com/photo/example.jpg",
            "|w": "20270221",
            "|h": 1773649029957,
            "_rev": "1-abc",
        }

        normalized = normalize_user_record(raw)
        self.assertEqual(normalized["user_id"], "16166162")
        self.assertEqual(normalized["token"], "jwt-token-value")
        self.assertEqual(normalized["display_name"], "Example User")
        self.assertEqual(normalized["phone"], "15500000000")
        self.assertEqual(normalized["updated_at"], 1773649029957)

    def test_latest_doc_member_context_picks_most_recent_member_id(self):
        events = [
            {"timestamp": "2026-03-17T17:18:40.006", "document_id": "doc-demo-01", "member_id": "old-member"},
            {"timestamp": "2026-03-17T18:32:48.609", "document_id": "other-doc", "member_id": "ignore-me"},
            {"timestamp": "2026-03-17T18:40:01.000", "document_id": "doc-demo-01", "member_id": "new-member"},
        ]

        context = latest_doc_member_context(events, "doc-demo-01")
        self.assertEqual(context["member_id"], "new-member")
        self.assertEqual(context["last_seen_at"], "2026-03-17T18:40:01.000")

    def test_build_api_headers_matches_desktop_shape(self):
        user = {"user_id": "16166162", "token": "jwt-token-value"}

        headers = build_api_headers(user, platform_version="10.0.26100")
        self.assertEqual(headers["mubu-desktop"], "true")
        self.assertEqual(headers["platform"], "windows")
        self.assertEqual(headers["platform-version"], "10.0.26100")
        self.assertEqual(headers["User-Agent"], "windows Mubu Electron")
        self.assertEqual(headers["userId"], "16166162")
        self.assertEqual(headers["token"], "jwt-token-value")
        self.assertEqual(headers["Content-Type"], "application/json;")

    def test_build_text_update_request_builds_server_side_change_payload(self):
        node = {
            "id": "node-1",
            "text": [{"type": 1, "text": "简历做一下"}],
            "modified": 1773739119771,
        }

        request = build_text_update_request(
            doc_id="doc-demo-01",
            member_id="7992964417993318",
            version=256,
            node=node,
            path=("nodes", 3, "children", 0),
            new_text="简历做一下更新",
            modified_ms=1773744000000,
        )

        self.assertEqual(request["pathname"], "/v3/api/colla/events")
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["data"]["documentId"], "doc-demo-01")
        self.assertEqual(request["data"]["memberId"], "7992964417993318")
        self.assertEqual(request["data"]["version"], 256)
        event = request["data"]["events"][0]
        self.assertEqual(event["name"], "update")
        updated = event["updated"][0]
        self.assertEqual(updated["updated"]["id"], "node-1")
        self.assertEqual(updated["updated"]["text"], "<span>简历做一下更新</span>")
        self.assertEqual(updated["updated"]["modified"], 1773744000000)
        self.assertEqual(updated["original"]["text"], "<span>简历做一下</span>")
        self.assertEqual(updated["path"], ["nodes", 3, "children", 0])

    def test_build_create_child_request_builds_create_payload(self):
        parent_node = {
            "id": "node-demo1",
            "children": [
                {"id": "child-0"},
                {"id": "child-1"},
            ],
        }

        request = build_create_child_request(
            doc_id="doc-demo-01",
            member_id="7992964417993318",
            version=257,
            parent_node=parent_node,
            parent_path=("nodes", 3, 0),
            text="继续推进 create-child",
            note="先 dry-run",
            child_id="new-child-1",
            modified_ms=1773748000000,
        )

        self.assertEqual(request["pathname"], "/v3/api/colla/events")
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["data"]["documentId"], "doc-demo-01")
        self.assertEqual(request["data"]["memberId"], "7992964417993318")
        self.assertEqual(request["data"]["version"], 257)
        event = request["data"]["events"][0]
        self.assertEqual(event["name"], "create")
        created = event["created"][0]
        self.assertEqual(created["index"], 2)
        self.assertEqual(created["parentId"], "node-demo1")
        self.assertEqual(
            created["path"],
            ["nodes", 3, "children", 0, "children", 2],
        )
        self.assertEqual(created["node"]["id"], "new-child-1")
        self.assertEqual(created["node"]["taskStatus"], 0)
        self.assertEqual(created["node"]["text"], "<span>继续推进 create-child</span>")
        self.assertEqual(created["node"]["note"], "<span>先 dry-run</span>")
        self.assertEqual(created["node"]["modified"], 1773748000000)
        self.assertEqual(created["node"]["children"], [])
        self.assertTrue(created["node"]["forceUpdate"])

    def test_parent_context_for_nested_node_path_returns_parent_and_index(self):
        data = {
            "nodes": [
                {
                    "id": "root-1",
                    "children": [
                        {
                            "id": "child-1",
                            "children": [
                                {
                                    "id": "leaf-1",
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        parent_node, parent_path, index = parent_context_for_path(data, ("nodes", 0, 0, 0))
        self.assertEqual(parent_node["id"], "child-1")
        self.assertEqual(parent_path, ("nodes", 0, 0))
        self.assertEqual(index, 0)

    def test_parent_context_for_root_node_path_returns_none_parent(self):
        data = {
            "nodes": [
                {
                    "id": "root-1",
                    "children": [],
                }
            ]
        }

        parent_node, parent_path, index = parent_context_for_path(data, ("nodes", 0))
        self.assertIsNone(parent_node)
        self.assertIsNone(parent_path)
        self.assertEqual(index, 0)

    def test_build_delete_node_request_builds_delete_payload(self):
        node = {
            "id": "child-2",
            "modified": 1773757000000,
            "text": "<span>临时删除节点</span>",
            "note": "<span>delete dry-run</span>",
            "children": [],
        }
        parent_node = {
            "id": "node-demo1",
        }

        request = build_delete_node_request(
            doc_id="doc-demo-01",
            member_id="7992964417993318",
            version=258,
            node=node,
            path=("nodes", 3, 0, 2),
            parent_node=parent_node,
        )

        self.assertEqual(request["pathname"], "/v3/api/colla/events")
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["data"]["documentId"], "doc-demo-01")
        self.assertEqual(request["data"]["memberId"], "7992964417993318")
        self.assertEqual(request["data"]["version"], 258)
        event = request["data"]["events"][0]
        self.assertEqual(event["name"], "delete")
        deleted = event["deleted"][0]
        self.assertEqual(deleted["parentId"], "node-demo1")
        self.assertEqual(deleted["index"], 2)
        self.assertEqual(
            deleted["path"],
            ["nodes", 3, "children", 0, "children", 2],
        )
        self.assertEqual(deleted["node"]["id"], "child-2")
        self.assertEqual(deleted["node"]["text"], "<span>临时删除节点</span>")
        self.assertEqual(deleted["node"]["note"], "<span>delete dry-run</span>")


if __name__ == "__main__":
    unittest.main()
