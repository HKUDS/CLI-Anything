"""Unit tests for MacroCLI core modules.

Covers: MacroDefinition, MacroRegistry, MacroRuntime, backends, routing.
All tests use synthetic data and do not require external software.
"""

import json
import os
import sys
import textwrap
import tempfile
from pathlib import Path

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

SIMPLE_MACRO_YAML = textwrap.dedent("""\
    name: test_macro
    version: "1.0"
    description: A test macro.
    parameters:
      output:
        type: string
        required: true
        description: Output path
      count:
        type: integer
        required: false
        default: 1
        min: 1
        max: 100
    steps:
      - id: step1
        backend: native_api
        action: run_command
        params:
          command: [echo, hello]
    postconditions: []
""")


def write_macro(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / f"{name}.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ── macro_model tests ─────────────────────────────────────────────────────────

class TestMacroModel:
    def test_load_from_yaml(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        p = write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        m = load_from_yaml(str(p))
        assert m.name == "test_macro"
        assert m.version == "1.0"
        assert "output" in m.parameters
        assert len(m.steps) == 1
        assert m.steps[0].backend == "native_api"

    def test_load_missing_file(self):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        with pytest.raises(FileNotFoundError):
            load_from_yaml("/nonexistent/path.yaml")

    def test_validate_params_required(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        p = write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        m = load_from_yaml(str(p))
        errors = m.validate_params({})
        assert any("output" in e for e in errors)

    def test_validate_params_type_error(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        p = write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        m = load_from_yaml(str(p))
        errors = m.validate_params({"output": "/tmp/x", "count": "not_an_int"})
        assert any("count" in e for e in errors)

    def test_validate_params_range(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        p = write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        m = load_from_yaml(str(p))
        errors = m.validate_params({"output": "/tmp/x", "count": 200})
        assert any("count" in e for e in errors)

    def test_validate_params_ok(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        p = write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        m = load_from_yaml(str(p))
        errors = m.validate_params({"output": "/tmp/x"})
        assert errors == []

    def test_resolve_params_defaults(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        p = write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        m = load_from_yaml(str(p))
        resolved = m.resolve_params({"output": "/tmp/x"})
        assert resolved["count"] == 1

    def test_structural_validation_no_steps(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        yaml_content = "name: bad\nsteps: []\n"
        p = write_macro(tmp_path, "bad", yaml_content)
        m = load_from_yaml(str(p))
        errors = m.validate()
        assert any("steps" in e for e in errors)

    def test_structural_validation_bad_backend(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        yaml_content = textwrap.dedent("""\
            name: bad
            steps:
              - id: x
                backend: fake_backend
                action: do_thing
        """)
        p = write_macro(tmp_path, "bad_backend", yaml_content)
        m = load_from_yaml(str(p))
        errors = m.validate()
        assert any("fake_backend" in e for e in errors)

    def test_to_dict(self, tmp_path):
        from cli_anything.macrocli.core.macro_model import load_from_yaml
        p = write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        m = load_from_yaml(str(p))
        d = m.to_dict()
        assert d["name"] == "test_macro"
        assert "parameters" in d
        assert "steps" in d


class TestSubstitute:
    def test_string_substitution(self):
        from cli_anything.macrocli.core.macro_model import substitute
        result = substitute("hello ${name}", {"name": "world"})
        assert result == "hello world"

    def test_nested_list(self):
        from cli_anything.macrocli.core.macro_model import substitute
        result = substitute(["echo", "${output}"], {"output": "/tmp/x"})
        assert result == ["echo", "/tmp/x"]

    def test_nested_dict(self):
        from cli_anything.macrocli.core.macro_model import substitute
        result = substitute({"path": "${output}", "other": 42}, {"output": "/out"})
        assert result["path"] == "/out"
        assert result["other"] == 42

    def test_missing_key_left_as_is(self):
        from cli_anything.macrocli.core.macro_model import substitute
        result = substitute("${missing}", {})
        assert result == "${missing}"


# ── MacroRegistry tests ───────────────────────────────────────────────────────

class TestMacroRegistry:
    def test_load_macro(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        reg = MacroRegistry(str(tmp_path))
        m = reg.load("test_macro")
        assert m.name == "test_macro"

    def test_load_missing_raises(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        reg = MacroRegistry(str(tmp_path))
        with pytest.raises(KeyError):
            reg.load("nonexistent_macro")

    def test_list_all(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        write_macro(tmp_path, "another", SIMPLE_MACRO_YAML.replace("test_macro", "another"))
        reg = MacroRegistry(str(tmp_path))
        names = reg.list_names()
        assert "test_macro" in names
        assert "another" in names

    def test_manifest_index(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        sub = tmp_path / "sub"
        sub.mkdir()
        write_macro(sub, "alpha", SIMPLE_MACRO_YAML.replace("test_macro", "alpha"))
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text("macros:\n  - name: alpha\n    path: sub/alpha.yaml\n")
        reg = MacroRegistry(str(tmp_path))
        m = reg.load("alpha")
        assert m.name == "alpha"

    def test_register_programmatic(self):
        from cli_anything.macrocli.core.registry import MacroRegistry
        from cli_anything.macrocli.core.macro_model import MacroDefinition, MacroStep
        reg = MacroRegistry("/nonexistent")
        macro = MacroDefinition(
            name="inline_macro",
            steps=[MacroStep(backend="native_api", action="run_command")],
        )
        reg.register(macro)
        assert reg.load("inline_macro").name == "inline_macro"

    def test_info(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        write_macro(tmp_path, "test_macro", SIMPLE_MACRO_YAML)
        reg = MacroRegistry(str(tmp_path))
        info = reg.info()
        assert info["total"] >= 1
        assert "macros_dir" in info


# ── Backend tests ─────────────────────────────────────────────────────────────

class TestNativeAPIBackend:
    def _make_context(self, params=None):
        from cli_anything.macrocli.backends.base import BackendContext
        return BackendContext(params=params or {})

    def _make_step(self, action, step_params):
        from cli_anything.macrocli.core.macro_model import MacroStep
        return MacroStep(id="test", backend="native_api", action=action, params=step_params)

    def test_run_command_success(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        b = NativeAPIBackend()
        step = self._make_step("run_command", {"command": ["echo", "hello"]})
        result = b.execute(step, {}, self._make_context())
        assert result.success

    def test_run_command_fails_bad_exit(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        b = NativeAPIBackend()
        step = self._make_step("run_command", {"command": ["false"]})
        result = b.execute(step, {}, self._make_context())
        assert not result.success
        assert "exit" in result.error.lower() or "failed" in result.error.lower()

    def test_run_command_not_found(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        b = NativeAPIBackend()
        step = self._make_step("run_command", {"command": ["__nonexistent_cmd__"]})
        result = b.execute(step, {}, self._make_context())
        assert not result.success

    def test_find_executable_found(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        b = NativeAPIBackend()
        step = self._make_step("find_executable", {"name": "echo"})
        result = b.execute(step, {}, self._make_context())
        assert result.success
        assert "executable" in result.output

    def test_find_executable_missing(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        b = NativeAPIBackend()
        step = self._make_step("find_executable", {
            "name": "__nonexistent__",
            "install_hint": "brew install nonexistent"
        })
        result = b.execute(step, {}, self._make_context())
        assert not result.success
        assert "brew install" in result.error

    def test_dry_run_does_not_execute(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        from cli_anything.macrocli.backends.base import BackendContext
        b = NativeAPIBackend()
        step = self._make_step("run_command", {"command": ["false"]})
        ctx = BackendContext(params={}, dry_run=True)
        result = b.execute(step, {}, ctx)
        assert result.success
        assert result.output.get("dry_run")

    def test_param_substitution_in_command(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        b = NativeAPIBackend()
        step = self._make_step("run_command", {"command": ["echo", "${msg}"]})
        result = b.execute(step, {"msg": "substituted"}, self._make_context({"msg": "substituted"}))
        assert result.success

    def test_unknown_action(self):
        from cli_anything.macrocli.backends.native_api import NativeAPIBackend
        b = NativeAPIBackend()
        step = self._make_step("unknown_action", {})
        result = b.execute(step, {}, self._make_context())
        assert not result.success
        assert "unknown action" in result.error.lower()


class TestFileTransformBackend:
    def _make_context(self):
        from cli_anything.macrocli.backends.base import BackendContext
        return BackendContext(params={})

    def test_json_set_and_get(self, tmp_path):
        from cli_anything.macrocli.backends.file_transform import FileTransformBackend
        from cli_anything.macrocli.core.macro_model import MacroStep
        b = FileTransformBackend()
        ctx = self._make_context()

        json_file = tmp_path / "data.json"
        json_file.write_text('{"a": 1}', encoding="utf-8")

        step = MacroStep(id="set", backend="file_transform", action="json_set", params={
            "input_file": str(json_file),
            "output_file": str(json_file),
            "path": "settings.theme",
            "value": "dark",
        })
        result = b.execute(step, {}, ctx)
        assert result.success

        import json
        data = json.loads(json_file.read_text())
        assert data["settings"]["theme"] == "dark"

    def test_text_replace(self, tmp_path):
        from cli_anything.macrocli.backends.file_transform import FileTransformBackend
        from cli_anything.macrocli.core.macro_model import MacroStep
        b = FileTransformBackend()
        ctx = self._make_context()

        txt_file = tmp_path / "config.ini"
        txt_file.write_text("theme=default\nsize=10\n", encoding="utf-8")

        step = MacroStep(id="replace", backend="file_transform", action="text_replace", params={
            "input_file": str(txt_file),
            "output_file": str(txt_file),
            "find": "theme=default",
            "replace": "theme=dark",
        })
        result = b.execute(step, {}, ctx)
        assert result.success
        assert "theme=dark" in txt_file.read_text()
        assert result.output["replacements"] == 1

    def test_copy_file(self, tmp_path):
        from cli_anything.macrocli.backends.file_transform import FileTransformBackend
        from cli_anything.macrocli.core.macro_model import MacroStep
        b = FileTransformBackend()
        ctx = self._make_context()

        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("content", encoding="utf-8")

        step = MacroStep(id="copy", backend="file_transform", action="copy_file", params={
            "src": str(src),
            "dst": str(dst),
        })
        result = b.execute(step, {}, ctx)
        assert result.success
        assert dst.read_text() == "content"

    def test_unknown_action(self):
        from cli_anything.macrocli.backends.file_transform import FileTransformBackend
        from cli_anything.macrocli.core.macro_model import MacroStep
        b = FileTransformBackend()
        step = MacroStep(id="x", backend="file_transform", action="unknown_op", params={})
        result = b.execute(step, {}, self._make_context())
        assert not result.success


class TestStepResult:
    def test_to_dict(self):
        from cli_anything.macrocli.backends.base import StepResult
        r = StepResult(success=True, output={"key": "val"}, backend_used="native_api")
        d = r.to_dict()
        assert d["success"] is True
        assert d["output"]["key"] == "val"
        assert d["backend_used"] == "native_api"


# ── Routing tests ─────────────────────────────────────────────────────────────

class TestRoutingEngine:
    def test_select_native_api(self):
        from cli_anything.macrocli.core.routing import RoutingEngine
        from cli_anything.macrocli.core.macro_model import MacroStep
        engine = RoutingEngine()
        step = MacroStep(id="x", backend="native_api", action="run_command")
        backend = engine.select(step)
        assert backend.name == "native_api"

    def test_select_file_transform(self):
        from cli_anything.macrocli.core.routing import RoutingEngine
        from cli_anything.macrocli.core.macro_model import MacroStep
        engine = RoutingEngine()
        step = MacroStep(id="x", backend="file_transform", action="json_set")
        backend = engine.select(step)
        assert backend.name == "file_transform"

    def test_describe(self):
        from cli_anything.macrocli.core.routing import RoutingEngine
        engine = RoutingEngine()
        desc = engine.describe()
        assert "native_api" in desc
        assert "file_transform" in desc
        assert "recovery" in desc

    def test_execute_step_native_api(self):
        from cli_anything.macrocli.core.routing import RoutingEngine
        from cli_anything.macrocli.core.macro_model import MacroStep
        from cli_anything.macrocli.backends.base import BackendContext
        engine = RoutingEngine()
        step = MacroStep(id="x", backend="native_api", action="run_command",
                         params={"command": ["echo", "hello"]})
        ctx = BackendContext(params={})
        result = engine.execute_step(step, {}, ctx)
        assert result.success


# ── Runtime tests ─────────────────────────────────────────────────────────────

class TestMacroRuntime:
    def _make_runtime(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        from cli_anything.macrocli.core.runtime import MacroRuntime
        # Register a real macro that just echoes
        yaml_content = textwrap.dedent("""\
            name: echo_macro
            parameters:
              msg:
                type: string
                required: false
                default: hello
            steps:
              - id: step1
                backend: native_api
                action: run_command
                params:
                  command: [echo, "${msg}"]
        """)
        write_macro(tmp_path, "echo_macro", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        return MacroRuntime(registry=reg)

    def test_execute_success(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        result = rt.execute("echo_macro", {"msg": "test"})
        assert result.success
        assert result.telemetry["steps_run"] == 1

    def test_execute_unknown_macro(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        result = rt.execute("nonexistent_macro", {})
        assert not result.success
        assert "not found" in result.error.lower()

    def test_execute_param_validation_failure(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        from cli_anything.macrocli.core.runtime import MacroRuntime
        yaml_content = textwrap.dedent("""\
            name: required_param_macro
            parameters:
              output:
                type: string
                required: true
            steps:
              - id: s1
                backend: native_api
                action: run_command
                params:
                  command: [echo, "${output}"]
        """)
        write_macro(tmp_path, "required_param_macro", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("required_param_macro", {})
        assert not result.success
        assert "output" in result.error

    def test_precondition_failure(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        from cli_anything.macrocli.core.runtime import MacroRuntime
        yaml_content = textwrap.dedent("""\
            name: precond_macro
            preconditions:
              - file_exists: /nonexistent_file_xyz_abc
            steps:
              - id: s1
                backend: native_api
                action: run_command
                params:
                  command: [echo, ok]
        """)
        write_macro(tmp_path, "precond_macro", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("precond_macro", {})
        assert not result.success
        assert "precondition" in result.error.lower()

    def test_postcondition_failure(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        from cli_anything.macrocli.core.runtime import MacroRuntime
        yaml_content = textwrap.dedent("""\
            name: postcond_macro
            steps:
              - id: s1
                backend: native_api
                action: run_command
                params:
                  command: [echo, ok]
            postconditions:
              - file_exists: /nonexistent_output_xyz
        """)
        write_macro(tmp_path, "postcond_macro", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("postcond_macro", {})
        assert not result.success
        assert "postcondition" in result.error.lower()

    def test_dry_run(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        result = rt.execute("echo_macro", {}, dry_run=True)
        assert result.success
        assert result.telemetry["dry_run"] is True

    def test_session_records_run(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        rt.execute("echo_macro", {})
        last = rt.session.last()
        assert last is not None
        assert last.macro_name == "echo_macro"

    def test_validate_macro(self, tmp_path):
        rt = self._make_runtime(tmp_path)
        errors = rt.validate_macro("echo_macro")
        assert errors == []

    def test_on_failure_skip(self, tmp_path):
        from cli_anything.macrocli.core.registry import MacroRegistry
        from cli_anything.macrocli.core.runtime import MacroRuntime
        yaml_content = textwrap.dedent("""\
            name: skip_macro
            steps:
              - id: bad_step
                backend: native_api
                action: run_command
                params:
                  command: [false]
                on_failure: skip
              - id: good_step
                backend: native_api
                action: run_command
                params:
                  command: [echo, reached]
        """)
        write_macro(tmp_path, "skip_macro", yaml_content)
        reg = MacroRegistry(str(tmp_path))
        rt = MacroRuntime(registry=reg)
        result = rt.execute("skip_macro", {})
        # Should succeed because bad step was skipped
        assert result.success
        assert result.telemetry["steps_run"] == 2


# ── Session tests ─────────────────────────────────────────────────────────────

class TestExecutionSession:
    def test_record_and_retrieve(self):
        from cli_anything.macrocli.core.session import ExecutionSession, RunRecord
        sess = ExecutionSession(session_id="test_sess")
        rec = RunRecord("m1", {}, True, {}, "", 100.0, ["native_api"], 1)
        sess.record(rec)
        assert sess.last().macro_name == "m1"
        assert len(sess.history()) == 1

    def test_stats(self):
        from cli_anything.macrocli.core.session import ExecutionSession, RunRecord
        sess = ExecutionSession()
        sess.record(RunRecord("m1", {}, True, {}, "", 100.0, [], 1))
        sess.record(RunRecord("m2", {}, False, {}, "err", 50.0, [], 0))
        stats = sess.stats()
        assert stats["total"] == 2
        assert stats["success"] == 1
        assert stats["success_rate"] == 0.5

    def test_save_and_load(self, tmp_path, monkeypatch):
        from cli_anything.macrocli.core import session as sess_mod
        import cli_anything.macrocli.core.session as sess_module
        # Redirect SESSION_DIR to tmp_path
        monkeypatch.setattr(sess_module, "SESSION_DIR", tmp_path)
        from cli_anything.macrocli.core.session import ExecutionSession, RunRecord
        sess = ExecutionSession(session_id="save_test")
        sess.record(RunRecord("m1", {"k": "v"}, True, {}, "", 200.0, ["native_api"], 1))
        sess.save()

        loaded = ExecutionSession.load("save_test")
        assert loaded is not None
        assert loaded.session_id == "save_test"
        assert loaded.last().macro_name == "m1"
