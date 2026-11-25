import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from cli_anything.flowise.backend import Flowise


@pytest.mark.skipif(os.getenv("FLOWISE_E2E") != "1", reason="Enable against a disposable Flowise server")
def test_installed_cli_manages_and_runs_an_agentflow(tmp_path):
    cli = shutil.which("cli-anything-flowise")
    assert cli, "Install cli-anything-flowise before running against Flowise"
    graph_path = Path(__file__).with_name("fixtures") / "hello-agentflow.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    backend = Flowise(os.environ["FLOWISE_URL"], os.environ["FLOWISE_API_KEY"], None)

    def run(*args):
        completed = subprocess.run(
            [cli, "--json", *args], text=True,
            capture_output=True, timeout=125,
        )
        assert completed.returncode == 0, completed.stdout or completed.stderr
        return json.loads(completed.stdout)

    name = f"cli-anything-e2e-{uuid4().hex}"
    created = run("flow", "create", name, str(graph_path), "--type", "AGENTFLOW")
    flow_id = created["id"]
    try:
        listing = run("flow", "list")
        if isinstance(listing, dict):
            listing = listing["data"]
        assert any(item["id"] == flow_id for item in listing)
        assert run("flow", "export", flow_id) == graph
        graph["nodes"][1]["data"]["inputs"]["directReplyMessage"] = "Updated by CLI-Anything"
        updated_graph = tmp_path / "updated.json"
        updated_graph.write_text(json.dumps(graph), encoding="utf-8")
        run("flow", "update", flow_id, "--name", f"{name}-updated", "--graph", str(updated_graph))
        assert run("flow", "export", flow_id) == graph
        run("flow", "deploy", flow_id)
        saved = run("flow", "show", flow_id)
        assert saved["name"] == f"{name}-updated"
        assert saved["deployed"] is True
        assert run("predict", flow_id, "--question", "cli smoke")["text"] == "Updated by CLI-Anything"
    finally:
        backend._request("DELETE", backend._flow_route(flow_id))
