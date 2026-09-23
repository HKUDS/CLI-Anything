"""GUI evidence for the OrcaRouter provider, generated from the real interface.

Drives the harness's own loopback settings page (``cli-anything-orcarouter ui``)
with Playwright and Chromium, and writes screenshots plus a manifest into the
checkout's ``orca-evidence/`` directory.

This is not a mock-up: the page, the assets and the HTTP API it talks to are the
ones the harness ships. Model options come from the live OrcaRouter catalog at
``https://api.orcarouter.ai/v1/models`` using the credential in
``ORCAROUTER_API_KEY``; the API key itself is never rendered, logged, or written
to any artifact.

Run from the repository root:

    ORCAROUTER_API_KEY=sk-orca-… python3 -m pytest orcarouter/agent-harness/tools/test_gui_evidence.py -q

The evidence directory is produced by this run and is deliberately not tracked
by git; the manifest is the artifact the delivery checks read.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS = REPO_ROOT / "orcarouter" / "agent-harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from cli_anything.orcarouter.core import catalog, credentials  # noqa: E402
from cli_anything.orcarouter.core import server as server_mod  # noqa: E402

EVIDENCE_DIR = REPO_ROOT / "orca-evidence"
CATALOG_SOURCE = "https://api.orcarouter.ai/v1/models?capability=chat"
FAKE_KEY = "sk-orca-evidence-00000000000000000000000000000000"
MIN_WIDTH = 800
MIN_HEIGHT = 450


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from the IHDR chunk, without pulling in an image library."""
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    assert header[12:16] == b"IHDR", f"{path.name} has no IHDR chunk"
    return struct.unpack(">II", header[16:24])


def alpha_of(rgba: str) -> float:
    """Alpha channel of a computed `rgb()/rgba()` colour string."""
    if not rgba or rgba in {"transparent", "rgba(0, 0, 0, 0)"}:
        return 0.0
    if rgba.startswith("rgb("):
        return 1.0
    if rgba.startswith("rgba("):
        parts = rgba[rgba.index("(") + 1 : rgba.rindex(")")].split(",")
        return float(parts[3]) if len(parts) == 4 else 1.0
    return 1.0


