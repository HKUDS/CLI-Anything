"""Tests for shared preview bundle helpers."""

import json
import sys
from pathlib import Path


_PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_DIR))

from preview_bundle import PROTOCOL_VERSION, find_latest_manifest


def _write_manifest(
    root: Path,
    *,
    recipe: str,
    bundle_id: str,
    created_at: str,
) -> None:
    bundle_dir = root / "test-app" / recipe / bundle_id
    bundle_dir.mkdir(parents=True)
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "bundle_id": bundle_id,
        "bundle_kind": "capture",
        "software": "test-app",
        "recipe": recipe,
        "status": "ok",
        "created_at": created_at,
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_find_latest_manifest_compares_created_at_across_recipes(tmp_path):
    preview_root = tmp_path / "previews"
    _write_manifest(
        preview_root,
        recipe="z-last-alphabetically",
        bundle_id="20260101T000000Z_old",
        created_at="2026-01-01T00:00:00Z",
    )
    _write_manifest(
        preview_root,
        recipe="a-first-alphabetically",
        bundle_id="20260201T000000Z_new",
        created_at="2026-02-01T00:00:00Z",
    )

    latest = find_latest_manifest("test-app", root_dir=str(preview_root))

    assert latest is not None
    assert latest["bundle_id"] == "20260201T000000Z_new"
