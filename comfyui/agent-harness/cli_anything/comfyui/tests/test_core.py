"""Unit tests for ComfyUI CLI harness — no ComfyUI installation required.

Tests cover:
- Workflow load/save/list/validate
- Queue operations (prompt, status, clear, history, interrupt)
- Model listing (checkpoints, LoRAs, VAEs, ControlNets, node info)
- Image listing and downloading
- CLI command parsing and output
- Error handling and edge cases

Run with:
    python -m pytest comfyui/tests/test_core.py
    python -m pytest comfyui/tests/test_core.py -v
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from cli_anything.comfyui.comfyui_cli import cli
from cli_anything.comfyui.core import workflows as workflow_mod
from cli_anything.comfyui.core import queue as queue_mod
from cli_anything.comfyui.core import models as models_mod
from cli_anything.comfyui.core import images as images_mod


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_workflow():
    """Minimal valid ComfyUI workflow (API format)."""
    return {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "v1-5-pruned-emaonly.ckpt"}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a photo of a cat", "clip": ["4", 1]}
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "bad quality", "clip": ["4", 1]}
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"batch_size": 1, "height": 512, "width": 512}
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 7, "denoise": 1, "model": ["4", 0],
                "negative": ["7", 0], "positive": ["6", 0],
                "latent_image": ["5", 0], "sampler_name": "euler",
                "scheduler": "normal", "seed": 42, "steps": 20
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]}
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]}
        }
    }


@pytest.fixture
def workflow_file(tmp_path, sample_workflow):
    """Write sample workflow to a temp file and return the path."""
    p = tmp_path / "test_workflow.json"
    p.write_text(json.dumps(sample_workflow))
    return str(p)


# ── Workflow Tests ───────────────────────────────────────────────

class TestWorkflowLoad:
    """Test workflow file loading."""

    def test_load_valid_workflow(self, workflow_file, sample_workflow):
        """Should load a valid workflow JSON file."""
        result = workflow_mod.load_workflow(workflow_file)
        assert result == sample_workflow
        assert "3" in result

    def test_load_nonexistent_file(self):
        """Should raise RuntimeError for missing file."""
        with pytest.raises(RuntimeError, match="not found"):
            workflow_mod.load_workflow("/nonexistent/path/workflow.json")

    def test_load_non_json_extension(self, tmp_path):
        """Should raise RuntimeError for non-.json file."""
        p = tmp_path / "workflow.txt"
        p.write_text("{}")
        with pytest.raises(RuntimeError, match=".json"):
            workflow_mod.load_workflow(str(p))

    def test_load_invalid_json(self, tmp_path):
        """Should raise RuntimeError for malformed JSON."""
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        with pytest.raises(RuntimeError, match="Invalid JSON"):
            workflow_mod.load_workflow(str(p))

    def test_load_non_dict_json(self, tmp_path):
        """Should raise RuntimeError if JSON root is not a dict."""
        p = tmp_path / "list.json"
        p.write_text("[1, 2, 3]")
        with pytest.raises(RuntimeError, match="JSON object"):
            workflow_mod.load_workflow(str(p))


class TestWorkflowSave:
    """Test workflow file saving."""

    def test_save_workflow(self, tmp_path, sample_workflow):
        """Should save workflow to JSON file."""
        dest = str(tmp_path / "saved.json")
        result = workflow_mod.save_workflow(sample_workflow, dest)
        assert result["status"] == "saved"
        assert result["node_count"] == len(sample_workflow)
        assert Path(dest).exists()
        loaded = json.loads(Path(dest).read_text())
        assert loaded == sample_workflow

    def test_save_creates_parent_dirs(self, tmp_path, sample_workflow):
        """Should create parent directories if they don't exist."""
        dest = str(tmp_path / "nested" / "deep" / "workflow.json")
        result = workflow_mod.save_workflow(sample_workflow, dest)
        assert result["status"] == "saved"
        assert Path(dest).exists()

    def test_save_non_dict_raises(self):
        """Should raise RuntimeError if workflow is not a dict."""
        with pytest.raises(RuntimeError, match="must be a dict"):
            workflow_mod.save_workflow([1, 2, 3], "/tmp/test.json")


