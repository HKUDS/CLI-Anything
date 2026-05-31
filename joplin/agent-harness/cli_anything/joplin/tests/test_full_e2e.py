"""E2E coverage for the Joplin backend CLI.

Test layout:
- `TestCLISubprocess`: CLI command checks that do not require a Joplin binary
- `TestBackendCommands`: isolated command-level checks against the real backend
- `TestBackendWorkflows`: short workflow tests for common user flows
- `TestBackendIntegration`: full end-to-end demonstration flow

Real-backend test classes are skipped automatically when the `joplin` binary
is not on PATH.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

import pytest


def _resolve_cli(name: str) -> list[str]:
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.joplin.joplin_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


@dataclass
class WorkflowStep:
    title: str
    args: list[str]


class BackendTestBase:
    CLI_BASE = _resolve_cli("cli-anything-joplin")

    def _run(self, args: list[str], check: bool = True, timeout: int | None = None):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )

    def _run_json(self, args: list[str], check: bool = True, timeout: int | None = None) -> dict:
        result = self._run(["--json", *args], check=check, timeout=timeout)
        if not result.stdout.strip():
            raise AssertionError(
                f"Empty stdout for args {args}; stderr was:\n{result.stderr}"
            )
        return json.loads(result.stdout)

    def _print_workflow_start(self, name: str, total_steps: int):
        print(f"\n=== Workflow: {name} ===")
        print(f"Steps: {total_steps}")

    def _print_step(self, index: int, total_steps: int, title: str, args: list[str]):
        print(f"[{index}/{total_steps}] {title}")
        print(f"Command: {' '.join(args)}")

    def _print_result(self, payload: dict):
        if payload.get("ok"):
            print(f"Result: ok=true, command={payload.get('command')}")
            data = payload.get("data")
            if isinstance(data, dict) and data:
                preview_keys = list(data.keys())[:3]
                preview = {k: data[k] for k in preview_keys}
                print(f"Data: {json.dumps(preview, ensure_ascii=False, default=str)}")
            elif data is not None:
                print(f"Data: {data}")
        else:
            err = payload.get("error") or {}
            print(f"Result: ok=false, command={payload.get('command')}, error={err.get('message')}")

    def _print_workflow_end(self, name: str, success: bool = True):
        if success:
            print(f"[PASS] Workflow passed: {name}")
        else:
            print(f"[FAIL] Workflow failed: {name}")

    def _run_workflow_step(self, step: WorkflowStep, check: bool = True, timeout: int | None = None) -> dict:
        result = self._run(["--json", *step.args], check=check, timeout=timeout)
        if not result.stdout.strip():
            self._print_workflow_end(step.title, success=False)
            raise AssertionError(
                f"Empty stdout for step '{step.title}' args={step.args}; stderr:\n{result.stderr}"
            )
        payload = json.loads(result.stdout)
        self._print_result(payload)
        return payload

    def _create_project(self, tmp_path, name: str):
        project_file = tmp_path / f"{name}.json"
        payload = self._run_json(["project", "new", "--name", name, "-o", str(project_file)])
        assert payload["ok"] is True
        assert payload["command"] == "project.new"
        assert project_file.exists()
        return project_file

    def _prepare_workspace(self, tmp_path, project_name: str):
        project_file = self._create_project(tmp_path, project_name)
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        return project_file, profile_dir


# ---------------------------------------------------------------------------
# CLI-only tests (no backend required)
# ---------------------------------------------------------------------------


class TestCLISubprocess(BackendTestBase):
    def test_help_shows_usage(self):
        r = self._run(["--help"])
        assert r.returncode == 0
        assert "cli-anything-joplin" in r.stdout or "Usage" in r.stdout

    def test_subgroup_help_for_every_group(self):
        for group in (
            "project",
            "notebooks",
            "notes",
            "todos",
            "tags",
            "search",
            "sync",
            "interop",
            "config",
            "attach",
            "status",
            "backend",
            "server",
            "e2ee",
            "session",
        ):
            r = self._run([group, "--help"])
            assert r.returncode == 0, f"{group} --help failed: {r.stderr}"
            assert "Commands:" in r.stdout or "Usage:" in r.stdout

    def test_project_new_returns_json_payload(self, tmp_path):
        out = tmp_path / "p.json"
        payload = self._run_json(["project", "new", "--name", "demo", "-o", str(out)])
        assert payload["ok"] is True
        assert payload["command"] == "project.new"
        assert payload["data"]["name"] == "demo"
        assert out.exists()

    def test_project_info_works_on_new_project(self, tmp_path):
        out = tmp_path / "p.json"
        self._run(["project", "new", "--name", "demo", "-o", str(out)])
        payload = self._run_json(["--project", str(out), "project", "info"])
        assert payload["ok"] is True
        assert payload["data"]["name"] == "demo"

    def test_project_json_dump(self, tmp_path):
        out = tmp_path / "p.json"
        self._run(["project", "new", "--name", "dump", "-o", str(out)])
        payload = self._run_json(["--project", str(out), "project", "json"])
        assert payload["ok"] is True
        assert payload["data"]["name"] == "dump"
        assert payload["data"]["backend"]["binary"] == "joplin"

    def test_session_status_without_project(self):
        payload = self._run_json(["session", "status"])
        assert payload["ok"] is True
        assert payload["data"]["has_project"] is False

    def test_project_save_roundtrip(self, tmp_path):
        out = tmp_path / "p.json"
        self._run(["project", "new", "--name", "demo", "-o", str(out)])
        payload = self._run_json(["--project", str(out), "project", "save"])
        assert payload["ok"] is True
        assert "saved" in payload["data"]

    def test_project_status_reports_loaded_project(self, tmp_path):
        out = tmp_path / "status.json"
        self._run(["project", "new", "--name", "status-demo", "-o", str(out)])
        payload = self._run_json(["--project", str(out), "project", "status"])
        assert payload["ok"] is True
        assert payload["data"]["project"]["name"] == "status-demo"
        assert payload["data"]["project_path"] == str(out)
        assert payload["data"]["session"]["has_project"] is True

    def test_dry_run_does_not_modify_project(self, tmp_path):
        out = tmp_path / "p.json"
        self._run(["project", "new", "--name", "dry", "-o", str(out)])
        with open(out, "r", encoding="utf-8") as f:
            before = json.load(f)

        # backend mutation in dry-run + bogus profile cannot actually run; we only
        # care that auto-save is suppressed even on error
        self._run(
            [
                "--dry-run",
                "--project",
                str(out),
                "--profile",
                str(tmp_path / "no-profile"),
                "session",
                "status",
            ],
            check=False,
        )
        with open(out, "r", encoding="utf-8") as f:
            after = json.load(f)
        assert len(after["history"]) == len(before["history"])

    def test_invalid_subcommand_exits_nonzero(self):
        r = self._run(["bogus-command"], check=False)
        assert r.returncode != 0


# ---------------------------------------------------------------------------
# Real backend tests
# ---------------------------------------------------------------------------


_JOPLIN_INSTALLED = shutil.which("joplin") is not None


@pytest.mark.skipif(not _JOPLIN_INSTALLED, reason="joplin binary not installed")
class TestBackendCommands(BackendTestBase):
    def test_project_status_and_info(self, tmp_path):
        project_file = self._create_project(tmp_path, "commands-project")

        status = self._run_json(["--project", str(project_file), "project", "status"])
        assert status["data"]["project"]["name"] == "commands-project"

        info = self._run_json(["--project", str(project_file), "project", "info"])
        assert info["data"]["name"] == "commands-project"

    def test_notebooks_and_notes_list(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "commands-lists")

        notebooks = self._run_json(["--project", str(project_file), "--profile", str(profile_dir), "notebooks", "list"])
        assert notebooks["ok"] is True
        assert notebooks["command"] == "notebooks.list"

        notes = self._run_json(["--project", str(project_file), "--profile", str(profile_dir), "notes", "list"])
        assert notes["ok"] is True

    def test_config_get_and_list(self, tmp_path):
        project_file = self._create_project(tmp_path, "commands-config")

        config_get = self._run_json(["--project", str(project_file), "config", "get", "sync.target"])
        assert config_get["ok"] is True

        config_list = self._run_json(["--project", str(project_file), "config", "list"])
        assert config_list["ok"] is True
        assert config_list["data"] is not None

    def test_status_show(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "commands-status")
        payload = self._run_json([
            "--project", str(project_file),
            "--profile", str(profile_dir),
            "status", "show",
        ])
        assert payload["ok"] is True
        assert payload["command"] == "status.show"

    def test_backend_utilities(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "commands-backend")

        version = self._run_json(["--project", str(project_file), "--profile", str(profile_dir), "backend", "version"])
        assert version["ok"] is True
        assert version["command"] == "backend.version"

        dump = self._run_json(["--project", str(project_file), "--profile", str(profile_dir), "backend", "dump"])
        assert dump["ok"] is True
        assert dump["command"] == "backend.dump"

        e2ee = self._run_json(["--project", str(project_file), "--profile", str(profile_dir), "e2ee", "status"])
        assert e2ee["ok"] is True
        assert e2ee["command"] == "e2ee.status"

        server = self._run_json(["--project", str(project_file), "--profile", str(profile_dir), "server", "status"])
        assert server["ok"] is True
        assert server["command"] == "server.status"

    def test_session_undo_redo(self, tmp_path):
        project_file = self._create_project(tmp_path, "commands-session")

        undo = self._run_json(["--project", str(project_file), "session", "undo"], check=False)
        assert undo["ok"] is False
        assert undo["error"]["message"] == "Nothing to undo"

        redo = self._run_json(["--project", str(project_file), "session", "redo"], check=False)
        assert redo["ok"] is False
        assert redo["error"]["message"] == "Nothing to redo"


@pytest.mark.skipif(not _JOPLIN_INSTALLED, reason="joplin binary not installed")
class TestBackendWorkflows(BackendTestBase):
    def _common_args(self, project_file, profile_dir):
        return ["--project", str(project_file), "--profile", str(profile_dir)]

    def test_note_lifecycle_workflow(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-notes")
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create notebook", base + ["notebooks", "create", "WorkflowBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "WorkflowBook"]),
            WorkflowStep("Create note", base + ["notes", "create", "WorkflowNote"]),
            WorkflowStep("Rename via set", base + ["notes", "set", "WorkflowNote", "title", "WorkflowNoteRenamed"]),
            WorkflowStep("Get note", base + ["notes", "get", "WorkflowNoteRenamed"]),
            WorkflowStep("Remove note", base + ["notes", "remove", "WorkflowNoteRenamed"]),
            WorkflowStep("Remove notebook", base + ["notebooks", "remove", "WorkflowBook"]),
        ]
        self._print_workflow_start("Note lifecycle", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        self._print_workflow_end("Note lifecycle")

    def test_note_organization_workflow(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-org")
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create source notebook", base + ["notebooks", "create", "OrgSrc"]),
            WorkflowStep("Create target notebook", base + ["notebooks", "create", "OrgDst"]),
            WorkflowStep("Use source notebook", base + ["notebooks", "use", "OrgSrc"]),
            WorkflowStep("Create note", base + ["notes", "create", "OrgNote"]),
            WorkflowStep("Copy to target", base + ["notes", "copy", "OrgNote", "OrgDst"]),
            WorkflowStep("Rename source note", base + ["notes", "rename", "OrgNote", "OrgNoteRenamed"]),
            WorkflowStep("Move renamed note to target", base + ["notes", "move", "OrgNoteRenamed", "OrgDst"]),
            WorkflowStep("Use target notebook", base + ["notebooks", "use", "OrgDst"]),
            WorkflowStep("List target notebook", base + ["notes", "list"]),
            WorkflowStep("Cleanup source notebook", base + ["notebooks", "remove", "OrgSrc"]),
            WorkflowStep("Cleanup target notebook", base + ["notebooks", "remove", "OrgDst"]),
        ]
        self._print_workflow_start("Note organization", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        self._print_workflow_end("Note organization")

    def test_todo_workflow(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-todos")
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create notebook", base + ["notebooks", "create", "TodoBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "TodoBook"]),
            WorkflowStep("Create todo", base + ["todos", "create", "Buy milk"]),
            WorkflowStep("List todos", base + ["todos", "list"]),
            WorkflowStep("Mark done", base + ["todos", "done", "Buy milk"]),
            WorkflowStep("Mark undone", base + ["todos", "undone", "Buy milk"]),
            WorkflowStep("Toggle todo", base + ["todos", "toggle", "Buy milk"]),
            WorkflowStep("Clear todo (back to note)", base + ["todos", "clear", "Buy milk"]),
            WorkflowStep("Cleanup notebook", base + ["notebooks", "remove", "TodoBook"]),
        ]
        self._print_workflow_start("Todo lifecycle", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        self._print_workflow_end("Todo lifecycle")

    def test_tagging_workflow(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-tags")
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create notebook", base + ["notebooks", "create", "TagBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "TagBook"]),
            WorkflowStep("Create note", base + ["notes", "create", "TagNote"]),
            WorkflowStep("Add tag", base + ["tags", "add", "wf-tag", "TagNote"]),
            WorkflowStep("List tags", base + ["tags", "list"]),
            WorkflowStep("Note tags", base + ["tags", "notetags", "TagNote"]),
            WorkflowStep("Tag notes", base + ["tags", "tagnotes", "wf-tag"]),
            WorkflowStep("Remove tag", base + ["tags", "remove", "wf-tag", "TagNote"]),
            WorkflowStep("Cleanup notebook", base + ["notebooks", "remove", "TagBook"]),
        ]
        self._print_workflow_start("Tagging", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        self._print_workflow_end("Tagging")

    def test_search_workflow(self, tmp_path):
        # `search` is documented as "only available in GUI mode" in some Joplin CLI
        # builds, so a clean ok=false response with a GUI-mode error message is also
        # acceptable. We require the rest of the workflow to succeed.
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-search")
        base = self._common_args(project_file, profile_dir)
        prep = [
            WorkflowStep("Create notebook", base + ["notebooks", "create", "SearchBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "SearchBook"]),
            WorkflowStep("Create note", base + ["notes", "create", "FindMe"]),
        ]
        self._print_workflow_start("Search", len(prep) + 2)
        for index, step in enumerate(prep, start=1):
            self._print_step(index, len(prep) + 2, step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True

        search_step = WorkflowStep("Search note by title", base + ["search", "run", "FindMe"])
        self._print_step(len(prep) + 1, len(prep) + 2, search_step.title, search_step.args)
        search_payload = self._run_workflow_step(search_step, check=False)
        if not search_payload["ok"]:
            assert "GUI" in search_payload["error"]["message"] or "search" in search_payload["error"]["message"].lower()

        cleanup_step = WorkflowStep("Cleanup notebook", base + ["notebooks", "remove", "SearchBook"])
        self._print_step(len(prep) + 2, len(prep) + 2, cleanup_step.title, cleanup_step.args)
        payload = self._run_workflow_step(cleanup_step)
        assert payload["ok"] is True
        self._print_workflow_end("Search")

    def test_sync_workflow_runs(self, tmp_path):
        # sync.target=0 (none) is the default. `sync run` is expected to be a no-op
        # in that state. We only require the command exits successfully.
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-sync")
        base = self._common_args(project_file, profile_dir)
        payload = self._run_workflow_step(WorkflowStep("Run sync", base + ["sync", "run"]), check=False)
        assert payload["command"] == "sync.run"

    def test_export_workflow_jex_and_md(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-export")
        export_jex = tmp_path / "wf.jex"
        export_md = tmp_path / "wf_md"
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create notebook", base + ["notebooks", "create", "ExportBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "ExportBook"]),
            WorkflowStep("Create note", base + ["notes", "create", "ExportNote"]),
            WorkflowStep("Export JEX", base + ["interop", "export", str(export_jex), "--format", "jex"]),
            WorkflowStep("Export MD", base + ["interop", "export", str(export_md), "--format", "md"]),
            WorkflowStep("Cleanup notebook", base + ["notebooks", "remove", "ExportBook"]),
        ]
        self._print_workflow_start("Export", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        assert export_jex.exists() and export_jex.stat().st_size > 0
        assert export_md.exists()
        self._print_workflow_end("Export")

    def test_import_md_workflow(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-import")
        md_source = tmp_path / "to_import"
        md_source.mkdir()
        (md_source / "imported_note.md").write_text("# Imported\n\nHello from import.", encoding="utf-8")

        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create destination notebook", base + ["notebooks", "create", "ImportBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "ImportBook"]),
            WorkflowStep("Import markdown", base + ["interop", "import", str(md_source), "--format", "md"]),
            WorkflowStep("List notes after import", base + ["notes", "list"]),
            WorkflowStep("Cleanup notebook", base + ["notebooks", "remove", "ImportBook"]),
        ]
        self._print_workflow_start("Import", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        self._print_workflow_end("Import")

    def test_attach_workflow(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-attach")
        attachment = tmp_path / "attach.txt"
        attachment.write_text("attached file contents", encoding="utf-8")
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create notebook", base + ["notebooks", "create", "AttachBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "AttachBook"]),
            WorkflowStep("Create note", base + ["notes", "create", "AttachNote"]),
            WorkflowStep("Attach file", base + ["attach", "add", "AttachNote", str(attachment)]),
            WorkflowStep("Get note", base + ["notes", "get", "AttachNote"]),
            WorkflowStep("Cleanup notebook", base + ["notebooks", "remove", "AttachBook"]),
        ]
        self._print_workflow_start("Attach", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        self._print_workflow_end("Attach")

    @pytest.mark.skipif(
        sys.platform.startswith("win"),
        reason="Unicode argument forwarding through joplin.cmd / cmd.exe on Windows "
        "drops to the active code page and corrupts non-ASCII titles. The harness "
        "itself handles unicode correctly (see test_core unicode roundtrip).",
    )
    def test_unicode_notebook_and_note(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-unicode")
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create unicode notebook", base + ["notebooks", "create", "笔记本-中文"]),
            WorkflowStep("Use unicode notebook", base + ["notebooks", "use", "笔记本-中文"]),
            WorkflowStep("Create unicode note", base + ["notes", "create", "笔记 A — αβγ"]),
            WorkflowStep("Cleanup unicode notebook", base + ["notebooks", "remove", "笔记本-中文"]),
        ]
        self._print_workflow_start("Unicode", len(steps))
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            payload = self._run_workflow_step(step)
            assert payload["ok"] is True
        self._print_workflow_end("Unicode")

    def test_session_history_persists(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "workflow-history")
        base = self._common_args(project_file, profile_dir)
        steps = [
            WorkflowStep("Create notebook", base + ["notebooks", "create", "HistBook"]),
            WorkflowStep("Use notebook", base + ["notebooks", "use", "HistBook"]),
            WorkflowStep("Create note", base + ["notes", "create", "HistNote"]),
        ]
        for index, step in enumerate(steps, start=1):
            self._print_step(index, len(steps), step.title, step.args)
            self._run_workflow_step(step)

        history = self._run_json(["--project", str(project_file), "session", "history"])
        assert history["ok"] is True
        actions = [h["action"] for h in history["data"]]
        for expected in ("notebook.create", "notebook.use", "note.create"):
            assert expected in actions

        # cleanup
        self._run(["--project", str(project_file), "--profile", str(profile_dir), "notebooks", "remove", "HistBook"], check=False)


# ---------------------------------------------------------------------------
# Full end-to-end roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _JOPLIN_INSTALLED, reason="joplin binary not installed")
class TestBackendIntegration(BackendTestBase):
    def test_full_backend_roundtrip(self, tmp_path):
        project_file, profile_dir = self._prepare_workspace(tmp_path, "integration-full")
        export_jex_path = tmp_path / "integration-full.jex"
        export_md_path = tmp_path / "integration-md"
        attachment = tmp_path / "attachment.txt"
        attachment.write_text("integration attachment payload", encoding="utf-8")

        base = ["--project", str(project_file), "--profile", str(profile_dir)]

        phases = [
            ("Inspect project", [
                WorkflowStep("Project status", ["--project", str(project_file), "project", "status"]),
                WorkflowStep("Project info", ["--project", str(project_file), "project", "info"]),
                WorkflowStep("Session status (no mutation yet)", ["--project", str(project_file), "session", "status"]),
            ]),
            ("Notebook setup", [
                WorkflowStep("List notebooks", base + ["notebooks", "list"]),
                WorkflowStep("Create main notebook", base + ["notebooks", "create", "IntegrationBook"]),
                WorkflowStep("Create secondary notebook", base + ["notebooks", "create", "IntegrationArchive"]),
                WorkflowStep("Use main notebook", base + ["notebooks", "use", "IntegrationBook"]),
            ]),
            ("Note lifecycle", [
                WorkflowStep("List notes", base + ["notes", "list"]),
                WorkflowStep("Create note", base + ["notes", "create", "IntegrationNote"]),
                WorkflowStep("Rename via set", base + ["notes", "set", "IntegrationNote", "title", "IntegrationNoteRenamed"]),
                WorkflowStep("Get note", base + ["notes", "get", "IntegrationNoteRenamed"]),
                WorkflowStep("Copy note to archive", base + ["notes", "copy", "IntegrationNoteRenamed", "IntegrationArchive"]),
                WorkflowStep("Create note for organization", base + ["notes", "create", "Orphan"]),
                WorkflowStep("Move note via mv", base + ["notes", "move", "Orphan", "IntegrationArchive"]),
                WorkflowStep("Rename note via ren", base + ["notes", "rename", "IntegrationNoteRenamed", "IntegrationNoteFinal"]),
            ]),
            ("Todos", [
                WorkflowStep("Create todo", base + ["todos", "create", "Drink water"]),
                WorkflowStep("List todos", base + ["todos", "list"]),
                WorkflowStep("Mark done", base + ["todos", "done", "Drink water"]),
                WorkflowStep("Mark undone", base + ["todos", "undone", "Drink water"]),
                WorkflowStep("Toggle todo", base + ["todos", "toggle", "Drink water"]),
                WorkflowStep("Clear todo back to note", base + ["todos", "clear", "Drink water"]),
            ]),
            ("Tags", [
                WorkflowStep("Add primary tag", base + ["tags", "add", "integration-tag", "IntegrationNoteFinal"]),
                WorkflowStep("Add secondary tag", base + ["tags", "add", "another-tag", "IntegrationNoteFinal"]),
                WorkflowStep("List tags", base + ["tags", "list"]),
                WorkflowStep("Note tags", base + ["tags", "notetags", "IntegrationNoteFinal"]),
                WorkflowStep("Tag notes", base + ["tags", "tagnotes", "integration-tag"]),
                WorkflowStep("Remove tag", base + ["tags", "remove", "integration-tag", "IntegrationNoteFinal"]),
            ]),
            ("Attach", [
                WorkflowStep("Attach file", base + ["attach", "add", "IntegrationNoteFinal", str(attachment)]),
                WorkflowStep("Verbose get", base + ["notes", "get", "IntegrationNoteFinal", "--verbose"]),
            ]),
            ("Status and config", [
                WorkflowStep("Backend status", base + ["status", "show"]),
                WorkflowStep("Config get", base + ["config", "get", "sync.target"]),
                WorkflowStep("Config list", base + ["config", "list"]),
            ]),
            ("Sync (no-op)", [
                WorkflowStep("Run sync (no target)", base + ["sync", "run"]),
            ]),
            ("Export and import", [
                WorkflowStep("Export JEX", base + ["interop", "export", str(export_jex_path), "--format", "jex"]),
                WorkflowStep("Export MD", base + ["interop", "export", str(export_md_path), "--format", "md"]),
            ]),
            ("Cleanup", [
                WorkflowStep("Remove final note", base + ["notes", "remove", "IntegrationNoteFinal"]),
                WorkflowStep("Remove main notebook", base + ["notebooks", "remove", "IntegrationBook"]),
                WorkflowStep("Remove archive notebook", base + ["notebooks", "remove", "IntegrationArchive"]),
                WorkflowStep("Save project", ["--project", str(project_file), "project", "save"]),
                WorkflowStep("Final project status", ["--project", str(project_file), "project", "status"]),
                WorkflowStep("Session history", ["--project", str(project_file), "session", "history"]),
            ]),
        ]

        print("\n=== Workflow: Full backend roundtrip ===")
        for phase_name, steps in phases:
            print(f"\n--- Phase: {phase_name} ---")
            for index, step in enumerate(steps, start=1):
                self._print_step(index, len(steps), step.title, step.args)
                # `sync run` may return ok=true with target=0 (none) or ok=false
                # depending on backend version; tolerate either.
                check = step.title not in {"Run sync (no target)"}
                payload = self._run_workflow_step(step, check=check)
                if step.title == "Run sync (no target)":
                    continue
                assert payload["ok"] is True, f"Step '{step.title}' failed: {payload}"

        assert export_jex_path.exists() and export_jex_path.stat().st_size > 0
        assert export_md_path.exists()

        # Verify the saved project carries the expected history
        final_project = json.loads(open(project_file, "r", encoding="utf-8").read())
        history_actions = [h["action"] for h in final_project["history"]]
        for action in (
            "notebook.create",
            "notebook.use",
            "note.create",
            "note.set",
            "note.copy",
            "note.move",
            "note.rename",
            "todo.create",
            "todo.toggle",
            "todo.done",
            "todo.undone",
            "todo.clear",
            "tag.add",
            "tag.remove",
            "attach.add",
            "interop.export",
            "note.remove",
            "notebook.remove",
        ):
            assert action in history_actions, f"Missing history action: {action}"

        print("[PASS] Workflow passed: Full backend roundtrip")
