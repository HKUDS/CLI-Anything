"""Core function contract tests for mubu_probe.

Pure logic tests — no I/O, no network, no live Mubu API.
Covers utility and transformation functions not already exercised by test_mubu_probe.py.
"""

import json
import tempfile
import unittest
from pathlib import Path

from mubu_probe import (
    ambiguous_error_message,
    build_folder_indexes,
    candidate_appdata_roots,
    dedupe_latest_records,
    default_mubu_data_root,
    enrich_document_meta,
    extract_plain_text,
    generate_node_id,
    infer_title,
    iter_nodes,
    looks_like_daily_title,
    maybe_plain_text_to_html,
    node_path_to_api_path,
    normalize_document_meta_record,
    normalize_folder_record,
    normalized_lookup_key,
    numeric_values,
    parse_child_refs,
    parse_event_timestamp_ms,
    parse_revision_generation,
    plain_text_to_html,
    resolve_node_at_path,
    rich_text_to_html,
    serialize_node,
    timestamp_ms_to_iso,
)


class PlainTextExtractionTests(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(extract_plain_text(None), "")

    def test_dict_with_text_key(self):
        self.assertEqual(extract_plain_text({"text": "<b>hello</b>"}), "hello")

    def test_dict_without_text_key(self):
        self.assertEqual(extract_plain_text({"foo": "bar"}), "")

    def test_nested_segment_list(self):
        segments = [{"type": 1, "text": "A"}, {"type": 1, "text": "B"}]
        self.assertEqual(extract_plain_text(segments), "AB")

    def test_html_entity_unescaping(self):
        self.assertEqual(extract_plain_text("<span>a&amp;b</span>"), "a&b")

    def test_zero_width_chars_removed(self):
        self.assertEqual(extract_plain_text("<span>\u200bhello\u200b</span>"), "hello")


class HtmlConversionTests(unittest.TestCase):
    def test_plain_text_to_html_wraps_in_span(self):
        result = plain_text_to_html("hello world")
        self.assertIn("<span>hello world</span>", result)

    def test_maybe_plain_text_to_html_always_wraps(self):
        # maybe_plain_text_to_html wraps any input (including existing html) in a span
        result = maybe_plain_text_to_html("plain text")
        self.assertIn("<span>", result)
        self.assertIn("plain text", result)

    def test_rich_text_to_html_handles_segment_list(self):
        segments = [{"type": 1, "text": "hello"}, {"type": 1, "text": " world"}]
        result = rich_text_to_html(segments)
        self.assertIn("hello", result)
        self.assertIn("world", result)


class NodeIdGenerationTests(unittest.TestCase):
    def test_generates_string_of_expected_length(self):
        node_id = generate_node_id()
        self.assertIsInstance(node_id, str)
        self.assertEqual(len(node_id), 10)

    def test_generates_unique_ids(self):
        ids = {generate_node_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)


class NodePathConversionTests(unittest.TestCase):
    def test_single_level_path(self):
        self.assertEqual(node_path_to_api_path(("nodes", 0)), ["nodes", 0])

    def test_multi_level_path_inserts_children(self):
        self.assertEqual(
            node_path_to_api_path(("nodes", 1, 2, 3)),
            ["nodes", 1, "children", 2, "children", 3],
        )


class NodeIterationTests(unittest.TestCase):
    def test_iter_nodes_yields_all_nodes_depth_first(self):
        data = {
            "nodes": [
                {
                    "id": "a",
                    "text": "<span>A</span>",
                    "children": [
                        {"id": "b", "text": "<span>B</span>", "children": []},
                    ],
                },
                {"id": "c", "text": "<span>C</span>", "children": []},
            ]
        }
        ids = [node["id"] for _, node in iter_nodes(data["nodes"])]
        self.assertEqual(ids, ["a", "b", "c"])

    def test_iter_nodes_provides_correct_paths(self):
        data = {
            "nodes": [
                {
                    "id": "a",
                    "children": [
                        {"id": "b", "children": []},
                    ],
                },
            ]
        }
        paths = [("nodes", *path) for path, _ in iter_nodes(data["nodes"])]
        self.assertEqual(paths, [("nodes", 0), ("nodes", 0, 0)])


class ResolveNodeAtPathTests(unittest.TestCase):
    def test_resolves_root_node(self):
        data = {"nodes": [{"id": "root", "children": []}]}
        node = resolve_node_at_path(data, ("nodes", 0))
        self.assertEqual(node["id"], "root")

    def test_resolves_nested_child(self):
        data = {
            "nodes": [
                {
                    "id": "root",
                    "children": [
                        {"id": "child", "children": []},
                    ],
                }
            ]
        }
        node = resolve_node_at_path(data, ("nodes", 0, 0))
        self.assertEqual(node["id"], "child")


class SerializeNodeTests(unittest.TestCase):
    def test_serialize_node_flattens_text(self):
        node = {
            "id": "n1",
            "text": "<span>hello</span>",
            "note": "<span>note</span>",
            "modified": 100,
            "children": [],
        }
        result = serialize_node(node, depth=0)
        self.assertEqual(result["id"], "n1")
        self.assertEqual(result["text"], "hello")
        self.assertEqual(result["note"], "note")
        self.assertEqual(result["modified"], 100)
        self.assertEqual(result["children"], [])


class FolderIndexTests(unittest.TestCase):
    def test_build_folder_indexes_creates_by_id_and_folder_paths(self):
        folders = [
            {"folder_id": "root", "name": "Root", "parent_id": "0"},
            {"folder_id": "child", "name": "Child", "parent_id": "root"},
        ]
        by_id, folder_paths = build_folder_indexes(folders)
        self.assertIn("root", by_id)
        self.assertIn("child", by_id)
        self.assertEqual(folder_paths.get("root"), "Root")
        self.assertEqual(folder_paths.get("child"), "Root/Child")


class DailyTitleTests(unittest.TestCase):
    def test_date_range_titles(self):
        self.assertTrue(looks_like_daily_title("26.03.16"))
        self.assertTrue(looks_like_daily_title("26.3.8-3.9"))

    def test_rejects_non_date_titles(self):
        self.assertFalse(looks_like_daily_title("DDL表"))
        self.assertFalse(looks_like_daily_title("模板更新"))

    def test_rejects_template_suffix(self):
        self.assertFalse(looks_like_daily_title("26.2.22模板更新"))


class NormalizationHelperTests(unittest.TestCase):
    def test_parse_child_refs_handles_json_string(self):
        raw = '[{"id":"a","type":"doc"},{"id":"b","type":"folder"}]'
        refs = parse_child_refs(raw)
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0]["id"], "a")

    def test_parse_child_refs_handles_list(self):
        refs = parse_child_refs([{"id": "x"}])
        self.assertEqual(refs[0]["id"], "x")

    def test_parse_child_refs_handles_empty(self):
        self.assertEqual(parse_child_refs(None), [])
        self.assertEqual(parse_child_refs(""), [])

    def test_normalized_lookup_key(self):
        self.assertEqual(normalized_lookup_key("Hello World"), "hello world")

    def test_numeric_values_extracts_ints(self):
        raw = {"|e": 100, "|z": "200", "|m": None, "other": "abc"}
        result = numeric_values(raw["|e"], raw["|z"], raw["|m"], raw["other"])
        self.assertEqual(result, [100])

    def test_parse_revision_generation(self):
        self.assertEqual(parse_revision_generation("2792-d896b5c6"), 2792)
        self.assertEqual(parse_revision_generation("invalid"), 0)
        self.assertEqual(parse_revision_generation(None), 0)