class TestWorkflowList:
    """Test listing workflow files in a directory."""

    def test_list_workflows(self, tmp_path, sample_workflow):
        """Should list all JSON files in directory."""
        (tmp_path / "workflow1.json").write_text(json.dumps(sample_workflow))
        (tmp_path / "workflow2.json").write_text(json.dumps({"1": {"class_type": "SaveImage", "inputs": {}}}))
        (tmp_path / "not_json.txt").write_text("ignored")

        result = workflow_mod.list_workflows(str(tmp_path))
        assert len(result) == 2
        filenames = [r["filename"] for r in result]
        assert "workflow1.json" in filenames
        assert "workflow2.json" in filenames

    def test_list_empty_directory(self, tmp_path):
        """Should return empty list for directory with no JSON files."""
        result = workflow_mod.list_workflows(str(tmp_path))
        assert result == []

    def test_list_nonexistent_directory(self):
        """Should raise RuntimeError for nonexistent directory."""
        with pytest.raises(RuntimeError, match="not found"):
            workflow_mod.list_workflows("/nonexistent/dir/xyz")


class TestWorkflowValidate:
    """Test workflow validation."""

    def test_valid_workflow(self, sample_workflow):
        """Should pass validation for a well-formed workflow."""
        result = workflow_mod.validate_workflow(sample_workflow)
        assert result["valid"] is True
        assert result["node_count"] == len(sample_workflow)
        assert result["errors"] == []

    def test_empty_workflow(self):
        """Should warn about empty workflow but not fail."""
        result = workflow_mod.validate_workflow({})
        assert result["valid"] is True
        assert any("empty" in w.lower() for w in result["warnings"])

    def test_missing_class_type(self):
        """Should error on node missing class_type."""
        wf = {"1": {"inputs": {"text": "hello"}}}
        result = workflow_mod.validate_workflow(wf)
        assert result["valid"] is False
        assert any("class_type" in e for e in result["errors"])

    def test_non_dict_inputs(self):
        """Should error when inputs is not a dict."""
        wf = {"1": {"class_type": "CLIPTextEncode", "inputs": ["bad"]}}
        result = workflow_mod.validate_workflow(wf)
        assert result["valid"] is False

    def test_non_dict_workflow(self):
        """Should fail validation if workflow is not a dict."""
        result = workflow_mod.validate_workflow("not a dict")
        assert result["valid"] is False
        assert result["node_count"] == 0


# ── Queue Tests ──────────────────────────────────────────────────

