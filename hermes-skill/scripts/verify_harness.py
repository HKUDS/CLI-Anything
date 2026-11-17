#!/usr/bin/env python3
"""Verify that a CLI-Anything harness satisfies the published harness contract.

The checks mirror `cli-anything-plugin/HARNESS.md`, `CONTRIBUTING.md` and the
root-skill mirror rule enforced by `.github/scripts/validate_root_skills.py`.
They are deliberately mechanical: each check fails with the file it expected and
the convention it came from, so an agent can act on the output without reading
the whole methodology.

Usage:
    python3 verify_harness.py <path> [<path> ...] [--json] [--strict]
    python3 verify_harness.py --all [--json]

`<path>` may be the software directory (`<software>/`) or its `agent-harness/`
directory. Exit code is 1 when any check with severity `error` fails. With
`--strict`, warnings fail too.

No third-party dependencies; Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PASS = "pass"
WARN = "warn"
FAIL = "fail"

REPO_MARKERS = ("cli-anything-plugin", "registry.json")


class Check(object):
    def __init__(self, check_id, status, detail, severity="error"):
        self.id = check_id
        self.status = status
        self.detail = detail
        self.severity = severity

    def as_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
        }


def find_repo_root(start):
    """Walk up looking for the CLI-Anything checkout that owns this harness."""
    for candidate in [start] + list(start.parents):
        if all((candidate / marker).exists() for marker in REPO_MARKERS):
            return candidate
    return None


def resolve_harness(path):
    """Accept either <software>/ or <software>/agent-harness/."""
    path = path.resolve()
    if path.name == "agent-harness" and path.is_dir():
        return path
    nested = path / "agent-harness"
    if nested.is_dir():
        return nested
    return path


def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def slugify(name):
    """Canonical CLI id: package and skill names are lowercase for every target.

    Software directories keep their upstream display name (`QGIS`, `3MF`) while the
    console script and skill mirror are `cli-anything-qgis` and
    `skills/cli-anything-qgis/`, so path derivation must not reuse the directory name.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def python_sources(root):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def check_layout(harness, software):
    checks = []
    module_root = harness / "cli_anything"
    if not module_root.is_dir():
        checks.append(Check("namespace-package", FAIL, "missing cli_anything/ namespace root"))
        return checks, None

    top_level_init = module_root / "__init__.py"
    if top_level_init.exists():
        checks.append(Check(
            "namespace-package",
            WARN,
            "cli_anything/__init__.py exists; the namespace root is meant to stay implicit",
            severity="warn",
        ))
    else:
        checks.append(Check("namespace-package", PASS, "cli_anything/ is a namespace package"))

    modules = sorted(p for p in module_root.iterdir() if p.is_dir() and not p.name.startswith("__"))
    if not modules:
        checks.append(Check("module-dir", FAIL, "cli_anything/ contains no package directory"))
        return checks, None

    expected = module_root / software.replace("-", "_")
    module = expected if expected.is_dir() else modules[0]
    checks.append(Check("module-dir", PASS, "package directory: cli_anything/%s" % module.name))

    cli_module = module / ("%s_cli.py" % module.name)
    checks.append(Check(
        "entry-module-cli",
        PASS if cli_module.is_file() else FAIL,
        "found %s_cli.py" % module.name if cli_module.is_file() else "missing %s_cli.py" % module.name,
    ))
    main_module = module / "__main__.py"
    checks.append(Check(
        "entry-module-main",
        PASS if main_module.is_file() else WARN,
        "found __main__.py" if main_module.is_file() else "no __main__.py; `python -m` entry is unavailable",
        severity="warn",
    ))
    return checks, module


def check_setup(harness, slug, module):
    setup_py = harness / "setup.py"
    if not setup_py.is_file():
        return [Check("setup-py", FAIL, "missing setup.py")]

    text = read(setup_py)
    checks = [Check("setup-py", PASS, "setup.py present")]
    entry = "cli-anything-%s" % slug
    entry_pattern = re.compile(r"cli-anything-%s\s*=\s*[\w.]+\s*:" % re.escape(slug))
    if "console_scripts" in text and entry_pattern.search(text):
        checks.append(Check("console-script", PASS, "console_scripts exposes %s" % entry))
    else:
        checks.append(Check(
            "console-script",
            FAIL,
            "setup.py must expose %s through console_scripts (name = module:function)" % entry,
        ))

    if "find_namespace_packages" in text:
        checks.append(Check("namespace-packages", PASS, "find_namespace_packages declared"))
    else:
        checks.append(Check(
            "namespace-packages",
            FAIL,
            "setup.py must use find_namespace_packages(include=['cli_anything.*'])",
        ))
    return checks


