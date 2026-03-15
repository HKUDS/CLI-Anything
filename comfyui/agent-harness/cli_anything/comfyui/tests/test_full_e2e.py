"""Full end-to-end tests for ComfyUI CLI harness.

These tests simulate a complete generation workflow using mocked HTTP responses.
They do NOT require ComfyUI to be installed or running.

Run with:
    python -m pytest comfyui/tests/test_full_e2e.py -v
"""

import json
from pathlib import Path
from unittest.mock import patch
import pytest
from click.testing import CliRunner

from cli_anything.comfyui.comfyui_cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_workflow():
    return {
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "a beautiful landscape", "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "ugly, bad", "clip": ["4", 1]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"batch_size": 1, "height": 512, "width": 512}},
        "3": {"class_type": "KSampler",
              "inputs": {"cfg": 7, "denoise": 1, "model": ["4", 0],
                         "negative": ["7", 0], "positive": ["6", 0],
                         "latent_image": ["5", 0], "sampler_name": "euler",
                         "scheduler": "normal", "seed": 12345, "steps": 20}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]}},
    }


@pytest.fixture
def workflow_file(tmp_path, sample_workflow):
    p = tmp_path / "landscape.json"
    p.write_text(json.dumps(sample_workflow))
    return str(p)


class TestFullGenerationWorkflow:
    """Simulate complete generate -> check -> download workflow."""

    def test_queue_and_check_status(self, runner, workflow_file):
        """Full flow: validate workflow -> queue it -> check queue status."""
        prompt_id = "e2e-prompt-001"

        queue_response = {"prompt_id": prompt_id, "number": 0, "node_errors": {}}
        status_response = {
            "queue_running": [["e2e-prompt-001", {}, {}, {}]],
            "queue_pending": [],
        }

        with patch("cli_anything.comfyui.core.queue.api_post", return_value=queue_response), \
             patch("cli_anything.comfyui.core.queue.api_get", return_value=status_response):

            # Step 1: Validate
            result = runner.invoke(cli, ["workflow", "validate", workflow_file])
            assert result.exit_code == 0

            # Step 2: Queue
            result = runner.invoke(cli, ["queue", "prompt", "--workflow", workflow_file])
            assert result.exit_code == 0
            assert prompt_id in result.output

            # Step 3: Check status
            result = runner.invoke(cli, ["queue", "status"])
            assert result.exit_code == 0

    def test_queue_then_download(self, runner, workflow_file, tmp_path):
        """Full flow: queue -> list outputs -> download image."""
        prompt_id = "e2e-prompt-002"
        img_filename = "ComfyUI_00001_.png"
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128

        history_response = {
            prompt_id: {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": img_filename, "subfolder": "", "type": "output"}
                        ]
                    }
                },
                "status": {"status_str": "success", "completed": True}
            }
        }

        dest = str(tmp_path / "downloaded.png")

        with patch("cli_anything.comfyui.core.queue.api_post",
                   return_value={"prompt_id": prompt_id, "number": 0, "node_errors": {}}), \
             patch("cli_anything.comfyui.core.queue.api_get", return_value=history_response), \
             patch("cli_anything.comfyui.core.images.api_get_raw", return_value=fake_png):

            # Queue
            result = runner.invoke(cli, ["queue", "prompt", "--workflow", workflow_file])
            assert result.exit_code == 0

            # List outputs
            result = runner.invoke(cli, ["images", "list", "--prompt-id", prompt_id])
            assert result.exit_code == 0
            assert img_filename in result.output

            # Download
            result = runner.invoke(cli, [
                "images", "download",
                "--filename", img_filename,
                "--output", dest,
            ])
            assert result.exit_code == 0
            assert Path(dest).read_bytes() == fake_png

    def test_json_mode_full_flow(self, runner, workflow_file):
        """All commands in --json mode should produce valid JSON throughout."""
        prompt_id = "e2e-json-003"
        queue_response = {"prompt_id": prompt_id, "number": 0, "node_errors": {}}

        with patch("cli_anything.comfyui.core.queue.api_post", return_value=queue_response):
            result = runner.invoke(cli, ["--json", "queue", "prompt", "--workflow", workflow_file])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["prompt_id"] == prompt_id

    def test_interrupt_generation(self, runner):
        """queue interrupt should stop current generation."""
        with patch("cli_anything.comfyui.core.queue.api_post", return_value={}):
            result = runner.invoke(cli, ["queue", "interrupt"])
        assert result.exit_code == 0
        assert "interrupted" in result.output

    def test_clear_queue_and_verify(self, runner):
        """Clear queue then verify it is empty."""
        empty_status = {"queue_running": [], "queue_pending": []}

        with patch("cli_anything.comfyui.core.queue.api_delete", return_value={}), \
             patch("cli_anything.comfyui.core.queue.api_get", return_value=empty_status):

            result = runner.invoke(cli, ["queue", "clear", "--confirm"])
            assert result.exit_code == 0
            assert "cleared" in result.output

            result = runner.invoke(cli, ["--json", "queue", "status"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["running_count"] == 0
            assert data["pending_count"] == 0


class TestModelDiscovery:
    """Test model listing as part of setup workflow."""

    def test_discover_all_model_types(self, runner):
        """Should list all four model types without error."""
        ckpt_resp = {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["model_a.ckpt"], {}]}}}}
        lora_resp = {"LoraLoader": {"input": {"required": {"lora_name": [["lora_style.safetensors"], {}]}}}}
        vae_resp = {"VAELoader": {"input": {"required": {"vae_name": [["vae.ckpt"], {}]}}}}
        cn_resp = {"ControlNetLoader": {"input": {"required": {"control_net_name": [["canny.pth"], {}]}}}}

        with patch("cli_anything.comfyui.core.models.api_get") as mock_api:
            mock_api.side_effect = [ckpt_resp, lora_resp, vae_resp, cn_resp]

            for cmd in [
                ["models", "checkpoints"],
                ["models", "loras"],
                ["models", "vaes"],
                ["models", "controlnets"],
            ]:
                result = runner.invoke(cli, cmd)
                assert result.exit_code == 0, f"Failed on: {cmd} — {result.output}"