class TestQueuePrompt:
    """Test submitting prompts to the queue."""

    def test_queue_prompt_success(self, sample_workflow):
        """Should return prompt_id and queue position."""
        mock_response = {
            "prompt_id": "abc-123-def",
            "number": 0,
            "node_errors": {},
        }
        with patch("cli_anything.comfyui.core.queue.api_post", return_value=mock_response):
            result = queue_mod.queue_prompt("http://localhost:8188", sample_workflow)

        assert result["prompt_id"] == "abc-123-def"
        assert result["number"] == 0
        assert result["node_errors"] == {}
        assert "client_id" in result

    def test_queue_prompt_with_client_id(self, sample_workflow):
        """Should use provided client_id."""
        mock_response = {"prompt_id": "xyz", "number": 1, "node_errors": {}}
        with patch("cli_anything.comfyui.core.queue.api_post", return_value=mock_response) as mock_post:
            result = queue_mod.queue_prompt("http://localhost:8188", sample_workflow, client_id="my-client")

        assert result["client_id"] == "my-client"
        call_args = mock_post.call_args
        assert call_args[0][2]["client_id"] == "my-client"

    def test_queue_empty_workflow_raises(self):
        """Should raise RuntimeError for empty workflow."""
        with pytest.raises(RuntimeError, match="empty"):
            queue_mod.queue_prompt("http://localhost:8188", {})

    def test_queue_prompt_server_error_raises(self, sample_workflow):
        """Should raise RuntimeError when server returns error."""
        mock_response = {
            "error": {"message": "Invalid prompt", "type": "value_error"}
        }
        with patch("cli_anything.comfyui.core.queue.api_post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="rejected"):
                queue_mod.queue_prompt("http://localhost:8188", sample_workflow)


class TestQueueStatus:
    """Test queue status retrieval."""

    def test_get_queue_status(self):
        """Should return running and pending counts."""
        mock_response = {
            "queue_running": [["abc", {}, {}, {}]],
            "queue_pending": [["def", {}, {}, {}], ["ghi", {}, {}, {}]],
        }
        with patch("cli_anything.comfyui.core.queue.api_get", return_value=mock_response):
            result = queue_mod.get_queue_status("http://localhost:8188")

        assert result["running_count"] == 1
        assert result["pending_count"] == 2

    def test_get_queue_status_empty(self):
        """Should handle empty queue."""
        mock_response = {"queue_running": [], "queue_pending": []}
        with patch("cli_anything.comfyui.core.queue.api_get", return_value=mock_response):
            result = queue_mod.get_queue_status("http://localhost:8188")

        assert result["running_count"] == 0
        assert result["pending_count"] == 0


class TestQueueClear:
    """Test queue clearing."""

    def test_clear_queue(self):
        """Should return cleared status."""
        with patch("cli_anything.comfyui.core.queue.api_delete", return_value={"status": "ok"}):
            result = queue_mod.clear_queue("http://localhost:8188")

        assert result["status"] == "cleared"

    def test_clear_queue_passes_clear_flag(self):
        """Should pass clear=True to the API."""
        with patch("cli_anything.comfyui.core.queue.api_delete", return_value={}) as mock_del:
            queue_mod.clear_queue("http://localhost:8188")

        call_args = mock_del.call_args
        # data kwarg or positional arg should contain {"clear": True}
        data_arg = call_args[1].get("data") or (call_args[0][2] if len(call_args[0]) > 2 else None)
        assert data_arg == {"clear": True}


class TestQueueHistory:
    """Test prompt history retrieval."""

    def test_get_history(self):
        """Should format history entries with outputs."""
        mock_response = {
            "abc-123": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
                "status": {"status_str": "success", "completed": True}
            }
        }
        with patch("cli_anything.comfyui.core.queue.api_get", return_value=mock_response):
            result = queue_mod.get_history("http://localhost:8188")

        assert result["total"] == 1
        assert "abc-123" in result["history"]
        entry = result["history"]["abc-123"]
        assert entry["completed"] is True
        assert len(entry["outputs"]) == 1
        assert entry["outputs"][0]["filename"] == "ComfyUI_00001_.png"

    def test_get_prompt_history_not_found(self):
        """Should raise RuntimeError when prompt ID not in history."""
        with patch("cli_anything.comfyui.core.queue.api_get", return_value={}):
            with pytest.raises(RuntimeError, match="not found"):
                queue_mod.get_prompt_history("http://localhost:8188", "nonexistent-id")

    def test_interrupt(self):
        """Should call interrupt endpoint and return status."""
        with patch("cli_anything.comfyui.core.queue.api_post", return_value={}):
            result = queue_mod.interrupt("http://localhost:8188")
        assert result["status"] == "interrupted"


# ── Models Tests ─────────────────────────────────────────────────

class TestModels:
    """Test model listing functions."""

    def _make_checkpoint_response(self, names):
        return {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [names, {}]}}}}

    def _make_lora_response(self, names):
        return {"LoraLoader": {"input": {"required": {"lora_name": [names, {}]}}}}

    def _make_vae_response(self, names):
        return {"VAELoader": {"input": {"required": {"vae_name": [names, {}]}}}}

    def _make_controlnet_response(self, names):
        return {"ControlNetLoader": {"input": {"required": {"control_net_name": [names, {}]}}}}

    def test_list_checkpoints(self):
        """Should return sorted list of checkpoint names."""
        mock_resp = self._make_checkpoint_response([
            "sd_xl_base_1.0.safetensors", "v1-5-pruned-emaonly.ckpt", "deliberate_v2.safetensors",
        ])
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = models_mod.list_checkpoints("http://localhost:8188")

        assert isinstance(result, list)
        assert len(result) == 3
        assert result == sorted(result)

    def test_list_loras(self):
        """Should return sorted list of LoRA names."""
        mock_resp = self._make_lora_response(["lora_b.safetensors", "lora_a.safetensors"])
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = models_mod.list_loras("http://localhost:8188")

        assert result == ["lora_a.safetensors", "lora_b.safetensors"]

    def test_list_vaes(self):
        """Should return sorted list of VAE names."""
        mock_resp = self._make_vae_response(["vae-ft-mse-840000-ema-pruned.ckpt"])
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = models_mod.list_vaes("http://localhost:8188")

        assert "vae-ft-mse-840000-ema-pruned.ckpt" in result

    def test_list_controlnets(self):
        """Should return sorted list of ControlNet names."""
        mock_resp = self._make_controlnet_response(["control_v11p_sd15_canny.pth"])
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = models_mod.list_controlnets("http://localhost:8188")

        assert "control_v11p_sd15_canny.pth" in result

    def test_list_checkpoints_bad_response_raises(self):
        """Should raise RuntimeError on unexpected API response."""
        with patch("cli_anything.comfyui.core.models.api_get", return_value={}):
            with pytest.raises(RuntimeError, match="checkpoint"):
                models_mod.list_checkpoints("http://localhost:8188")

    def test_get_node_info(self):
        """Should return formatted node schema."""
        mock_resp = {
            "KSampler": {
                "display_name": "KSampler",
                "description": "Samples latents",
                "category": "sampling",
                "input": {"required": {"steps": [["INT"], {"default": 20}]}},
                "output": ["LATENT"],
                "output_name": ["LATENT"],
            }
        }
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = models_mod.get_node_info("http://localhost:8188", "KSampler")

        assert result["class_type"] == "KSampler"
        assert result["category"] == "sampling"

    def test_get_node_info_not_found_raises(self):
        """Should raise RuntimeError when node class not in response."""
        with patch("cli_anything.comfyui.core.models.api_get", return_value={}):
            with pytest.raises(RuntimeError, match="not found"):
                models_mod.get_node_info("http://localhost:8188", "NonExistentNode")

    def test_list_all_node_classes(self):
        """Should return sorted list of all node class names."""
        mock_resp = {"KSampler": {}, "CLIPTextEncode": {}, "SaveImage": {}}
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = models_mod.list_all_node_classes("http://localhost:8188")

        assert result == ["CLIPTextEncode", "KSampler", "SaveImage"]


