"""E2E tests for cli-anything-ollama — requires Ollama running at localhost:11434.

These tests interact with a real Ollama server. Skip if Ollama is not available.

Usage:
    python -m pytest cli_anything/ollama/tests/test_full_e2e.py -v
"""

import pytest
from click.testing import CliRunner

from cli_anything.ollama.utils.ollama_backend import is_available, DEFAULT_BASE_URL
from cli_anything.ollama.ollama_cli import cli

# Skip all tests if Ollama is not running
pytestmark = pytest.mark.skipif(
    not is_available(DEFAULT_BASE_URL),
    reason="Ollama server not available at localhost:11434"
)

# Small model for testing — tinyllama is ~637MB
TEST_MODEL = "tinyllama"


@pytest.fixture
def runner():
    return CliRunner()


class TestServerE2E:
    def test_server_status(self, runner):
        result = runner.invoke(cli, ["server", "status"])
        assert result.exit_code == 0

    def test_server_version(self, runner):
        result = runner.invoke(cli, ["--json", "server", "version"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "version" in data


class TestModelE2E:
    def test_model_list(self, runner):
        result = runner.invoke(cli, ["--json", "model", "list"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "models" in data

    def test_model_pull(self, runner):
        result = runner.invoke(cli, ["model", "pull", TEST_MODEL, "--no-stream"])
        assert result.exit_code == 0

    def test_model_show(self, runner):
        # Ensure model is pulled first
        runner.invoke(cli, ["model", "pull", TEST_MODEL, "--no-stream"])
        result = runner.invoke(cli, ["--json", "model", "show", TEST_MODEL])
        assert result.exit_code == 0

    def test_model_ps(self, runner):
        result = runner.invoke(cli, ["--json", "model", "ps"])
        assert result.exit_code == 0

    def test_model_copy_and_delete(self, runner):
        # Ensure source exists
        runner.invoke(cli, ["model", "pull", TEST_MODEL, "--no-stream"])
        # Copy
        result = runner.invoke(cli, ["model", "copy", TEST_MODEL, f"{TEST_MODEL}-test-copy"])
        assert result.exit_code == 0
        # Delete copy
        result = runner.invoke(cli, ["model", "rm", f"{TEST_MODEL}-test-copy"])
        assert result.exit_code == 0


class TestGenerateE2E:
    def test_generate_text(self, runner):
        # Ensure model exists
        runner.invoke(cli, ["model", "pull", TEST_MODEL, "--no-stream"])
        result = runner.invoke(cli, ["--json", "generate", "text",
                                     "--model", TEST_MODEL,
                                     "--prompt", "Say hello in one word",
                                     "--no-stream", "--num-predict", "10"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "response" in data

    def test_generate_chat(self, runner):
        # Ensure model exists
        runner.invoke(cli, ["model", "pull", TEST_MODEL, "--no-stream"])
        result = runner.invoke(cli, ["--json", "generate", "chat",
                                     "--model", TEST_MODEL,
                                     "--message", "user:Say hi",
                                     "--no-stream"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "message" in data


class TestEmbedE2E:
    """Embedding tests — requires a model that supports embeddings."""

    @pytest.mark.skipif(True, reason="Requires an embedding model like nomic-embed-text")
    def test_embed_text(self, runner):
        result = runner.invoke(cli, ["--json", "embed", "text",
                                     "--model", "nomic-embed-text",
                                     "--input", "Hello world"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "embeddings" in data


class TestCleanup:
    def test_delete_test_model(self, runner):
        """Clean up test model after all tests."""
        result = runner.invoke(cli, ["model", "rm", TEST_MODEL])
        # Don't assert exit_code — model might not exist
