#!/usr/bin/env python3
"""Self-contained UIA runner for this harness.

Subcommands: tree | menus | invoke <path> | select <path> | set-value <path> <text>
Finds the target window by process class or title. Every driving action
requires --yes. Requires: pip install uiautomation
"""

import argparse
import json
import re
import sys

try:
    import uiautomation as auto
except ImportError:
    print(json.dumps({"ok": False, "detail": "pip install uiautomation"}))
    sys.exit(3)

DESTRUCTIVE_RE = re.compile(
    r"save|close|delete|remove|exit|quit|format|discard|overwrite|replace",
    re.IGNORECASE,
)


def find_window(process=None, title=None, pid=None):
    for w in auto.GetRootControl().GetChildren():
        if pid and w.ProcessId == pid:
            return w
        if process and (w.ClassName or "").lower() == process.lower():
            return w
        if title and title.lower() in (w.Name or "").lower():
            return w
    return None


def capture(window, maxdepth=6):
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
                nodes.append(
                    {
                        "path": " > ".join(chain + [name or ct]),
                        "control_type": ct,
                        "name": name,
                        "patterns": pats,
                    }
                )
            walk(child, chain + [name or ct], depth + 1)

    walk(window, [window.Name or "window"], 1)
    return nodes


def resolve(window, path):
    parts = [p for p in path.split(" > ") if p]
    if not parts:
        return None
    found = []

    def walk(ctrl, chain, depth):
        if depth > 8:
            return
        for child in ctrl.GetChildren():
            name = child.Name or ""
            ct = child.ControlTypeName or ""
            full = chain + [name]
            if (
                name == parts[-1]
                and " > ".join(full) == " > ".join(parts)
                or " > ".join(full[-len(parts):]) == " > ".join(parts)
            ):
                found.append(child)
            walk(child, chain + [name or ct], depth + 1)

    walk(window, [window.Name or "window"], 1)
    return found[0] if found else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--process", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--allow-destructive", action="store_true")
    a = ap.parse_args()

    window = find_window(a.process, a.title, a.pid)
    if not window:
        print(json.dumps({"ok": False, "detail": "target window not found"}))
        return 2

    if a.cmd == "tree":
        print(json.dumps({"ok": True, "window": window.Name, "nodes": capture(window)}))
        return 0
    if a.cmd == "menus":
        nodes = capture(window)
        menus = [n["path"] for n in nodes if "ExpandCollapse" in n["patterns"]]
        print(json.dumps({"ok": True, "menus": menus}))
        return 0

    if not a.yes:
        print(json.dumps({"ok": False, "detail": "driving requires --yes"}))
        return 2
    path = a.args[0] if a.args else ""
    if DESTRUCTIVE_RE.search(path) and not a.allow_destructive:
        print(json.dumps({"ok": False, "detail": "destructive-looking path refused"}))
        return 2
    node = resolve(window, path)
    if not node:
        print(json.dumps({"ok": False, "detail": "node not found: " + path}))
        return 2
    try:
        if a.cmd == "invoke":
            node.GetInvokePattern().Invoke()
        elif a.cmd == "select":
            node.GetSelectionItemPattern().Select()
        elif a.cmd == "set-value":
            node.GetValuePattern().SetValue(a.args[1] if len(a.args) > 1 else "")
        else:
            print(json.dumps({"ok": False, "detail": "unknown cmd"}))
            return 2
    except Exception as e:
        print(json.dumps({"ok": False, "detail": f"{type(e).__name__}: {e}"}))
        return 2
    print(json.dumps({"ok": True, "action": a.cmd, "path": path}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