# ── Images Tests ─────────────────────────────────────────────────

class TestImages:
    """Test image listing and downloading."""

    def test_list_output_images(self):
        """Should return list of image file refs for a prompt."""
        mock_history = {
            "prompt_id": "abc-123",
            "status": "success",
            "completed": True,
            "outputs": [
                {"node_id": "9", "filename": "ComfyUI_00001_.png",
                 "subfolder": "", "type": "output"}
            ]
        }
        with patch("cli_anything.comfyui.core.images.get_prompt_history",
                   return_value=mock_history):
            result = images_mod.list_output_images("http://localhost:8188", "abc-123")

        assert len(result) == 1
        assert result[0]["filename"] == "ComfyUI_00001_.png"

    def test_list_output_images_incomplete_raises(self):
        """Should raise RuntimeError when prompt not yet complete."""
        mock_history = {
            "prompt_id": "abc-123",
            "status": "running",
            "completed": False,
            "outputs": []
        }
        with patch("cli_anything.comfyui.core.images.get_prompt_history",
                   return_value=mock_history):
            with pytest.raises(RuntimeError, match="not completed"):
                images_mod.list_output_images("http://localhost:8188", "abc-123")

    def test_download_image(self, tmp_path):
        """Should download image bytes and write to disk."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        dest = str(tmp_path / "output.png")

        with patch("cli_anything.comfyui.core.images.api_get_raw", return_value=fake_png):
            result = images_mod.download_image(
                base_url="http://localhost:8188",
                filename="ComfyUI_00001_.png",
                output_path=dest,
            )

        assert result["status"] == "downloaded"
        assert result["size_bytes"] == len(fake_png)
        assert Path(dest).read_bytes() == fake_png

    def test_download_image_no_overwrite_raises(self, tmp_path):
        """Should raise RuntimeError when output file exists and overwrite=False."""
        dest = tmp_path / "existing.png"
        dest.write_bytes(b"existing content")

        with pytest.raises(RuntimeError, match="already exists"):
            images_mod.download_image(
                base_url="http://localhost:8188",
                filename="ComfyUI_00001_.png",
                output_path=str(dest),
                overwrite=False,
            )

    def test_download_image_overwrite(self, tmp_path):
        """Should overwrite existing file when overwrite=True."""
        dest = tmp_path / "existing.png"
        dest.write_bytes(b"old content")
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

        with patch("cli_anything.comfyui.core.images.api_get_raw", return_value=fake_png):
            images_mod.download_image(
                base_url="http://localhost:8188",
                filename="ComfyUI_00001_.png",
                output_path=str(dest),
                overwrite=True,
            )

        assert dest.read_bytes() == fake_png

    def test_download_prompt_images(self, tmp_path):
        """Should download all images for a prompt to a directory."""
        mock_history = {
            "prompt_id": "abc-123",
            "status": "success",
            "completed": True,
            "outputs": [
                {"node_id": "9", "filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"},
                {"node_id": "9", "filename": "ComfyUI_00002_.png", "subfolder": "", "type": "output"},
            ]
        }
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20

        with patch("cli_anything.comfyui.core.images.get_prompt_history", return_value=mock_history), \
             patch("cli_anything.comfyui.core.images.api_get_raw", return_value=fake_png):
            results = images_mod.download_prompt_images(
                base_url="http://localhost:8188",
                prompt_id="abc-123",
                output_dir=str(tmp_path),
            )

        assert len(results) == 2
        assert all(r["status"] == "downloaded" for r in results)


# ── CLI Integration Tests ─────────────────────────────────────────

class TestCLIWorkflow:
    """Test CLI workflow commands."""

    def test_workflow_list(self, runner, tmp_path, sample_workflow):
        """workflow list should display JSON files."""
        (tmp_path / "my_wf.json").write_text(json.dumps(sample_workflow))

        result = runner.invoke(cli, ["workflow", "list", str(tmp_path)])
        assert result.exit_code == 0
        assert "my_wf.json" in result.output

    def test_workflow_validate_valid(self, runner, workflow_file):
        """workflow validate should pass for a valid workflow."""
        result = runner.invoke(cli, ["workflow", "validate", workflow_file])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_workflow_validate_json_output(self, runner, workflow_file):
        """--json flag should produce valid JSON output."""
        result = runner.invoke(cli, ["--json", "workflow", "validate", workflow_file])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "valid" in data
        assert "node_count" in data


class TestCLIQueue:
    """Test CLI queue commands."""

    def test_queue_prompt(self, runner, workflow_file):
        """queue prompt should queue a workflow and show prompt_id."""
        mock_response = {"prompt_id": "test-id-999", "number": 0, "node_errors": {}}
        with patch("cli_anything.comfyui.core.queue.api_post", return_value=mock_response):
            result = runner.invoke(cli, ["queue", "prompt", "--workflow", workflow_file])

        assert result.exit_code == 0
        assert "test-id-999" in result.output

    def test_queue_status(self, runner):
        """queue status should show running and pending counts."""
        mock_response = {"queue_running": [], "queue_pending": [["id1", {}, {}, {}]]}
        with patch("cli_anything.comfyui.core.queue.api_get", return_value=mock_response):
            result = runner.invoke(cli, ["queue", "status"])

        assert result.exit_code == 0
        assert "1" in result.output

    def test_queue_clear_with_confirm(self, runner):
        """queue clear --confirm should skip prompt and clear."""
        with patch("cli_anything.comfyui.core.queue.api_delete", return_value={}):
            result = runner.invoke(cli, ["queue", "clear", "--confirm"])

        assert result.exit_code == 0
        assert "cleared" in result.output

    def test_queue_history_json(self, runner):
        """queue history --json should return valid JSON."""
        mock_response = {
            "abc": {"outputs": {}, "status": {"status_str": "success", "completed": True}}
        }
        with patch("cli_anything.comfyui.core.queue.api_get", return_value=mock_response):
            result = runner.invoke(cli, ["--json", "queue", "history"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "history" in data
        assert "total" in data


class TestCLIModels:
    """Test CLI models commands."""

    def test_models_checkpoints(self, runner):
        """models checkpoints should list checkpoint names."""
        mock_resp = {
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": [["v1-5-pruned-emaonly.ckpt", "sd_xl_base_1.0.safetensors"], {}]}}
            }
        }
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = runner.invoke(cli, ["models", "checkpoints"])

        assert result.exit_code == 0
        assert "v1-5-pruned-emaonly.ckpt" in result.output

    def test_models_checkpoints_json(self, runner):
        """models checkpoints --json should return a JSON array."""
        mock_resp = {
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": [["model_a.safetensors"], {}]}}
            }
        }
        with patch("cli_anything.comfyui.core.models.api_get", return_value=mock_resp):
            result = runner.invoke(cli, ["--json", "models", "checkpoints"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert "model_a.safetensors" in data


class TestCLIImages:
    """Test CLI images commands."""

    def test_images_list(self, runner):
        """images list should show output filenames."""
        mock_history = {
            "prompt_id": "abc-123",
            "status": "success",
            "completed": True,
            "outputs": [{"node_id": "9", "filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]
        }
        with patch("cli_anything.comfyui.core.images.get_prompt_history", return_value=mock_history):
            result = runner.invoke(cli, ["images", "list", "--prompt-id", "abc-123"])

        assert result.exit_code == 0
        assert "ComfyUI_00001_.png" in result.output

    def test_images_download(self, runner, tmp_path):
        """images download should save file to disk."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30
        dest = str(tmp_path / "out.png")

        with patch("cli_anything.comfyui.core.images.api_get_raw", return_value=fake_png):
            result = runner.invoke(cli, [
                "images", "download",
                "--filename", "ComfyUI_00001_.png",
                "--output", dest,
            ])

        assert result.exit_code == 0
        assert "downloaded" in result.output.lower()
        assert Path(dest).exists()


