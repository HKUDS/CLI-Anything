"""Unit tests for cli-anything-ollama — no Ollama server required."""

import json
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from cli_anything.ollama.ollama_cli import cli, _format_size
from cli_anything.ollama.utils.ollama_backend import DEFAULT_BASE_URL


@pytest.fixture
def runner():
    return CliRunner()


# ── Backend URL construction ─────────────────────────────────────

class TestBackend:
    def test_default_base_url(self):
        assert DEFAULT_BASE_URL == "http://localhost:11434"

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_is_available_true(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import is_available
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        assert is_available() is True
        mock_get.assert_called_once_with("http://localhost:11434/", timeout=5)

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_is_available_false(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import is_available
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        assert is_available() is False

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_api_get_connection_error(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import api_get
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            api_get("http://localhost:11434", "/api/tags")

    @patch("cli_anything.ollama.utils.ollama_backend.requests.post")
    def test_api_post_connection_error(self, mock_post):
        from cli_anything.ollama.utils.ollama_backend import api_post
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            api_post("http://localhost:11434", "/api/show", {"name": "test"})

    @patch("cli_anything.ollama.utils.ollama_backend.requests.delete")
    def test_api_delete_connection_error(self, mock_delete):
        from cli_anything.ollama.utils.ollama_backend import api_delete
        import requests
        mock_delete.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            api_delete("http://localhost:11434", "/api/delete", {"name": "test"})

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_api_get_success(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import api_get
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"models": []}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"models": []}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        result = api_get("http://localhost:11434", "/api/tags")
        assert result == {"models": []}

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_api_get_trailing_slash_stripped(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import api_get
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"models": []}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"models": []}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        api_get("http://localhost:11434/", "/api/tags")
        mock_get.assert_called_once_with(
            "http://localhost:11434/api/tags", params=None, timeout=30
        )

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_api_get_timeout(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import api_get
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        with pytest.raises(RuntimeError, match="timed out"):
            api_get("http://localhost:11434", "/api/tags")


# ── Output formatting ────────────────────────────────────────────

class TestFormatSize:
    def test_zero(self):
        assert _format_size(0) == "0 B"

    def test_bytes(self):
        assert _format_size(512) == "512.0 B"

    def test_kilobytes(self):
        assert _format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        result = _format_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = _format_size(3 * 1024 * 1024 * 1024)
        assert "GB" in result


# ── CLI argument parsing ─────────────────────────────────────────

class TestCLIParsing:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Ollama CLI" in result.output

    def test_model_help(self, runner):
        result = runner.invoke(cli, ["model", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output
        assert "pull" in result.output
        assert "rm" in result.output
        assert "copy" in result.output
        assert "ps" in result.output

    def test_generate_help(self, runner):
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "text" in result.output
        assert "chat" in result.output

    def test_embed_help(self, runner):
        result = runner.invoke(cli, ["embed", "--help"])
        assert result.exit_code == 0
        assert "text" in result.output

    def test_server_help(self, runner):
        result = runner.invoke(cli, ["server", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "version" in result.output

    def test_session_help(self, runner):
        result = runner.invoke(cli, ["session", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "history" in result.output

    def test_json_flag(self, runner):
        result = runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "host" in data

    def test_host_flag(self, runner):
        result = runner.invoke(cli, ["--host", "http://example:1234", "--json", "session", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["host"] == "http://example:1234"


# ── Session state ────────────────────────────────────────────────

class TestSessionState:
    def test_session_status_defaults(self, runner):
        result = runner.invoke(cli, ["--json", "session", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["chat_history_length"] == 0

    def test_session_history_empty(self, runner):
        result = runner.invoke(cli, ["--json", "session", "history"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["messages"] == []

    def test_session_history_human(self, runner):
        result = runner.invoke(cli, ["session", "history"])
        assert result.exit_code == 0
        assert "No chat history" in result.output


# ── Error handling ───────────────────────────────────────────────

class TestErrorHandling:
    @patch("cli_anything.ollama.core.models.api_get")
    def test_model_list_connection_error(self, mock_api, runner):
        mock_api.side_effect = RuntimeError(
            "Cannot connect to Ollama at http://localhost:11434. "
            "Is Ollama running? Start it with: ollama serve"
        )
        result = runner.invoke(cli, ["model", "list"])
        assert result.exit_code == 1

    @patch("cli_anything.ollama.core.models.api_get")
    def test_model_list_connection_error_json(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Ollama")
        result = runner.invoke(cli, ["--json", "model", "list"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data

    @patch("cli_anything.ollama.core.server.api_get")
    def test_server_status_error(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Ollama")
        result = runner.invoke(cli, ["server", "status"])
        assert result.exit_code == 1

    def test_generate_chat_no_messages(self, runner):
        result = runner.invoke(cli, ["generate", "chat", "--model", "test"])
        assert result.exit_code == 1

    def test_generate_chat_bad_format(self, runner):
        result = runner.invoke(cli, ["generate", "chat", "--model", "test",
                                     "--message", "no-colon-here"])
        assert result.exit_code == 1


# ── Model commands with mocked API ──────────────────────────────

class TestModelCommands:
    @patch("cli_anything.ollama.core.models.api_get")
    def test_model_list_empty(self, mock_api, runner):
        mock_api.return_value = {"models": []}
        result = runner.invoke(cli, ["model", "list"])
        assert result.exit_code == 0
        assert "No models" in result.output

    @patch("cli_anything.ollama.core.models.api_get")
    def test_model_list_json(self, mock_api, runner):
        mock_api.return_value = {"models": [{"name": "llama3.2", "size": 2000000000}]}
        result = runner.invoke(cli, ["--json", "model", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["models"]) == 1

    @patch("cli_anything.ollama.core.models.api_get")
    def test_model_list_formatted(self, mock_api, runner):
        mock_api.return_value = {
            "models": [{"name": "llama3.2:latest", "size": 2000000000, "modified_at": "2024-01-01T00:00:00Z"}]
        }
        result = runner.invoke(cli, ["model", "list"])
        assert result.exit_code == 0
        assert "llama3.2:latest" in result.output

    @patch("cli_anything.ollama.core.models.api_post")
    def test_model_show(self, mock_api, runner):
        mock_api.return_value = {"modelfile": "FROM llama3.2", "parameters": "temperature 0.7"}
        result = runner.invoke(cli, ["--json", "model", "show", "llama3.2"])
        assert result.exit_code == 0

    @patch("cli_anything.ollama.core.models.api_delete")
    def test_model_rm(self, mock_api, runner):
        mock_api.return_value = {"status": "ok"}
        result = runner.invoke(cli, ["model", "rm", "test-model"])
        assert result.exit_code == 0
        assert "Deleted" in result.output

    @patch("cli_anything.ollama.core.models.api_post")
    def test_model_copy(self, mock_api, runner):
        mock_api.return_value = {"status": "ok"}
        result = runner.invoke(cli, ["model", "copy", "src", "dst"])
        assert result.exit_code == 0
        assert "Copied" in result.output

    @patch("cli_anything.ollama.core.models.api_get")
    def test_model_ps_empty(self, mock_api, runner):
        mock_api.return_value = {"models": []}
        result = runner.invoke(cli, ["model", "ps"])
        assert result.exit_code == 0
        assert "No models" in result.output


# ── Server commands with mocked API ──────────────────────────────

class TestServerCommands:
    @patch("cli_anything.ollama.core.server.api_get")
    def test_server_status(self, mock_api, runner):
        mock_api.return_value = {"status": "ok", "message": "Ollama is running"}
        result = runner.invoke(cli, ["server", "status"])
        assert result.exit_code == 0

    @patch("cli_anything.ollama.core.server.api_get")
    def test_server_version(self, mock_api, runner):
        mock_api.return_value = {"version": "0.1.30"}
        result = runner.invoke(cli, ["--json", "server", "version"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["version"] == "0.1.30"


# ── Embed command with mocked API ────────────────────────────────

class TestEmbedCommands:
    @patch("cli_anything.ollama.core.embeddings.api_post")
    def test_embed_text_json(self, mock_api, runner):
        mock_api.return_value = {"embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]]}
        result = runner.invoke(cli, ["--json", "embed", "text",
                                     "--model", "nomic-embed-text",
                                     "--input", "Hello world"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "embeddings" in data

    @patch("cli_anything.ollama.core.embeddings.api_post")
    def test_embed_text_multiple_inputs_json(self, mock_api, runner):
        mock_api.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        result = runner.invoke(cli, ["--json", "embed", "text",
                                     "--model", "nomic-embed-text",
                                     "--input", "Hello",
                                     "--input", "World"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["embeddings"]) == 2
        call_data = mock_api.call_args[0][2]
        assert call_data["input"] == ["Hello", "World"]

    @patch("cli_anything.ollama.core.embeddings.api_post")
    def test_embed_text_human(self, mock_api, runner):
        mock_api.return_value = {"embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]]}
        result = runner.invoke(cli, ["embed", "text",
                                     "--model", "nomic-embed-text",
                                     "--input", "Hello"])
        assert result.exit_code == 0
        assert "Dimensions: 6" in result.output

    @patch("cli_anything.ollama.core.embeddings.api_post")
    def test_embed_text_preview_values(self, mock_api, runner):
        mock_api.return_value = {"embeddings": [[0.123456, 0.234567, 0.345678, 0.456789, 0.567890, 0.6]]}
        result = runner.invoke(cli, ["embed", "text",
                                     "--model", "nomic-embed-text",
                                     "--input", "Hello"])
        assert result.exit_code == 0
        assert "Preview:" in result.output
        assert "0.123456" in result.output

    @patch("cli_anything.ollama.core.embeddings.api_post")
    def test_embed_text_empty_embeddings(self, mock_api, runner):
        mock_api.return_value = {"embeddings": []}
        result = runner.invoke(cli, ["embed", "text",
                                     "--model", "nomic-embed-text",
                                     "--input", "Hello"])
        assert result.exit_code == 0


# ── Generate text with mocked API ────────────────────────────────

class TestGenerateTextCommands:
    @patch("cli_anything.ollama.core.generate.api_post")
    def test_generate_text_no_stream_json(self, mock_api, runner):
        mock_api.return_value = {
            "model": "llama3.2",
            "response": "Hello! How can I help you?",
            "done": True,
            "total_duration": 1234567890,
            "eval_count": 7,
        }
        result = runner.invoke(cli, ["--json", "generate", "text",
                                     "--model", "llama3.2",
                                     "--prompt", "Say hello",
                                     "--no-stream"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["response"] == "Hello! How can I help you?"
        assert data["done"] is True

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_generate_text_no_stream_human(self, mock_api, runner):
        mock_api.return_value = {
            "model": "llama3.2",
            "response": "The sky is blue.",
            "done": True,
        }
        result = runner.invoke(cli, ["generate", "text",
                                     "--model", "llama3.2",
                                     "--prompt", "Why is the sky blue?",
                                     "--no-stream"])
        assert result.exit_code == 0
        assert "The sky is blue." in result.output

    @patch("cli_anything.ollama.core.generate.api_post_stream")
    def test_generate_text_streaming(self, mock_stream, runner):
        mock_stream.return_value = iter([
            {"response": "Hello", "done": False},
            {"response": " world", "done": False},
            {"response": "!", "done": True, "total_duration": 100000},
        ])
        result = runner.invoke(cli, ["generate", "text",
                                     "--model", "llama3.2",
                                     "--prompt", "Say hello"])
        assert result.exit_code == 0
        assert "Hello world!" in result.output

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_generate_text_with_system(self, mock_api, runner):
        mock_api.return_value = {
            "model": "llama3.2",
            "response": "Ahoy!",
            "done": True,
        }
        result = runner.invoke(cli, ["--json", "generate", "text",
                                     "--model", "llama3.2",
                                     "--prompt", "Say hello",
                                     "--system", "You are a pirate",
                                     "--no-stream"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["response"] == "Ahoy!"

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_generate_text_with_options(self, mock_api, runner):
        mock_api.return_value = {"model": "llama3.2", "response": "Hi", "done": True}
        result = runner.invoke(cli, ["--json", "generate", "text",
                                     "--model", "llama3.2",
                                     "--prompt", "Hello",
                                     "--temperature", "0.5",
                                     "--top-p", "0.9",
                                     "--num-predict", "50",
                                     "--no-stream"])
        assert result.exit_code == 0
        # Verify options were passed
        call_args = mock_api.call_args
        assert call_args is not None

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_generate_text_connection_error(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Ollama")
        result = runner.invoke(cli, ["generate", "text",
                                     "--model", "llama3.2",
                                     "--prompt", "Hello",
                                     "--no-stream"])
        assert result.exit_code == 1

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_generate_text_connection_error_json(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Ollama")
        result = runner.invoke(cli, ["--json", "generate", "text",
                                     "--model", "llama3.2",
                                     "--prompt", "Hello",
                                     "--no-stream"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data
        assert "runtime_error" in data["type"]


# ── Generate chat with mocked API ────────────────────────────────

class TestGenerateChatCommands:
    @patch("cli_anything.ollama.core.generate.api_post")
    def test_chat_no_stream_json(self, mock_api, runner):
        mock_api.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Hello! How can I help?"},
            "done": True,
            "total_duration": 1234567890,
        }
        result = runner.invoke(cli, ["--json", "generate", "chat",
                                     "--model", "llama3.2",
                                     "--message", "user:Hi there",
                                     "--no-stream"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["message"]["role"] == "assistant"
        assert "Hello" in data["message"]["content"]

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_chat_multi_message(self, mock_api, runner):
        mock_api.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Python is great!"},
            "done": True,
        }
        result = runner.invoke(cli, ["--json", "generate", "chat",
                                     "--model", "llama3.2",
                                     "--message", "user:What is Python?",
                                     "--message", "assistant:It's a programming language",
                                     "--message", "user:Tell me more",
                                     "--no-stream"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["message"]["content"] == "Python is great!"

    @patch("cli_anything.ollama.core.generate.api_post_stream")
    def test_chat_streaming(self, mock_stream, runner):
        mock_stream.return_value = iter([
            {"message": {"role": "assistant", "content": "I'm"}, "done": False},
            {"message": {"role": "assistant", "content": " doing"}, "done": False},
            {"message": {"role": "assistant", "content": " well!"}, "done": True},
        ])
        result = runner.invoke(cli, ["generate", "chat",
                                     "--model", "llama3.2",
                                     "--message", "user:How are you?"])
        assert result.exit_code == 0
        assert "I'm doing well!" in result.output

    @patch("cli_anything.ollama.core.generate.api_post_stream")
    def test_chat_streaming_error(self, mock_stream, runner):
        mock_stream.return_value = iter([
            {"message": {"role": "assistant", "content": "partial"}, "done": False},
            {"error": "stream failed"},
        ])
        result = runner.invoke(cli, ["generate", "chat",
                                     "--model", "llama3.2",
                                     "--message", "user:Hello"])
        assert result.exit_code == 1
        assert "Error: stream failed" in result.output

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_chat_from_file(self, mock_api, runner, tmp_path):
        messages_file = tmp_path / "messages.json"
        messages_file.write_text(json.dumps([
            {"role": "user", "content": "What is 2+2?"},
        ]))
        mock_api.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "4"},
            "done": True,
        }
        result = runner.invoke(cli, ["--json", "generate", "chat",
                                     "--model", "llama3.2",
                                     "--file", str(messages_file),
                                     "--no-stream"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["message"]["content"] == "4"

    def test_chat_missing_model(self, runner):
        result = runner.invoke(cli, ["generate", "chat",
                                     "--message", "user:Hello"])
        assert result.exit_code != 0

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_chat_connection_error(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Ollama")
        result = runner.invoke(cli, ["generate", "chat",
                                     "--model", "llama3.2",
                                     "--message", "user:Hello",
                                     "--no-stream"])
        assert result.exit_code == 1


# ── Model pull with mocked API ───────────────────────────────────

class TestModelPullCommands:
    @patch("cli_anything.ollama.core.models.api_post")
    def test_pull_no_stream(self, mock_api, runner):
        mock_api.return_value = {"status": "success"}
        result = runner.invoke(cli, ["model", "pull", "llama3.2", "--no-stream"])
        assert result.exit_code == 0
        assert "Pulled" in result.output

    @patch("cli_anything.ollama.core.models.api_post")
    def test_pull_no_stream_json(self, mock_api, runner):
        mock_api.return_value = {"status": "success"}
        result = runner.invoke(cli, ["--json", "model", "pull", "llama3.2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"

    @patch("cli_anything.ollama.core.models.api_post_stream")
    def test_pull_streaming(self, mock_stream, runner):
        mock_stream.return_value = iter([
            {"status": "pulling manifest"},
            {"status": "downloading", "digest": "sha256:abc123", "total": 1000, "completed": 500},
            {"status": "downloading", "digest": "sha256:abc123", "total": 1000, "completed": 1000},
            {"status": "verifying sha256 digest"},
            {"status": "writing manifest"},
            {"status": "success"},
        ])
        result = runner.invoke(cli, ["model", "pull", "llama3.2"])
        assert result.exit_code == 0
        assert "Done" in result.output

    @patch("cli_anything.ollama.core.models.api_post_stream")
    def test_pull_streaming_error(self, mock_stream, runner):
        mock_stream.return_value = iter([
            {"status": "downloading"},
            {"error": "disk full"},
        ])
        result = runner.invoke(cli, ["model", "pull", "llama3.2"])
        assert result.exit_code == 1
        assert "Error: disk full" in result.output

    @patch("cli_anything.ollama.core.models.api_post")
    def test_pull_connection_error(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Cannot connect to Ollama")
        result = runner.invoke(cli, ["model", "pull", "llama3.2", "--no-stream"])
        assert result.exit_code == 1


# ── Model ps with loaded models ──────────────────────────────────

class TestModelPsCommands:
    @patch("cli_anything.ollama.core.models.api_get")
    def test_ps_with_models(self, mock_api, runner):
        mock_api.return_value = {
            "models": [{
                "name": "llama3.2:latest",
                "size": 3825819519,
                "size_vram": 3825819519,
                "expires_at": "2024-06-04T14:38:31.83753-07:00",
            }]
        }
        result = runner.invoke(cli, ["model", "ps"])
        assert result.exit_code == 0
        assert "llama3.2:latest" in result.output

    @patch("cli_anything.ollama.core.models.api_get")
    def test_ps_with_models_json(self, mock_api, runner):
        mock_api.return_value = {
            "models": [{
                "name": "llama3.2:latest",
                "size": 3825819519,
                "size_vram": 3825819519,
            }]
        }
        result = runner.invoke(cli, ["--json", "model", "ps"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["models"]) == 1
        assert data["models"][0]["name"] == "llama3.2:latest"


# ── Model show with full response ────────────────────────────────

class TestModelShowCommands:
    @patch("cli_anything.ollama.core.models.api_post")
    def test_show_human_output(self, mock_api, runner):
        mock_api.return_value = {
            "modelfile": "FROM llama3.2\nPARAMETER temperature 0.7",
            "parameters": "temperature 0.7\ntop_p 0.9",
            "template": "{{ .Prompt }}",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "llama",
                "parameter_size": "3.2B",
                "quantization_level": "Q4_0",
            },
        }
        result = runner.invoke(cli, ["model", "show", "llama3.2"])
        assert result.exit_code == 0
        assert "llama3.2" in result.output

    @patch("cli_anything.ollama.core.models.api_post")
    def test_show_json_output(self, mock_api, runner):
        mock_api.return_value = {
            "modelfile": "FROM llama3.2",
            "details": {"family": "llama", "parameter_size": "3.2B"},
        }
        result = runner.invoke(cli, ["--json", "model", "show", "llama3.2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["details"]["family"] == "llama"

    @patch("cli_anything.ollama.core.models.api_post")
    def test_show_nonexistent_model(self, mock_api, runner):
        mock_api.side_effect = RuntimeError("Ollama API error 404 on POST /api/show: model not found")
        result = runner.invoke(cli, ["model", "show", "nonexistent"])
        assert result.exit_code == 1


# ── Backend streaming ────────────────────────────────────────────

class TestBackendStreaming:
    @patch("cli_anything.ollama.utils.ollama_backend.requests.post")
    def test_api_post_stream_success(self, mock_post):
        from cli_anything.ollama.utils.ollama_backend import api_post_stream
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [
            b'{"response": "Hello", "done": false}',
            b'{"response": " world", "done": true}',
        ]
        mock_post.return_value = mock_resp
        chunks = list(api_post_stream("http://localhost:11434", "/api/generate", {"model": "test"}))
        assert len(chunks) == 2
        assert chunks[0]["response"] == "Hello"
        assert chunks[1]["done"] is True

    @patch("cli_anything.ollama.utils.ollama_backend.requests.post")
    def test_api_post_stream_connection_error(self, mock_post):
        from cli_anything.ollama.utils.ollama_backend import api_post_stream
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            list(api_post_stream("http://localhost:11434", "/api/generate", {}))

    @patch("cli_anything.ollama.utils.ollama_backend.requests.post")
    def test_api_post_stream_skips_empty_lines(self, mock_post):
        from cli_anything.ollama.utils.ollama_backend import api_post_stream
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [
            b'{"response": "Hi", "done": false}',
            b'',
            b'{"response": "!", "done": true}',
        ]
        mock_post.return_value = mock_resp
        chunks = list(api_post_stream("http://localhost:11434", "/api/generate", {}))
        assert len(chunks) == 2


# ── Backend HTTP error handling ──────────────────────────────────

class TestBackendHTTPErrors:
    @patch("cli_anything.ollama.utils.ollama_backend.requests.post")
    def test_api_post_http_error(self, mock_post):
        from cli_anything.ollama.utils.ollama_backend import api_post
        import requests
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "model not found"
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_post.return_value = mock_resp
        with pytest.raises(RuntimeError, match="Ollama API error 404"):
            api_post("http://localhost:11434", "/api/show", {"name": "bad"})

    @patch("cli_anything.ollama.utils.ollama_backend.requests.post")
    def test_api_post_timeout(self, mock_post):
        from cli_anything.ollama.utils.ollama_backend import api_post
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        with pytest.raises(RuntimeError, match="timed out"):
            api_post("http://localhost:11434", "/api/show", {"name": "test"})

    @patch("cli_anything.ollama.utils.ollama_backend.requests.delete")
    def test_api_delete_http_error(self, mock_delete):
        from cli_anything.ollama.utils.ollama_backend import api_delete
        import requests
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "model not found"
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_delete.return_value = mock_resp
        with pytest.raises(RuntimeError, match="Ollama API error 404"):
            api_delete("http://localhost:11434", "/api/delete", {"name": "bad"})

    @patch("cli_anything.ollama.utils.ollama_backend.requests.delete")
    def test_api_delete_timeout(self, mock_delete):
        from cli_anything.ollama.utils.ollama_backend import api_delete
        import requests
        mock_delete.side_effect = requests.exceptions.Timeout()
        with pytest.raises(RuntimeError, match="timed out"):
            api_delete("http://localhost:11434", "/api/delete", {"name": "test"})

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_api_get_http_error(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import api_get
        import requests
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "internal server error"
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_get.return_value = mock_resp
        with pytest.raises(RuntimeError, match="Ollama API error 500"):
            api_get("http://localhost:11434", "/api/tags")

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_api_get_plain_text_response(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import api_get
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"Ollama is running"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.text = "Ollama is running"
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp
        result = api_get("http://localhost:11434", "/")
        assert result["message"] == "Ollama is running"

    @patch("cli_anything.ollama.utils.ollama_backend.requests.post")
    def test_api_post_204_no_content(self, mock_post):
        from cli_anything.ollama.utils.ollama_backend import api_post
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        result = api_post("http://localhost:11434", "/api/copy", {"source": "a", "destination": "b"})
        assert result == {"status": "ok"}

    @patch("cli_anything.ollama.utils.ollama_backend.requests.get")
    def test_is_available_timeout(self, mock_get):
        from cli_anything.ollama.utils.ollama_backend import is_available
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        assert is_available() is False


# ── Core module direct tests ─────────────────────────────────────

class TestCoreModules:
    @patch("cli_anything.ollama.core.generate.api_post")
    def test_generate_builds_correct_payload(self, mock_api):
        from cli_anything.ollama.core.generate import generate
        mock_api.return_value = {"response": "hi", "done": True}
        generate("http://localhost:11434", "llama3.2", "Hello",
                 system="Be helpful", options={"temperature": 0.5}, stream=False)
        call_data = mock_api.call_args[0][2]
        assert call_data["model"] == "llama3.2"
        assert call_data["prompt"] == "Hello"
        assert call_data["system"] == "Be helpful"
        assert call_data["options"]["temperature"] == 0.5
        assert call_data["stream"] is False

    @patch("cli_anything.ollama.core.generate.api_post")
    def test_chat_builds_correct_payload(self, mock_api):
        from cli_anything.ollama.core.generate import chat
        mock_api.return_value = {"message": {"role": "assistant", "content": "hi"}, "done": True}
        messages = [{"role": "user", "content": "Hello"}]
        chat("http://localhost:11434", "llama3.2", messages,
             options={"temperature": 0.8}, stream=False)
        call_data = mock_api.call_args[0][2]
        assert call_data["model"] == "llama3.2"
        assert call_data["messages"] == messages
        assert call_data["options"]["temperature"] == 0.8

    @patch("cli_anything.ollama.core.embeddings.api_post")
    def test_embed_builds_correct_payload(self, mock_api):
        from cli_anything.ollama.core.embeddings import embed
        mock_api.return_value = {"embeddings": [[0.1, 0.2]]}
        embed("http://localhost:11434", "nomic-embed-text", "test input")
        call_data = mock_api.call_args[0][2]
        assert call_data["model"] == "nomic-embed-text"
        assert call_data["input"] == "test input"

    @patch("cli_anything.ollama.core.embeddings.api_post")
    def test_embed_list_input(self, mock_api):
        from cli_anything.ollama.core.embeddings import embed
        mock_api.return_value = {"embeddings": [[0.1], [0.2]]}
        embed("http://localhost:11434", "nomic-embed-text", ["hello", "world"])
        call_data = mock_api.call_args[0][2]
        assert call_data["input"] == ["hello", "world"]

    @patch("cli_anything.ollama.core.models.api_post")
    def test_copy_model_payload(self, mock_api):
        from cli_anything.ollama.core.models import copy_model
        mock_api.return_value = {"status": "ok"}
        copy_model("http://localhost:11434", "llama3.2", "my-llama")
        call_data = mock_api.call_args[0][2]
        assert call_data["source"] == "llama3.2"
        assert call_data["destination"] == "my-llama"

    @patch("cli_anything.ollama.core.models.api_delete")
    def test_delete_model_payload(self, mock_api):
        from cli_anything.ollama.core.models import delete_model
        mock_api.return_value = {"status": "ok"}
        delete_model("http://localhost:11434", "old-model")
        call_data = mock_api.call_args[0][2]
        assert call_data["name"] == "old-model"


# ── Stream to stdout helper ──────────────────────────────────────

class TestStreamToStdout:
    def test_stream_to_stdout_generate(self, capsys):
        from cli_anything.ollama.core.generate import stream_to_stdout
        chunks = iter([
            {"response": "Hello", "done": False},
            {"response": " there", "done": False},
            {"response": "!", "done": True, "total_duration": 999},
        ])
        final = stream_to_stdout(chunks)
        captured = capsys.readouterr()
        assert "Hello there!" in captured.out
        assert final["done"] is True
        assert final["total_duration"] == 999

    def test_stream_to_stdout_chat(self, capsys):
        from cli_anything.ollama.core.generate import stream_to_stdout
        chunks = iter([
            {"message": {"role": "assistant", "content": "Yes"}, "done": False},
            {"message": {"role": "assistant", "content": "!"}, "done": True},
        ])
        final = stream_to_stdout(chunks)
        captured = capsys.readouterr()
        assert "Yes!" in captured.out

    def test_stream_to_stdout_empty(self, capsys):
        from cli_anything.ollama.core.generate import stream_to_stdout
        chunks = iter([{"done": True}])
        final = stream_to_stdout(chunks)
        captured = capsys.readouterr()
        assert final["done"] is True
