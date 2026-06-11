"""E2E tests for MiniMax CLI — uses real API when MINIMAX_API_KEY is set."""

import os
import json
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch, MagicMock

from cli_anything.minimax.utils.minimax_backend import (
    chat_completion,
    chat_completion_stream,
    tts_synthesize,
)

API_KEY = os.environ.get("MINIMAX_API_KEY")
HARNESS_ROOT = Path(__file__).resolve().parents[3]


def _resolve_cli(name):
    """Resolve installed CLI command; fall back to python -m for local dev."""
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.")
    module = f"{module}.{name.split('-')[-1]}_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


def _subprocess_env(tmp_path, extra=None):
    env = os.environ.copy()
    env.pop("MINIMAX_API_KEY", None)
    env["HOME"] = str(tmp_path)
    pythonpath_parts = [str(HARNESS_ROOT)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    if extra:
        env.update(extra)
    return env


@contextmanager
def _fake_minimax_server(status_code=200):
    """Run a local MiniMax-compatible HTTP fake for CLI subprocess tests."""

    class Handler(BaseHTTPRequestHandler):
        requests_seen = []

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
            self.requests_seen.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization", ""),
                    "payload": payload,
                }
            )

            if status_code != 200:
                response = b'{"error":"Invalid API key"}'
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return

            if self.path.endswith("/chat/completions"):
                response = json.dumps(
                    {
                        "choices": [
                            {"message": {"role": "assistant", "content": "mock chat ok"}}
                        ],
                        "usage": {
                            "prompt_tokens": 3,
                            "completion_tokens": 2,
                            "total_tokens": 5,
                        },
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return

            if self.path.endswith("/v1/t2a_v2"):
                hex_audio = bytes([0xFF, 0xFB, 0x11, 0x22]).hex()
                event = json.dumps(
                    {
                        "data": {"audio": hex_audio, "status": 2},
                        "base_resp": {"status_code": 0, "status_msg": "success"},
                    }
                )
                response = f"data:{event}\n\ndata:[DONE]\n\n".encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", Handler.requests_seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestCLISubprocessSmoke:
    CLI_BASE = _resolve_cli("cli-anything-minimax")

    def _run(self, args, tmp_path, extra_env=None, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            env=_subprocess_env(tmp_path, extra_env),
        )

    def test_installed_command_help_smoke(self, tmp_path):
        result = self._run(["--help"], tmp_path)
        assert result.returncode == 0
        assert "MiniMax CLI" in result.stdout
        assert "chat" in result.stdout
        assert "tts" in result.stdout

    def test_no_backend_commands_work_without_api_key(self, tmp_path):
        session_status = self._run(["--json", "session", "status"], tmp_path)
        status = json.loads(session_status.stdout)
        assert status["message_count"] == 0
        assert status["history_count"] == 0

        models = self._run(["models"], tmp_path)
        assert "MiniMax-M3" in models.stdout
        assert "MiniMax-M2.7" in models.stdout

        models_json = self._run(["--json", "models"], tmp_path)
        model_payload = json.loads(models_json.stdout)
        assert isinstance(model_payload, list)
        assert model_payload[0]["id"] == "MiniMax-M3"

        voices = self._run(["voices"], tmp_path)
        assert "English_Graceful_Lady" in voices.stdout

        voices_json = self._run(["--json", "voices"], tmp_path)
        voice_payload = json.loads(voices_json.stdout)
        assert isinstance(voice_payload, list)
        assert "English_Graceful_Lady" in voice_payload

    def test_missing_api_key_fails_before_network_call(self, tmp_path):
        result = self._run(
            ["--json", "chat", "--prompt", "hello"],
            tmp_path,
            check=False,
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["type"] == "RuntimeError"
        assert "MiniMax API key not found" in payload["error"]
        assert "MINIMAX_API_KEY" in payload["error"]

    def test_invalid_minimax_api_key_reports_api_error(self, tmp_path):
        with _fake_minimax_server(status_code=401) as (base_url, requests_seen):
            result = self._run(
                ["--json", "chat", "--prompt", "hello"],
                tmp_path,
                extra_env={
                    "MINIMAX_API_KEY": "invalid-key",
                    "MINIMAX_BASE_URL": base_url,
                },
                check=False,
            )

        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["type"] == "RuntimeError"
        assert "MiniMax API error" in payload["error"]
        assert requests_seen[0]["authorization"] == "Bearer invalid-key"

    def test_api_mocked_chat_and_tts_workflow(self, tmp_path):
        with _fake_minimax_server() as (base_url, requests_seen):
            chat = self._run(
                ["--json", "chat", "--prompt", "Say ok"],
                tmp_path,
                extra_env={
                    "MINIMAX_API_KEY": "sk-test",
                    "MINIMAX_BASE_URL": base_url,
                },
            )
            chat_payload = json.loads(chat.stdout)
            assert chat_payload["content"] == "mock chat ok"
            assert chat_payload["usage"]["total_tokens"] == 5

            audio_path = tmp_path / "mock.mp3"
            tts = self._run(
                [
                    "--json",
                    "tts",
                    "--text",
                    "Hello from the fake API",
                    "--output",
                    str(audio_path),
                ],
                tmp_path,
                extra_env={
                    "MINIMAX_API_KEY": "sk-test",
                    "MINIMAX_BASE_URL": base_url,
                },
            )
            tts_payload = json.loads(tts.stdout)

        assert tts_payload["output_file"] == str(audio_path)
        assert tts_payload["size_bytes"] == 4
        assert audio_path.read_bytes() == bytes([0xFF, 0xFB, 0x11, 0x22])
        assert any(req["path"].endswith("/chat/completions") for req in requests_seen)
        assert any(req["path"].endswith("/v1/t2a_v2") for req in requests_seen)


# ── Chat ───────────────────────────────────────────────────────────────────────

def test_chat_completion_e2e():
    """Test chat completion — real API if key present, otherwise mock."""
    if not API_KEY:
        mock_response = {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            result = chat_completion(
                api_key="sk-mock",
                model="MiniMax-M3",
                messages=[{"role": "user", "content": "Say ok"}],
            )
            assert result["choices"][0]["message"]["content"] == "ok"
        return

    result = chat_completion(
        api_key=API_KEY,
        model="MiniMax-M3",
        messages=[{"role": "user", "content": "Say 'ok'"}],
        max_tokens=10,
    )
    assert "choices" in result
    assert result["choices"][0]["message"]["content"]


def test_chat_completion_highspeed_model_e2e():
    """Test MiniMax-M2.7-highspeed model."""
    if not API_KEY:
        mock_response = {
            "choices": [{"message": {"role": "assistant", "content": "done"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            result = chat_completion(
                api_key="sk-mock",
                model="MiniMax-M2.7-highspeed",
                messages=[{"role": "user", "content": "Say done"}],
            )
            body = mock_post.call_args[1]["json"]
            assert body["model"] == "MiniMax-M2.7-highspeed"
            assert result["choices"][0]["message"]["content"] == "done"
        return

    result = chat_completion(
        api_key=API_KEY,
        model="MiniMax-M2.7-highspeed",
        messages=[{"role": "user", "content": "Say 'done'"}],
        max_tokens=10,
    )
    assert "choices" in result
    assert result["choices"][0]["message"]["content"]


def test_chat_stream_e2e():
    """Test streaming chat."""
    if not API_KEY:
        mock_chunks = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            b'data: {"choices": [{"delta": {"content": "!"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_lines.return_value = mock_chunks
            mock_post.return_value = mock_resp

            full = ""

            def on_chunk(c):
                nonlocal full
                full += c

            chat_completion_stream(
                api_key="sk-mock",
                model="MiniMax-M3",
                messages=[{"role": "user", "content": "Hello"}],
                on_chunk=on_chunk,
            )
            assert full == "Hello!"
        return

    # Real streaming test
    received = []
    chat_completion_stream(
        api_key=API_KEY,
        model="MiniMax-M3",
        messages=[{"role": "user", "content": "Say 'ok' only"}],
        max_tokens=5,
        on_chunk=lambda c: received.append(c),
    )
    assert len(received) > 0


# ── TTS ────────────────────────────────────────────────────────────────────────

def test_tts_e2e(tmp_path):
    """Test TTS synthesis."""
    if not API_KEY:
        hex_audio = bytes([0xFF, 0xFB, 0x00]).hex()
        sse_line = json.dumps({
            "data": {"audio": hex_audio, "status": 2},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_content.return_value = [f"data:{sse_line}\n\n".encode()]
            mock_post.return_value = mock_resp

            out = str(tmp_path / "test.mp3")
            audio = tts_synthesize(
                api_key="sk-mock",
                text="Hello world",
                model="speech-2.8-hd",
                voice="English_Graceful_Lady",
                output_path=out,
            )
            assert len(audio) == 3
        return

    out = str(tmp_path / "real.mp3")
    audio = tts_synthesize(
        api_key=API_KEY,
        text="Hello, this is a test.",
        model="speech-2.8-hd",
        voice="English_Graceful_Lady",
        output_path=out,
    )
    assert len(audio) > 100, "Expected non-trivial audio output"