def test_gui_evidence_from_the_real_settings_page():
    from playwright.sync_api import sync_playwright

    failures: list[str] = []
    ui_by_kind: dict[str, dict] = {}

    def check(condition: bool, label: str, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {label}{(' — ' + detail) if detail else ''}")
        if not condition:
            failures.append(label)

    api_key = os.environ.get("ORCAROUTER_API_KEY", "").strip()
    assert api_key, "ORCAROUTER_API_KEY is required for the live GUI evidence"

    # Live catalog through the implemented provider path, so the counts in the
    # manifest describe exactly what the UI will show.
    credential = credentials.require_credential()
    live = catalog.fetch_live_catalog(credential, capability=catalog.CAPABILITY_CHAT)
    chat_models = catalog.selectable_models(live, catalog.CAPABILITY_CHAT)
    image_models = catalog.selectable_models(
        live, catalog.CAPABILITY_CHAT, required_modalities=("image",)
    )
    assert chat_models and image_models, "live catalog did not provide the required model sets"

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    server, url = server_mod.start_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    screenshots: list[tuple[str, str]] = [
        ("auth-methods", "Both authentication choices side by side, stored key masked"),
        ("text-model-dropdown", "Chat model dropdown expanded, options from the live catalog"),
        ("multimodal-model-dropdown", "Dropdown after attaching an image: image-input chat models"),
    ]

    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(
                executable_path="/usr/bin/chromium", args=["--no-sandbox"]
            )
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="load")
            page.wait_for_selector("#auth-api-key-input")
            page.wait_for_function(
                "() => document.getElementById('model-trigger').disabled === false",
                timeout=20000,
            )

            print("Authentication choices")
            api_key_visible = page.locator("#method-api-key").is_visible()
            pkce_visible = page.locator("#method-pkce").is_visible()
            check(api_key_visible, "api_key_visible")
            check(pkce_visible, "pkce_visible")
            check(
                page.locator("#auth-api-key-input").get_attribute("type") == "password",
                "api_key_field_is_password_input",
            )
            controls_enabled = (
                page.locator("#auth-api-key-save").is_enabled()
                and page.locator("#auth-pkce-connect").is_enabled()
                and page.locator("#auth-pkce-oob").is_enabled()
                and page.locator("#model-trigger").is_enabled()
            )
            check(controls_enabled, "controls_enabled")

            # Store a fake key through the API-key choice and confirm masking.
            page.fill("#auth-api-key-input", FAKE_KEY)
            page.click("#auth-api-key-save")
            page.wait_for_function(
                "() => document.getElementById('auth-masked').textContent.startsWith('sk-orca')",
                timeout=10000,
            )
            masked = page.inner_text("#auth-masked")
            secret_masked = (
                masked != FAKE_KEY and "..." in masked and masked.startswith("sk-orca")
            )
            check(secret_masked, "secret_masked", masked)
            page_content = page.content()
            check(FAKE_KEY not in page_content, "api_key_never_rendered_in_dom")
            check(api_key not in page_content, "live_key_never_rendered_in_dom")

            # PKCE choice is exercised for real: start an out-of-band attempt so
            # the authorization hint and the code field appear, then cancel.
            page.click("#auth-pkce-oob")
            page.wait_for_function(
                "() => document.getElementById('auth-pkce-code-row').hidden === false",
                timeout=10000,
            )
            check(page.locator("#auth-authorize-link").is_visible(), "pkce_authorize_link_visible")
            check(page.locator("#auth-pkce-cancel").is_enabled(), "pkce_cancel_enabled")
            page.click("#auth-pkce-cancel")
            page.wait_for_function(
                "() => document.getElementById('auth-pkce-cancel').disabled === true",
                timeout=10000,
            )
            check(page.locator("#auth-pkce-code-row").is_hidden(), "pkce_cancel_releases_ui")

            ui_by_kind["auth-methods"] = {
                "api_key_visible": api_key_visible,
                "pkce_visible": pkce_visible,
                "secret_masked": secret_masked,
                "controls_enabled": controls_enabled,
            }
            page.screenshot(path=str(EVIDENCE_DIR / "auth-methods.png"))

            print("Text model dropdown")
            page.click("#model-trigger")
            page.wait_for_selector("#model-panel:not([hidden])")
            page.wait_for_function(
                "() => document.querySelectorAll('#model-list li').length > 0", timeout=10000
            )
            trigger_box = page.locator("#model-trigger").bounding_box()
            panel_box = page.locator("#model-panel").bounding_box()
            right_delta = abs(
                (trigger_box["x"] + trigger_box["width"])
                - (panel_box["x"] + panel_box["width"])
            )
            panel_style = page.evaluate(
                """() => {
                    const s = getComputedStyle(document.getElementById('model-panel'));
                    return {bg: s.backgroundColor, bw: s.borderTopWidth, bc: s.borderTopColor};
                }"""
            )
            text_items = page.locator("#model-list li").count()
            text_assertion = {
                "dropdown_open": page.locator("#model-panel").is_visible(),
                "item_count": text_items,
                "opaque_background": alpha_of(panel_style["bg"]) == 1.0,
                "visible_border": float(panel_style["bw"].replace("px", "") or 0) > 0
                and alpha_of(panel_style["bc"]) > 0,
                "trigger_panel_right_delta": round(right_delta, 2),
            }
            ui_by_kind["text-model-dropdown"] = text_assertion
            check(text_assertion["dropdown_open"], "text_dropdown_open")
            check(text_items == len(chat_models), "text_dropdown_has_items", str(text_items))
            check(text_assertion["opaque_background"], "text_dropdown_opaque_background")
            check(text_assertion["visible_border"], "text_dropdown_visible_border")
            check(right_delta <= 2, "text_dropdown_aligned", f"{right_delta:.2f}px")

            ids = page.eval_on_selector_all(
                "#model-list li", "els => els.map(e => e.dataset.modelId)"
            )
            check(
                set(ids) == {m.id for m in chat_models},
                "text_dropdown_matches_live_catalog",
                f"{len(ids)} items",
            )
            page.screenshot(path=str(EVIDENCE_DIR / "text-model-dropdown.png"))

            print("Multimodal model dropdown")
            page.click("#attach-image")
            page.wait_for_function(
                f"() => document.querySelectorAll('#model-list li').length === {len(image_models)}",
                timeout=15000,
            )
            page.click("#model-trigger")
            page.wait_for_selector("#model-panel:not([hidden])")
            image_items = page.locator("#model-list li").count()
            image_ids = page.eval_on_selector_all(
                "#model-list li", "els => els.map(e => e.dataset.modelId)"
            )
            panel_style = page.evaluate(
                """() => {
                    const s = getComputedStyle(document.getElementById('model-panel'));
                    return {bg: s.backgroundColor, bw: s.borderTopWidth, bc: s.borderTopColor};
                }"""
            )
            trigger_box = page.locator("#model-trigger").bounding_box()
            panel_box = page.locator("#model-panel").bounding_box()
            right_delta = abs(
                (trigger_box["x"] + trigger_box["width"])
                - (panel_box["x"] + panel_box["width"])
            )
            image_assertion = {
                "dropdown_open": page.locator("#model-panel").is_visible(),
                "item_count": image_items,
                "opaque_background": alpha_of(panel_style["bg"]) == 1.0,
                "visible_border": float(panel_style["bw"].replace("px", "") or 0) > 0
                and alpha_of(panel_style["bc"]) > 0,
                "trigger_panel_right_delta": round(right_delta, 2),
            }
            ui_by_kind["multimodal-model-dropdown"] = image_assertion
            check(image_items == len(image_models), "multimodal_item_count", str(image_items))
            check(
                set(image_ids) == {m.id for m in image_models},
                "multimodal_dropdown_matches_capability_filter",
            )
            check(image_items < text_items, "multimodal_dropdown_is_narrower_than_text")
            page.screenshot(path=str(EVIDENCE_DIR / "multimodal-model-dropdown.png"))

            print("pagehide / back-forward cache")
            page.click("#attach-image")  # back to the text entry point
            page.wait_for_function(
                f"() => document.querySelectorAll('#model-list li').length === {len(chat_models)}",
                timeout=15000,
            )
            page.click("#auth-pkce-oob")
            page.wait_for_function(
                "() => document.getElementById('auth-pkce-code-row').hidden === false",
                timeout=10000,
            )
            page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
            check(page.locator("#auth-pkce-hint").is_hidden(), "pagehide_clears_hint")
            check(page.locator("#auth-pkce-connect").is_enabled(), "pagehide_clears_busy")
            # A second login must be startable without remounting the page.
            page.click("#auth-pkce-oob")
            page.wait_for_function(
                "() => document.getElementById('auth-pkce-code-row').hidden === false",
                timeout=10000,
            )
            check(True, "second_login_after_pagehide_without_remount")
            page.click("#auth-pkce-cancel")

            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    artifacts = []
    for kind, describes in screenshots:
        path = EVIDENCE_DIR / f"{kind}.png"
        width, height = png_size(path)
        check(
            width >= MIN_WIDTH and height >= MIN_HEIGHT,
            f"{kind}_size",
            f"{width}x{height}",
        )
        check(path.stat().st_size >= 10_000, f"{kind}_file_size", str(path.stat().st_size))
        artifacts.append(
            {
                "kind": kind,
                "path": f"{kind}.png",
                "sha256": sha256_of(path),
                "width": width,
                "height": height,
                "describes": describes,
                "ui": ui_by_kind[kind],
            }
        )

    manifest = {
        "automation": {
            "framework": "playwright",
            "passed": not failures,
            "catalog_source": CATALOG_SOURCE,
            "catalog_model_count": len(chat_models),
            "image_model_count": len(image_models),
        },
        "interface": "orcarouter/agent-harness/cli_anything/orcarouter/ui (served by `cli-anything-orcarouter ui`)",
        "command": (
            "ORCAROUTER_API_KEY=… python3 -m pytest "
            "orcarouter/agent-harness/tools/test_gui_evidence.py -q"
        ),
        "artifacts": artifacts,
        "failures": failures,
    }
    (EVIDENCE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    assert not failures, f"GUI evidence assertion(s) failed: {failures}"


if __name__ == "__main__":  # pragma: no cover - direct invocation
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