class TestErrorHandling:
    """Test error scenarios are handled gracefully."""

    def test_connection_refused_shows_error(self, runner, workflow_file):
        """Should show friendly error when ComfyUI is not running."""
        with patch("cli_anything.comfyui.core.queue.api_post",
                   side_effect=RuntimeError("Cannot connect to ComfyUI at http://localhost:8188. Is ComfyUI running?")):
            result = runner.invoke(cli, ["queue", "prompt", "--workflow", workflow_file])

        assert result.exit_code != 0
        assert "Cannot connect" in result.output or "Error" in result.output

    def test_server_rejects_workflow_shows_error(self, runner, workflow_file):
        """Should show error message when server rejects the workflow."""
        with patch("cli_anything.comfyui.core.queue.api_post",
                   return_value={"error": {"message": "Node not found: BadNode", "type": "value_error"}}):
            result = runner.invoke(cli, ["queue", "prompt", "--workflow", workflow_file])

        assert result.exit_code != 0
        assert "Error" in result.output or "rejected" in result.output

    def test_nonexistent_workflow_shows_error(self, runner):
        """Should error when workflow file does not exist."""
        result = runner.invoke(cli, ["queue", "prompt", "--workflow", "/nonexistent.json"])
        assert result.exit_code != 0

    def test_download_missing_image_shows_error(self, runner, tmp_path):
        """Should error when trying to download non-existent image."""
        with patch("cli_anything.comfyui.core.images.api_get_raw",
                   side_effect=RuntimeError("ComfyUI API error 404")):
            result = runner.invoke(cli, [
                "images", "download",
                "--filename", "nonexistent.png",
                "--output", str(tmp_path / "out.png"),
            ])

        assert result.exit_code != 0