def check_cli_surface(module, repo_root):
    sources = python_sources(module) if module else []
    joined = "\n".join(read(p) for p in sources)
    checks = []

    checks.append(Check(
        "json-output",
        PASS if '"--json"' in joined or "'--json'" in joined else FAIL,
        "global --json option found" if '"--json"' in joined or "'--json'" in joined
        else "no --json option in the CLI sources",
    ))
    checks.append(Check(
        "repl-default",
        PASS if "invoke_without_command=True" in joined else FAIL,
        "REPL runs when no subcommand is given" if "invoke_without_command=True" in joined
        else "Click group needs invoke_without_command=True and a REPL fallback",
    ))
    checks.append(Check(
        "dry-run",
        PASS if "--dry-run" in joined else WARN,
        "--dry-run present" if "--dry-run" in joined
        else "no --dry-run option; mutations should be previewable",
        severity="warn",
    ))

    skin = module / "utils" / "repl_skin.py" if module else None
    canonical = repo_root / "cli-anything-plugin" / "repl_skin.py" if repo_root else None
    if skin is None or not skin.is_file():
        checks.append(Check("repl-skin", FAIL, "missing utils/repl_skin.py"))
    elif canonical is None or not canonical.is_file():
        checks.append(Check("repl-skin", WARN, "utils/repl_skin.py present; canonical copy not resolvable", severity="warn"))
    elif skin.read_bytes() == canonical.read_bytes():
        checks.append(Check("repl-skin", PASS, "utils/repl_skin.py matches the canonical copy"))
    else:
        checks.append(Check(
            "repl-skin",
            WARN,
            "utils/repl_skin.py differs from cli-anything-plugin/repl_skin.py",
            severity="warn",
        ))
    return checks


def check_docs_and_tests(harness, software, slug, module, repo_root):
    checks = []

    sop = None
    for candidate in harness.iterdir() if harness.is_dir() else []:
        if candidate.is_file() and candidate.name.lower() == "%s.md" % software.lower():
            sop = candidate
    checks.append(Check(
        "sop-doc",
        PASS if sop else WARN,
        "found %s" % sop.name if sop else "missing %s.md architecture SOP" % software.upper(),
        severity="warn" if not sop else "error",
    ))

    tests_dir = module / "tests" if module else None
    for name, label in (("test_core.py", "unit tests"), ("test_full_e2e.py", "E2E tests")):
        target = tests_dir / name if tests_dir else None
        checks.append(Check(
            "tests-%s" % name.replace("test_", "").replace(".py", ""),
            PASS if target is not None and target.is_file() else FAIL,
            "found %s" % name if target is not None and target.is_file() else "missing %s (%s)" % (name, label),
        ))

    test_md = None
    for candidate in harness.rglob("TEST.md") if harness.is_dir() else []:
        test_md = candidate
        break
    if test_md is None:
        checks.append(Check("test-md", FAIL, "missing TEST.md test plan"))
    else:
        body = read(test_md)
        has_results = re.search(r"^#+\s*.*result", body, re.IGNORECASE | re.MULTILINE) is not None
        checks.append(Check(
            "test-md",
            PASS if has_results else WARN,
            "TEST.md records results" if has_results else "TEST.md has no results section",
            severity="warn",
        ))

    root_skill = repo_root / "skills" / ("cli-anything-%s" % slug) / "SKILL.md" if repo_root else None
    if root_skill is None:
        checks.append(Check("root-skill", WARN, "repo root not resolvable", severity="warn"))
    elif root_skill.is_file():
        checks.append(Check("root-skill", PASS, "root skill mirror present"))
    else:
        checks.append(Check(
            "root-skill",
            FAIL,
            "missing skills/cli-anything-%s/SKILL.md mirror" % slug,
        ))

    packaged = module / "skills" / "SKILL.md" if module else None
    checks.append(Check(
        "packaged-skill",
        PASS if packaged is not None and packaged.is_file() else FAIL,
        "packaged cli_anything/<module>/skills/SKILL.md present"
        if packaged is not None and packaged.is_file()
        else "missing packaged cli_anything/<module>/skills/SKILL.md",
    ))
    return checks


