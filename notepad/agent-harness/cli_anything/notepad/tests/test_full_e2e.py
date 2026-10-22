"""E2E tests for the Notepad GUI harness. Require a live Notepad window.

Skipped unless a Notepad window is found. These tests are READ-ONLY: they
capture the UIA tree and read state, but never drive the GUI, so running them
cannot modify an open document.
"""

import pytest

uia = pytest.importorskip("uiautomation")


def _find_notepad():
    for w in uia.GetRootControl().GetChildren():
        if (w.ClassName or "").lower() == "notepad":
            return w
    return None


@pytest.fixture(scope="module")
def window():
    w = _find_notepad()
    if w is None:
        pytest.skip("no Notepad window found - open Notepad to run E2E")
    return w


def _capture(win, maxdepth=6):
    nodes = []

    def walk(ctrl, chain, depth):
        if depth > maxdepth or len(nodes) > 400:
            return
        for child in ctrl.GetChildren():
            name = child.Name or ""
            ct = child.ControlTypeName or ""
            pats = []
            for pname in ("Invoke", "Value", "ExpandCollapse", "SelectionItem", "Toggle"):
                try:
                    if getattr(child, f"Get{pname}Pattern", lambda: None)():
                        pats.append(pname)
                except Exception:
                    pass
            if name or pats:
                nodes.append({"path": " > ".join(chain + [name or ct]), "control_type": ct, "patterns": pats})
            walk(child, chain + [name or ct], depth + 1)

    walk(win, [win.Name or "window"], 1)
    return nodes


def test_window_is_notepad(window):
    assert (window.ClassName or "").lower() == "notepad"
    assert window.Name


def test_tree_has_text_editor(window):
    nodes = _capture(window)
    editors = [n for n in nodes if n["control_type"] == "DocumentControl"]
    assert editors, "no DocumentControl (text editor) in the UIA tree"
    assert any("Value" in n["patterns"] for n in editors)


def test_tree_has_menu_bar(window):
    nodes = _capture(window)
    menus = [n for n in nodes if "ExpandCollapse" in n["patterns"]]
    assert menus, "no expandable menu items found"
    paths = " ".join(n["path"] for n in menus)
    assert "File" in paths


def test_driving_requires_confirmation():
    """The uia_runner must refuse to act without --yes."""
    import subprocess
    import sys
    from pathlib import Path

    runner = Path(__file__).parent.parent / "utils" / "uia_runner.py"
    proc = subprocess.run(
        [sys.executable, str(runner), "invoke", "Notepad > File", "--process", "Notepad"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert "--yes" in proc.stdout
