"""Full end-to-end tests for cli-anything-mubu.

These tests invoke the CLI against real local Mubu desktop data.
They require the Mubu desktop app to have been used on this machine
so that backup, storage, and log directories exist.

Tests are skipped automatically when local data directories are missing.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]

# Import mubu_probe defaults for path detection
sys.path.insert(0, str(REPO_ROOT / "agent-harness"))
try:
    from mubu_probe import (
        DEFAULT_BACKUP_ROOT,
        DEFAULT_LOG_ROOT,
        DEFAULT_STORAGE_ROOT,
        build_folder_indexes,
        choose_current_daily_document,
        load_document_metas,
        load_folders,
    )
finally:
    sys.path.pop(0)

HAS_LOCAL_DATA = (
    DEFAULT_BACKUP_ROOT.is_dir()
    and DEFAULT_STORAGE_ROOT.is_dir()
)


def detect_daily_folder_ref() -> str | None:
    if not HAS_LOCAL_DATA:
        return None

    metas = load_document_metas(DEFAULT_STORAGE_ROOT)
    folders = load_folders(DEFAULT_STORAGE_ROOT)
    _, folder_paths = build_folder_indexes(folders)
    docs_by_folder: dict[str, list[dict[str, object]]] = {}
    for meta in metas:
        folder_id = meta.get("folder_id")
        if isinstance(folder_id, str):
            docs_by_folder.setdefault(folder_id, []).append(meta)

    best_path: str | None = None
    best_score = -1
    for folder in folders:
        folder_id = folder.get("folder_id")
        if not isinstance(folder_id, str):
            continue
        _, candidates = choose_current_daily_document(docs_by_folder.get(folder_id, []))
        if not candidates:
            continue
        folder_path = folder_paths.get(folder_id, "")
        if not folder_path:
            continue
        score = max(
            max(item.get("updated_at") or 0, item.get("created_at") or 0)
            for item in candidates
        )
        if score > best_score:
            best_score = score
            best_path = folder_path
    return best_path


DETECTED_DAILY_FOLDER_REF = detect_daily_folder_ref()
HAS_DAILY_FOLDER = HAS_LOCAL_DATA and DETECTED_DAILY_FOLDER_REF is not None

SKIP_REASON = "Mubu local data or a daily-style folder was not found"
LIVE_API_SKIP_MARKERS = (
    "CERTIFICATE_VERIFY_FAILED",
    "SSLCertVerificationError",
    "Hostname mismatch",
    "request failed for https://api2.mubu.com",
    "urlopen error",
)


def assert_cli_success_or_skip(testcase: unittest.TestCase, result: subprocess.CompletedProcess) -> None:
    if result.returncode == 0:
        return
    details = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if any(marker in details for marker in LIVE_API_SKIP_MARKERS):
        testcase.skipTest(f"live Mubu API unavailable in this environment: {details.splitlines()[-1]}")
    testcase.fail(details or f"CLI exited with status {result.returncode}")


def resolve_cli() -> list[str]:
    installed = shutil.which("cli-anything-mubu")
    if installed:
        return [installed]
    return [sys.executable, "-m", "cli_anything.mubu"]


@unittest.skipUnless(HAS_DAILY_FOLDER, SKIP_REASON)
class DiscoverE2ETests(unittest.TestCase):
    CLI_BASE = resolve_cli()

    def run_cli(self, args: list[str], extra_env: dict | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_docs_returns_json_list(self):
        result = self.run_cli(["docs", "--limit", "3", "--json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn("doc_id", data[0])

    def test_folders_returns_json_list(self):
        result = self.run_cli(["folders", "--json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn("folder_id", data[0])

    def test_recent_returns_json_list(self):
        result = self.run_cli(["recent", "--limit", "3", "--json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_daily_current_returns_doc_path(self):
        result = self.run_cli(
            ["daily-current", "--json"],
            extra_env={"MUBU_DAILY_FOLDER": DETECTED_DAILY_FOLDER_REF},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        # Response wraps document info in a nested structure
        doc = data.get("document", data)
        self.assertIn("doc_path", doc)
        self.assertIn(DETECTED_DAILY_FOLDER_REF, doc["doc_path"])


@unittest.skipUnless(HAS_DAILY_FOLDER, SKIP_REASON)
class InspectE2ETests(unittest.TestCase):
    CLI_BASE = resolve_cli()

    def run_cli(self, args: list[str], extra_env: dict | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_search_finds_results(self):
        result = self.run_cli(["search", "日", "--limit", "3", "--json"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)

    def test_daily_nodes_returns_node_list(self):
        result = self.run_cli(
            ["daily-nodes", "--json"],
            extra_env={"MUBU_DAILY_FOLDER": DETECTED_DAILY_FOLDER_REF},
        )
        assert_cli_success_or_skip(self, result)
        data = json.loads(result.stdout)
        self.assertIn("nodes", data)
        self.assertIsInstance(data["nodes"], list)


@unittest.skipUnless(HAS_DAILY_FOLDER, SKIP_REASON)
class SessionE2ETests(unittest.TestCase):
    CLI_BASE = resolve_cli()

    def run_cli(self, args: list[str], input_text: str | None = None, extra_env: dict | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            self.CLI_BASE + args,
            input=input_text,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def test_session_use_daily_sets_current_doc(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "CLI_ANYTHING_MUBU_STATE_DIR": tmpdir,
                "MUBU_DAILY_FOLDER": DETECTED_DAILY_FOLDER_REF,
            }
            self.run_cli(["session", "use-daily"], extra_env=env)
            result = self.run_cli(["session", "status", "--json"], extra_env=env)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            data = json.loads(result.stdout)
            self.assertIsNotNone(data.get("current_doc"))
            self.assertIn(DETECTED_DAILY_FOLDER_REF, data["current_doc"])

    def test_repl_use_daily_then_daily_nodes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "CLI_ANYTHING_MUBU_STATE_DIR": tmpdir,
                "MUBU_DAILY_FOLDER": DETECTED_DAILY_FOLDER_REF,
            }
            result = self.run_cli(
                [],
                input_text="use-daily\ndaily-nodes --json\nexit\n",
                extra_env=env,
            )
            assert_cli_success_or_skip(self, result)
            self.assertIn('"nodes"', result.stdout)


@unittest.skipUnless(HAS_DAILY_FOLDER, SKIP_REASON)
class MutateDryRunE2ETests(unittest.TestCase):
    """Test mutation commands in dry-run mode (no --execute)."""

    CLI_BASE = resolve_cli()

    def run_cli(self, args: list[str], extra_env: dict | None = None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    def _resolve_daily_node(self) -> tuple[str, str]:
        """Helper: get a stable daily document reference and first node id."""
        result = self.run_cli(
            ["daily-nodes", "--json"],
            extra_env={"MUBU_DAILY_FOLDER": DETECTED_DAILY_FOLDER_REF},
        )
        assert_cli_success_or_skip(self, result)
        data = json.loads(result.stdout)
        doc = data.get("document", data)
        doc_ref = doc.get("doc_id") or doc["doc_path"]
        node_id = data["nodes"][0]["node_id"]
        return doc_ref, node_id

    def test_update_text_dry_run(self):
        doc_ref, node_id = self._resolve_daily_node()
        result = self.run_cli([
            "update-text", doc_ref,
            "--node-id", node_id,
            "--text", "dry run test",
            "--json",
        ])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("request", data)
        self.assertFalse(data.get("executed", False))

    def test_create_child_dry_run(self):
        doc_ref, node_id = self._resolve_daily_node()
        result = self.run_cli([
            "create-child", doc_ref,
            "--parent-node-id", node_id,
            "--text", "dry run child",
            "--json",
        ])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("request", data)
        self.assertFalse(data.get("executed", False))

    def test_delete_node_dry_run(self):
        doc_ref, node_id = self._resolve_daily_node()
        result = self.run_cli([
            "delete-node", doc_ref,
            "--node-id", node_id,
            "--json",
        ])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data.get("executed", False))


if __name__ == "__main__":
    unittest.main()