class TimestampConversionTests(unittest.TestCase):
    def test_timestamp_ms_to_iso(self):
        result = timestamp_ms_to_iso(1710000000000)
        self.assertIsInstance(result, str)
        # Timezone dependent; just check date is in March 2024
        self.assertIn("2024-03-", result)

    def test_parse_event_timestamp_ms(self):
        result = parse_event_timestamp_ms("2026-03-17T17:18:40.006")
        self.assertIsInstance(result, (int, float))
        self.assertGreater(result, 0)


class DefaultPathDiscoveryTests(unittest.TestCase):
    def test_candidate_appdata_roots_prefers_explicit_environment(self):
        env = {
            "APPDATA": "/tmp/appdata",
            "USERPROFILE": "/tmp/profile",
            "USER": "alice",
        }
        candidates = candidate_appdata_roots(env=env, home=Path("/home/alice"), mount_root=Path("/tmp/users"))
        self.assertEqual(candidates[0], Path("/tmp/appdata"))
        self.assertIn(Path("/tmp/profile/AppData/Roaming"), candidates)
        self.assertIn(Path("/tmp/users/alice/AppData/Roaming"), candidates)

    def test_default_mubu_data_root_uses_first_existing_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mount_root = Path(tmpdir) / "Users"
            roaming = mount_root / "alice" / "AppData" / "Roaming"
            roaming.mkdir(parents=True)
            root = default_mubu_data_root(env={}, home=Path("/home/alice"), mount_root=mount_root)
            self.assertEqual(root, roaming / "Mubu" / "mubu_app_data" / "mubu_data")


class DedupeLatestRecordsTests(unittest.TestCase):
    def test_keeps_highest_revision(self):
        records = [
            {"id": "a", "_rev": "1-abc"},
            {"id": "a", "_rev": "3-def"},
            {"id": "a", "_rev": "2-ghi"},
            {"id": "b", "_rev": "1-xyz"},
        ]
        result = dedupe_latest_records(records)
        by_id = {r["id"]: r for r in result}
        self.assertEqual(len(result), 2)
        self.assertEqual(by_id["a"]["_rev"], "3-def")


class AmbiguousErrorMessageTests(unittest.TestCase):
    def test_formats_readable_message(self):
        candidates = [
            {"path": "Workspace/Daily tasks"},
            {"path": "Archive/Daily tasks"},
        ]
        msg = ambiguous_error_message("folder", "Daily tasks", candidates, "path")
        self.assertIn("Daily tasks", msg)
        self.assertIn("Workspace", msg)
        self.assertIn("Archive", msg)


class EnrichDocumentMetaTests(unittest.TestCase):
    def test_adds_folder_path(self):
        meta = {"doc_id": "d1", "folder_id": "f1", "title": "Doc"}
        folders = [
            {"folder_id": "root", "name": "Root", "parent_id": "0"},
            {"folder_id": "f1", "name": "Sub", "parent_id": "root"},
        ]
        _, folder_paths = build_folder_indexes(folders)
        enriched = enrich_document_meta(meta, folder_paths)
        self.assertIn("Sub", enriched.get("folder_path", ""))
        self.assertIn("Doc", enriched.get("doc_path", ""))


if __name__ == "__main__":
    unittest.main()