def parse_frontmatter(text):
    """Minimal YAML frontmatter reader for the two keys that matter here.

    Handles `key: value`, quoted values, and block scalars (`>-`, `|`, `|-`)
    whose continuation lines are indented. Avoids a PyYAML dependency so the
    checker runs anywhere the harness runs.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    lines = text[3:end].splitlines()
    values = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not match:
            index += 1
            continue
        key, raw = match.group(1), match.group(2).strip()
        index += 1
        if raw in (">", ">-", "|", "|-", ""):
            collected = []
            while index < len(lines) and (lines[index].startswith((" ", "\t")) or not lines[index].strip()):
                collected.append(lines[index].strip())
                index += 1
            values[key] = " ".join(part for part in collected if part)
        else:
            values[key] = raw.strip("\"'")
    return values


def check_skill_frontmatter(repo_root, slug):
    if repo_root is None:
        return []
    skill = repo_root / "skills" / ("cli-anything-%s" % slug) / "SKILL.md"
    if not skill.is_file():
        return []
    frontmatter = parse_frontmatter(read(skill))
    if "name" not in frontmatter or "description" not in frontmatter:
        return [Check("skill-frontmatter", FAIL, "root skill needs name and description frontmatter")]
    description = frontmatter["description"]
    detail = "name=%s, description=%d chars" % (frontmatter["name"], len(description))
    if description.endswith("..."):
        return [Check(
            "skill-frontmatter",
            WARN,
            detail + "; description is truncated mid-sentence, which weakens retrieval",
            severity="warn",
        )]
    return [Check("skill-frontmatter", PASS, detail)]


def verify(path, strict=False):
    harness = resolve_harness(path)
    software = harness.parent.name if harness.name == "agent-harness" else harness.name
    slug = slugify(software)
    repo_root = find_repo_root(harness)

    checks, module = check_layout(harness, software)
    checks += check_setup(harness, slug, module)
    checks += check_cli_surface(module, repo_root)
    checks += check_docs_and_tests(harness, software, slug, module, repo_root)
    checks += check_skill_frontmatter(repo_root, slug)

    errors = [c for c in checks if c.status == FAIL and c.severity == "error"]
    warnings = [c for c in checks if c.status in (FAIL, WARN) and c.severity == "warn"]
    ok = not errors and not (strict and warnings)
    return {
        "ok": ok,
        "name": software,
        "slug": slug,
        "path": str(harness),
        "checks": [c.as_dict() for c in checks],
        "summary": {"errors": len(errors), "warnings": len(warnings)},
    }


def discover(repo_root):
    found = []
    for harness in sorted(repo_root.glob("*/agent-harness")):
        if harness.is_dir():
            found.append(harness)
    return found


def print_human(result):
    status = "PASS" if result["ok"] else "FAIL"
    print("%s  %s  (%s)" % (status, result["name"], result["path"]))
    for check in result["checks"]:
        marker = {"pass": "  ok  ", "warn": " warn ", "fail": " fail "}[check["status"]]
        print("  %s %-22s %s" % (marker, check["id"], check["detail"]))
    summary = result["summary"]
    print("  %d error(s), %d warning(s)\n" % (summary["errors"], summary["warnings"]))


def print_summary(results):
    failed = [r for r in results if not r["ok"]]
    errors = sum(r["summary"]["errors"] for r in results)
    warnings = sum(r["summary"]["warnings"] for r in results)
    print("harnesses: %d  passing: %d  failing: %d  errors: %d  warnings: %d"
          % (len(results), len(results) - len(failed), len(failed), errors, warnings))
    for result in failed:
        reasons = [
            c["id"] for c in result["checks"]
            if c["status"] == "fail" and c["severity"] == "error"
        ]
        print("- %s: %s" % (result["name"], ", ".join(reasons)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify CLI-Anything harness contract compliance.")
    parser.add_argument("paths", nargs="*", help="software dir or agent-harness dir")
    parser.add_argument("--all", action="store_true", help="verify every harness in this checkout")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--summary", action="store_true", help="print one summary line plus failures")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args(argv)

    repo_root = find_repo_root(Path.cwd())
    paths = [Path(p) for p in args.paths]
    if args.all:
        if repo_root is None:
            print("--all requires running inside a CLI-Anything checkout", file=sys.stderr)
            return 2
        paths = discover(repo_root)
    if not paths:
        parser.print_help(sys.stderr)
        return 2

    results = [verify(p, strict=args.strict) for p in paths]
    if args.json:
        payload = {
            "ok": all(r["ok"] for r in results),
            "harnesses": results,
            "summary": {
                "harnesses": len(results),
                "failed": sum(0 if r["ok"] else 1 for r in results),
                "errors": sum(r["summary"]["errors"] for r in results),
                "warnings": sum(r["summary"]["warnings"] for r in results),
            },
        }
        print(json.dumps(payload, indent=2))
    elif args.summary:
        print_summary(results)
    else:
        for result in results:
            print_human(result)
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
