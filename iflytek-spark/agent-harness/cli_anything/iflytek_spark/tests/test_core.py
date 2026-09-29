"""Unit tests for the Spark-X2.5 harness — no server required (HTTP is mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from click.testing import CliRunner

from cli_anything.iflytek_spark.core.session import ChatSession
from cli_anything.iflytek_spark.spark_cli import cli
from cli_anything.iflytek_spark.utils import spark_backend as backend
from cli_anything.iflytek_spark.utils.spark_backend import (
    BACKENDS,
    ThinkStreamSplitter,
    build_request,
    chat_completion,
    chat_completion_stream,
    load_config,
    mask_secret,
    resolve_model,
    resolve_settings,
    save_config,
    split_reasoning,
)

ENV_VARS = (
    backend.ENV_BACKEND,
    backend.ENV_BASE_URL,
    backend.ENV_API_KEY,
    backend.ENV_MODEL,
)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(backend.ENV_HOME, str(tmp_path))
    return tmp_path


def _json_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.text = json.dumps(payload)
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return resp


def _sse_response(chunks):
    resp = MagicMock()
    resp.status_code = 200
    lines = [f"data: {json.dumps(c)}".encode() for c in chunks] + [b"data: [DONE]"]
    resp.iter_lines.return_value = lines
    return resp


def _completion(content, reasoning=None, model="spark2.5"):
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return {
        "model": model,
        "choices": [{"message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 30, "total_tokens": 42},
    }


# ── settings ─────────────────────────────────────────────────────────


class TestSettings:
    def test_defaults_to_sglang_preset(self):
        s = resolve_settings()
        assert s["backend"] == "sglang"
        assert s["base_url"] == "http://localhost:30000/v1"
        assert s["model"] == "spark2.5"
        assert s["api_key"] is None

    def test_backend_presets(self):
        assert resolve_settings(backend="vllm")["model"] == "spark25"
        assert resolve_settings(backend="ollama")["base_url"] == "http://localhost:11434/v1"
        maas = resolve_settings(backend="maas")
        assert maas["base_url"] == "https://maas-api.cn-huabei-1.xf-yun.com/v2"
        assert maas["model"] is None

    def test_unknown_backend(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            resolve_settings(backend="nope")

    def test_precedence_arg_env_config(self, monkeypatch):
        save_config({"backend": "ollama", "default_model": "cfg-model", "api_key": "cfg-key"})
        assert resolve_settings()["model"] == "cfg-model"
        assert resolve_settings()["backend"] == "ollama"
        monkeypatch.setenv(backend.ENV_MODEL, "env-model")
        monkeypatch.setenv(backend.ENV_API_KEY, "env-key")
        s = resolve_settings()
        assert s["model"] == "env-model"
        assert s["api_key"] == "env-key"
        s = resolve_settings(model="arg-model", api_key="arg-key")
        assert s["model"] == "arg-model"
        assert s["api_key"] == "arg-key"

    def test_base_url_trailing_slash(self):
        assert resolve_settings(base_url="http://h:1/v1/")["base_url"] == "http://h:1/v1"

    def test_config_roundtrip(self, isolated_home):
        save_config({"backend": "vllm"})
        assert load_config() == {"backend": "vllm"}
        assert (isolated_home / "config.json").is_file()

    def test_mask_secret(self):
        assert mask_secret("abcdefghijklmnop") == "abcdef..."
        assert mask_secret("short") == "***"
        assert mask_secret(None) is None


# ── reasoning split ──────────────────────────────────────────────────


class TestSplitReasoning:
    def test_separate_reasoning_content(self):
        r, c = split_reasoning({"content": "Hefei.", "reasoning_content": "Anhui capital..."})
        assert (r, c) == ("Anhui capital...", "Hefei.")

    def test_ollama_reasoning_field(self):
        r, c = split_reasoning({"content": "Hefei.", "reasoning": "think"})
        assert (r, c) == ("think", "Hefei.")

    def test_prefilled_think_without_parser(self):
        # Chat template pre-fills <think>, so only the closing tag comes back.
        r, c = split_reasoning({"content": "The capital is Hefei.\n</think>\n\nHefei."})
        assert r == "The capital is Hefei."
        assert c == "Hefei."

    def test_full_think_block(self):
        r, c = split_reasoning({"content": "<think>\nhmm\n</think>\n\nanswer"})
        assert (r, c) == ("hmm", "answer")

    def test_no_reasoning(self):
        assert split_reasoning({"content": " plain "}) == ("", "plain")

    def test_null_content(self):
        assert split_reasoning({"content": None}) == ("", "")


class TestStreamSplitter:
    def _run(self, pieces, **kw):
        s = ThinkStreamSplitter(**kw)
        events = []
        for p in pieces:
            events += s.feed(p)
        events += s.flush()
        return events

    def test_prefilled_close_tag_split_across_chunks(self):
        events = self._run(["reason", "ing</th", "ink>\n\nHe", "fei"])
        assert events[0] == ("reasoning", "reasoning")
        assert "".join(t for k, t in events if k == "content") == "Hefei"

    def test_no_close_tag_flushes_as_content(self):
        assert self._run(["just ", "text"]) == [("content", "just text")]

    def test_passthrough(self):
        assert self._run(["a</think>b"], passthrough=True) == [("content", "a</think>b")]

    def test_reasoning_seen_releases_buffer(self):
        s = ThinkStreamSplitter()
        assert s.feed("\n\n") == []
        assert s.reasoning_seen() == []
        assert s.feed("\n\nanswer") == [("content", "answer")]
        assert s.feed(" more") == [("content", " more")]


# ── HTTP calls ───────────────────────────────────────────────────────


class TestRequests:
    def test_build_request_no_think(self):
        body = build_request("m", [], temperature=1.0, top_p=0.95, max_tokens=8, thinking=False)
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        assert body["temperature"] == 1.0
        assert body["top_p"] == 0.95
        assert body["max_tokens"] == 8
        assert "stream" not in body

    def test_build_request_thinking_is_default(self):
        assert "chat_template_kwargs" not in build_request("m", [])

    def test_chat_completion_prefilled(self):
        settings = resolve_settings()
        with patch("requests.post", return_value=_json_response(_completion("r</think>\n\nHefei."))) as post:
            result = chat_completion(settings, [{"role": "user", "content": "q"}])
        assert result["content"] == "Hefei."
        assert result["reasoning"] == "r"
        assert result["usage"]["total_tokens"] == 42
        url = post.call_args.args[0]
        assert url == "http://localhost:30000/v1/chat/completions"
        assert "Authorization" not in post.call_args.kwargs["headers"]

    def test_chat_completion_sends_bearer_key(self):
        settings = resolve_settings(backend="maas", api_key="secret", model="xspark")
        with patch("requests.post", return_value=_json_response(_completion("ok"))) as post:
            chat_completion(settings, [])
        assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer secret"
        assert post.call_args.kwargs["json"]["model"] == "xspark"

    def test_http_error(self):
        settings = resolve_settings()
        with patch("requests.post", return_value=_json_response({"error": "bad"}, status=401)):
            with pytest.raises(RuntimeError, match="Spark API error"):
                chat_completion(settings, [])

    def test_connection_error_hint(self):
        settings = resolve_settings()
        with patch("requests.post", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(RuntimeError, match="Cannot reach Spark-X2.5 server"):
                chat_completion(settings, [])

    def test_resolve_model_autodetect(self):
        settings = resolve_settings(backend="llamacpp")
        with patch("requests.get", return_value=_json_response({"data": [{"id": "Spark-X2.5-1.7B-Q4_K_M.gguf"}]})):
            assert resolve_model(settings) == "Spark-X2.5-1.7B-Q4_K_M.gguf"

    def test_resolve_model_none_served(self):
        settings = resolve_settings(backend="maas")
        with patch("requests.get", return_value=_json_response({"data": []})):
            with pytest.raises(RuntimeError, match="No model configured"):
                resolve_model(settings)

    def test_stream_with_reasoning_field(self):
        chunks = [
            {"choices": [{"delta": {"reasoning_content": "think "}}]},
            {"choices": [{"delta": {"reasoning_content": "more"}}]},
            {"choices": [{"delta": {"content": "\n\nHe"}}]},
            {"choices": [{"delta": {"content": "fei"}}]},
        ]
        seen = {"r": "", "c": ""}
        with patch("requests.post", return_value=_sse_response(chunks)):
            result = chat_completion_stream(
                resolve_settings(), [],
                on_reasoning=lambda t: seen.__setitem__("r", seen["r"] + t),
                on_content=lambda t: seen.__setitem__("c", seen["c"] + t),
            )
        assert result == {"model": "spark2.5", "reasoning": "think more", "content": "Hefei"}
        assert seen == {"r": "think more", "c": "Hefei"}

    def test_stream_prefilled(self):
        chunks = [{"choices": [{"delta": {"content": p}}]} for p in ["abc", "</think>", "\n\nok"]]
        with patch("requests.post", return_value=_sse_response(chunks)):
            result = chat_completion_stream(resolve_settings(), [])
        assert result["reasoning"] == "abc"
        assert result["content"] == "ok"

    def test_stream_no_think_is_passthrough(self):
        chunks = [{"choices": [{"delta": {"content": "direct answer"}}]}]
        with patch("requests.post", return_value=_sse_response(chunks)) as post:
            result = chat_completion_stream(resolve_settings(), [], thinking=False)
        assert result["content"] == "direct answer"
        assert post.call_args.kwargs["json"]["chat_template_kwargs"] == {"enable_thinking": False}


# ── session ──────────────────────────────────────────────────────────


class TestSession:
    def test_exchange_persists(self, tmp_path):
        path = str(tmp_path / "s.json")
        s = ChatSession(path)
        s.add_exchange("你好", "Hello", "spark2.5")
        reloaded = ChatSession(path)
        assert reloaded.get_messages() == [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "Hello"},
        ]
        assert reloaded.status()["turns"] == 1
        reloaded.clear()
        assert ChatSession(path).get_messages() == []


# ── CLI ──────────────────────────────────────────────────────────────


class TestCLI:
    def test_help(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Spark-X2.5" in result.output

    def test_backends_json(self):
        result = CliRunner().invoke(cli, ["--json", "backends"])
        assert result.exit_code == 0
        names = [b["name"] for b in json.loads(result.output)]
        assert names == list(BACKENDS)

    def test_chat_json_and_session(self, isolated_home):
        with patch("requests.post", return_value=_json_response(_completion("r</think>合肥。"))) as post:
            result = CliRunner().invoke(cli, ["--json", "chat", "--show-reasoning", "安徽的省会在哪里？"])
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            assert data["content"] == "合肥。"
            assert data["reasoning"] == "r"
            assert data["backend"] == "sglang"

            result = CliRunner().invoke(cli, ["--json", "chat", "-p", "再说一遍"])
            assert result.exit_code == 0
            sent = post.call_args.kwargs["json"]["messages"]
            assert [m["role"] for m in sent] == ["user", "assistant", "user"]
            assert sent[1]["content"] == "合肥。"
            assert "reasoning" not in json.loads(result.output)

        status = CliRunner().invoke(cli, ["--json", "session", "status"])
        assert json.loads(status.output)["turns"] == 2

    def test_chat_no_session(self, isolated_home):
        with patch("requests.post", return_value=_json_response(_completion("x"))):
            CliRunner().invoke(cli, ["chat", "--no-session", "hi"])
        assert not (isolated_home / "session.json").exists()

    def test_chat_reads_stdin(self):
        with patch("requests.post", return_value=_json_response(_completion("pong"))) as post:
            result = CliRunner().invoke(cli, ["chat", "--no-session"], input="ping\n")
        assert result.exit_code == 0
        assert result.output.strip() == "pong"
        assert post.call_args.kwargs["json"]["messages"][-1]["content"] == "ping"

    def test_chat_empty_prompt_errors(self):
        result = CliRunner().invoke(cli, ["--json", "chat"], input="")
        assert result.exit_code == 1
        assert json.loads(result.output)["type"] == "ValueError"

    def test_global_options_reach_backend(self):
        with patch("requests.post", return_value=_json_response(_completion("ok"))) as post:
            result = CliRunner().invoke(cli, [
                "--backend", "maas", "--api-key", "k-123", "--model", "xmodel",
                "chat", "--no-session", "--no-think", "hi",
            ])
        assert result.exit_code == 0, result.output
        assert post.call_args.args[0] == "https://maas-api.cn-huabei-1.xf-yun.com/v2/chat/completions"
        body = post.call_args.kwargs["json"]
        assert body["model"] == "xmodel"
        assert body["chat_template_kwargs"] == {"enable_thinking": False}

    def test_connection_error_json(self):
        with patch("requests.post", side_effect=requests.ConnectionError("refused")):
            result = CliRunner().invoke(cli, ["--json", "chat", "--no-session", "hi"])
        assert result.exit_code == 1
        assert "Cannot reach" in json.loads(result.output)["error"]

    def test_models_json(self):
        with patch("requests.get", return_value=_json_response({"data": [{"id": "spark2.5"}]})):
            result = CliRunner().invoke(cli, ["--json", "models"])
        assert json.loads(result.output)["models"] == ["spark2.5"]

    def test_config_set_get_masks_key(self):
        runner = CliRunner()
        assert runner.invoke(cli, ["config", "set", "api_key", "abcdefghijklmnop"]).exit_code == 0
        result = runner.invoke(cli, ["--json", "config", "get"])
        assert json.loads(result.output)["api_key"] == "abcdef..."
        assert load_config()["api_key"] == "abcdefghijklmnop"

    def test_config_rejects_unknown_backend(self):
        result = CliRunner().invoke(cli, ["--json", "config", "set", "backend", "nope"])
        assert result.exit_code == 1
        assert load_config() == {}

    def test_stream_json(self):
        chunks = [{"choices": [{"delta": {"content": p}}]} for p in ["x</think>", "done"]]
        with patch("requests.post", return_value=_sse_response(chunks)):
            result = CliRunner().invoke(cli, ["--json", "stream", "--no-session", "q"])
        assert result.exit_code == 0
        assert json.loads(result.output)["content"] == "done"
