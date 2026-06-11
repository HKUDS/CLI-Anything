"""E2E tests for cli-anything-web-yu-pri."""

import json
import os
import subprocess
import sys

import pytest


def _run_cli(args, check=True):
    command = [sys.executable, "-m", "cli_anything.web_yu_pri.web_yu_pri_cli"] + args
    return subprocess.run(command, capture_output=True, text=True, check=check)


def test_dry_run_cli_workflow(tmp_path):
    items_path = tmp_path / "items.json"
    items_path.write_text(
        json.dumps(
            {
                "items": [
                    {"description": "Award plaque", "value": 8000, "quantity": 1, "country": "KR"},
                    {"description": "Certificate", "value": 9000, "quantity": 1, "country": "KR"},
                ]
            }
        ),
        encoding="utf-8",
    )
    result = _run_cli(["--json", "contents", "fill", str(items_path), "--dry-run"])
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert data["plan"]["computed_total"] == 17000
    assert data["safety"]["final_submit_clicked"] is False
    assert "item_description" in data["selectors"]


@pytest.mark.skipif(
    os.environ.get("WEB_YU_PRI_LIVE_E2E") != "1",
    reason="requires a real Japan Post account and logged-in browser profile",
)
def test_live_status_against_contents_page():
    result = _run_cli(["--json", "status", "--url", "https://mgr.post.japanpost.jp/M060800.do"])
    data = json.loads(result.stdout)
    assert data["url"].startswith("https://mgr.post.japanpost.jp/")
    assert "title" in data
