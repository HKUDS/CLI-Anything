"""E2E tests for cli-anything-iflytek-spark — require a live Spark-X2.5 server.

The server is taken from the usual settings (IFLYTEK_SPARK_BACKEND,
IFLYTEK_SPARK_BASE_URL, IFLYTEK_SPARK_API_KEY, IFLYTEK_SPARK_MODEL, default
SGLang on localhost:30000). Live tests are skipped when it is not reachable.

Usage:
    IFLYTEK_SPARK_BACKEND=llamacpp python -m pytest cli_anything/iflytek_spark/tests/test_full_e2e.py -v -s
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from cli_anything.iflytek_spark.utils.spark_backend import (
    THINK_CLOSE,
    THINK_OPEN,
    is_available,
    resolve_settings,
)

SETTINGS = resolve_settings()
LIVE = is_available(SETTINGS["base_url"], SETTINGS.get("api_key"))
live = pytest.mark.skipif(not LIVE, reason=f"Spark-X2.5 server not reachable at {SETTINGS['base_url']}")


def _resolve_cli(name):
    """Resolve the installed CLI command; fall back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.iflytek_spark"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-iflytek-spark")

    @pytest.fixture(autouse=True)
    def _home(self, tmp_path):
        self.env = dict(os.environ, IFLYTEK_SPARK_HOME=str(tmp_path), PYTHONIOENCODING="utf-8")

    def _run(self, args, input=None):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True, encoding="utf-8",
            input=input, env=self.env, timeout=900,
        )

    def _json(self, args, input=None):
        result = self._run(["--json"] + args, input=input)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Spark-X2.5" in result.stdout

    def test_backends_json(self):
        names = [b["name"] for b in self._json(["backends"])]
        assert {"sglang", "vllm", "ollama", "llamacpp", "maas"} <= set(names)

    def test_config_roundtrip(self):
        self._json(["config", "set", "backend", "ollama"])
        assert self._json(["config", "get"])["backend"] == "ollama"

    def test_unreachable_server_reports_error(self):
        result = self._run(["--json", "--base-url", "http://127.0.0.1:9/v1", "--model", "m",
                            "chat", "--no-session", "hi"])
        assert result.returncode == 1
        assert "Cannot reach" in json.loads(result.stdout)["error"]

    @live
    def test_models(self):
        data = self._json(["models"])
        print(f"\n  models: {data['models']}")
        assert data["models"]

    @live
    def test_connectivity(self):
        data = self._json(["test"])
        print(f"\n  test: {data}")
        assert data["status"] == "ok"

    @live
    def test_chat_splits_reasoning(self):
        data = self._json(["chat", "--no-session", "--show-reasoning", "--max-tokens", "2048",
                           "What is 17 * 23? Reply with the number only."])
        print(f"\n  reasoning: {data['reasoning'][:200]!r}...\n  content: {data['content']!r}")
        assert "391" in data["content"]
        assert THINK_OPEN not in data["content"] and THINK_CLOSE not in data["content"]
        assert data["reasoning"]

    @live
    def test_chat_no_think(self):
        data = self._json(["chat", "--no-session", "--no-think", "--show-reasoning", "--max-tokens", "256",
                           "Translate to English, reply with the translation only: 你好"])
        print(f"\n  no-think content: {data['content']!r}")
        assert "hello" in data["content"].lower()
        assert THINK_CLOSE not in data["content"]

    @live
    def test_stream(self):
        data = self._json(["stream", "--no-session", "--max-tokens", "2048",
                           "What is the capital of France? One word."])
        print(f"\n  stream content: {data['content']!r}")
        assert "paris" in data["content"].lower()
        assert THINK_CLOSE not in data["content"]

    @live
    def test_multi_turn_session(self):
        question = ["--no-think", "--max-tokens", "64", "What is the capital of Japan? One word."]
        fresh = self._json(["chat", "--no-session"] + question)
        first = self._json(["chat", "--no-think", "--max-tokens", "64", "Name one primary colour. One word."])
        second = self._json(["chat"] + question)
        print(f"\n  prompt tokens: fresh={fresh['usage']['prompt_tokens']} "
              f"with history={second['usage']['prompt_tokens']}")
        # The earlier turn must reach the server, so the same question costs
        # at least that turn's prompt and answer on top of the fresh prompt.
        grown = second["usage"]["prompt_tokens"] - fresh["usage"]["prompt_tokens"]
        assert grown >= first["usage"]["completion_tokens"]
        assert THINK_CLOSE not in first["content"]
        assert self._json(["session", "status"])["turns"] == 2

    @live
    def test_stdin_prompt(self):
        data = self._json(["chat", "--no-session", "--no-think", "--max-tokens", "64"],
                          input="Reply with the single word: pong")
        assert "pong" in data["content"].lower()