class TestCLISystem:
    """Test CLI system commands."""

    def test_system_stats(self, runner):
        """system stats should display server info."""
        mock_stats = {
            "system": {"os": "linux", "python_version": "3.11"},
            "devices": [{"name": "NVIDIA RTX 3060", "vram_total": 12884901888}]
        }
        with patch("cli_anything.comfyui.comfyui_cli.api_get", return_value=mock_stats):
            result = runner.invoke(cli, ["system", "stats"])

        assert result.exit_code == 0

    def test_system_stats_json(self, runner):
        """system stats --json should return valid JSON."""
        mock_stats = {"system": {"os": "linux"}, "devices": []}
        with patch("cli_anything.comfyui.comfyui_cli.api_get", return_value=mock_stats):
            result = runner.invoke(cli, ["--json", "system", "stats"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "system" in data


# ── Backend Tests ────────────────────────────────────────────────

class TestBackend:
    """Test comfyui_backend HTTP wrappers."""

    def test_api_get_success(self):
        """api_get should return parsed JSON on success."""
        from cli_anything.comfyui.utils.comfyui_backend import api_get

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"result": "ok"}'
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status = MagicMock()

        with patch("cli_anything.comfyui.utils.comfyui_backend.requests.get",
                   return_value=mock_resp):
            result = api_get("http://localhost:8188", "/queue")

        assert result == {"result": "ok"}

    def test_api_get_connection_error(self):
        """api_get should raise RuntimeError on connection failure."""
        import requests as req
        from cli_anything.comfyui.utils.comfyui_backend import api_get

        with patch("cli_anything.comfyui.utils.comfyui_backend.requests.get",
                   side_effect=req.exceptions.ConnectionError("refused")):
            with pytest.raises(RuntimeError, match="Cannot connect"):
                api_get("http://localhost:8188", "/queue")

    def test_api_post_success(self):
        """api_post should return parsed JSON on success."""
        from cli_anything.comfyui.utils.comfyui_backend import api_post

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"prompt_id": "abc"}'
        mock_resp.json.return_value = {"prompt_id": "abc"}
        mock_resp.raise_for_status = MagicMock()

        with patch("cli_anything.comfyui.utils.comfyui_backend.requests.post",
                   return_value=mock_resp):
            result = api_post("http://localhost:8188", "/prompt", {"prompt": {}})

        assert result["prompt_id"] == "abc"

    def test_api_delete_success(self):
        """api_delete should return ok status on 204."""
        from cli_anything.comfyui.utils.comfyui_backend import api_delete

        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        mock_resp.raise_for_status = MagicMock()

        with patch("cli_anything.comfyui.utils.comfyui_backend.requests.delete",
                   return_value=mock_resp):
            result = api_delete("http://localhost:8188", "/queue")

        assert result == {"status": "ok"}

    def test_api_get_raw_returns_bytes(self):
        """api_get_raw should return raw bytes."""
        from cli_anything.comfyui.utils.comfyui_backend import api_get_raw

        fake_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_bytes
        mock_resp.raise_for_status = MagicMock()

        with patch("cli_anything.comfyui.utils.comfyui_backend.requests.get",
                   return_value=mock_resp):
            result = api_get_raw("http://localhost:8188", "/view",
                                 params={"filename": "ComfyUI_00001_.png", "type": "output"})

        assert result == fake_bytes

    def test_api_get_timeout_raises(self):
        """api_get should raise RuntimeError on timeout."""
        import requests as req
        from cli_anything.comfyui.utils.comfyui_backend import api_get

        with patch("cli_anything.comfyui.utils.comfyui_backend.requests.get",
                   side_effect=req.exceptions.Timeout()):
            with pytest.raises(RuntimeError, match="timed out"):
                api_get("http://localhost:8188", "/queue")
