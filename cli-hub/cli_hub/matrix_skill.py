"""Render local matrix skill files with resolved CLI skill paths.

Installed layout (one directory per matrix, so the skill's relative links to
``references/*.md`` and ``scripts/*.py`` resolve):

    ~/.cli-hub/matrix/<name>/SKILL.md
    ~/.cli-hub/matrix/<name>/references/...
    ~/.cli-hub/matrix/<name>/scripts/...

Skill content source lookup chain:

1. Repo checkout: ``<repo_root>/cli-hub-matrix/<name>/`` (via ``skill_md``).
2. Bundled package data: ``cli_hub/_matrix_data/<name>/`` (shipped in
   wheels/sdists built from a checkout; absent in editable installs, which
   hit the checkout in step 1 instead).
3. Published URL: ``https://hkuds.github.io/CLI-Anything/matrix/<name>/SKILL.md``
   (SKILL.md only; references/scripts stay remote and are linked from the
   rendered file).
4. Generated stub.
"""

import shutil
import subprocess
from importlib import metadata
from pathlib import Path

import requests

from cli_hub.registry import get_cli

MATRIX_SKILL_DIR = Path.home() / ".cli-hub" / "matrix"

# Base URL where deploy-pages.yml publishes cli-hub-matrix/ content (main only).
MATRIX_CONTENT_BASE_URL = "https://hkuds.github.io/CLI-Anything/matrix"

# Package data dir bundled into wheels/sdists by cli-hub/setup.py.
BUNDLED_MATRIX_DATA_DIR = Path(__file__).resolve().parent / "_matrix_data"

# Asset directories co-installed beside the rendered SKILL.md.
MATRIX_ASSET_SUBDIRS = ("references", "scripts")

_COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def _find_repo_root():
    """Find the repository root via git, falling back to parent traversal."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            root = Path(result.stdout.strip())
            if root.is_dir():
                return root
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: walk up from this file looking for .git
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent

    return None


def get_rendered_matrix_skill_path(name):
    """Return the local rendered SKILL.md path for a matrix.

    Prefers the per-matrix directory layout (``<name>/SKILL.md``); falls back
    to the legacy flat ``<name>.SKILL.md`` file when only that exists, so
    pre-existing installs keep resolving until the next re-render.
    """
    current = MATRIX_SKILL_DIR / name / "SKILL.md"
    legacy = MATRIX_SKILL_DIR / f"{name}.SKILL.md"
    if not current.exists() and legacy.exists():
        return legacy
    return current


def resolve_local_skill_path(cli):
    """Resolve an installed harness CLI's local SKILL.md path if possible."""
    if cli.get("_source", "harness") != "harness":
        return None

    dist_name = cli.get("dist_name") or f"cli-anything-{cli['name']}"
    try:
        dist = metadata.distribution(dist_name)
    except metadata.PackageNotFoundError:
        return _fallback_repo_skill_path(cli)

    for file in dist.files or []:
        file_str = str(file).replace("\\", "/")
        if file_str.endswith("/skills/SKILL.md") or file_str.endswith("skills/SKILL.md"):
            return str(dist.locate_file(file).resolve())

    return _fallback_repo_skill_path(cli)


def _fallback_repo_skill_path(cli):
    """Use the repo-relative skill path when available in the current checkout."""
    skill_ref = cli.get("skill_md")
    if not skill_ref or "://" in skill_ref or skill_ref.startswith("npx "):
        return None

    repo_root = _find_repo_root()
    if repo_root is None:
        return None
    candidate = repo_root / skill_ref
    if candidate.exists():
        return str(candidate.resolve())
    return None


def render_matrix_skill_file(matrix_item, installed=None):
    """Write a local matrix SKILL.md with resolved member skill paths.

    Renders into ``MATRIX_SKILL_DIR/<name>/SKILL.md`` and co-installs the
    matrix content directory's ``references/`` and ``scripts/`` beside it so
    the skill's relative links resolve. Re-rendering is idempotent: asset
    directories are replaced wholesale on each render.
    """
    name = matrix_item["name"]
    output_dir = MATRIX_SKILL_DIR / name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "SKILL.md"

    template_path, content_dir = _resolve_matrix_content_source(matrix_item)
    base_content = _load_matrix_skill_template(matrix_item, template_path).rstrip()
    copied = _copy_matrix_assets(content_dir, output_dir) if content_dir else []

    extra = ""
    if not copied:
        extra = (
            "\n\n## Reference Modules\n\n"
            "No local copy of this matrix's `references/` and `scripts/` was "
            "found; relative links above will not resolve locally. The "
            "published copies live under "
            f"{MATRIX_CONTENT_BASE_URL}/{name}/ (e.g. "
            f"{MATRIX_CONTENT_BASE_URL}/{name}/SKILL.md)."
        )

    injected_section = _render_injected_section(matrix_item, installed or {})
    output_path.write_text(
        f"{base_content}\n\n<!-- MATRIX_SKILL_PATHS:START -->\n\n{injected_section}{extra}\n\n<!-- MATRIX_SKILL_PATHS:END -->\n",
        encoding="utf-8",
    )
    return output_path


def _resolve_matrix_content_source(matrix_item):
    """Locate the matrix skill source as ``(template_path, content_dir)``.

    Tries the repo checkout first, then bundled package data. Either element
    may be ``None`` when nothing local is available (the template then falls
    back to the published URL or a stub).
    """
    skill_ref = matrix_item.get("skill_md")
    if skill_ref and "://" not in skill_ref and not skill_ref.startswith("npx "):
        repo_root = _find_repo_root()
        if repo_root is not None:
            candidate = repo_root / skill_ref
            if candidate.exists():
                return candidate, candidate.parent

    bundled = BUNDLED_MATRIX_DATA_DIR / matrix_item["name"] / "SKILL.md"
    if bundled.exists():
        return bundled, bundled.parent

    return None, None


def _copy_matrix_assets(content_dir, output_dir):
    """Copy references/ and scripts/ beside the rendered SKILL.md.

    Existing asset directories are removed first so re-installs are clean and
    stale files do not linger. ``__pycache__`` and ``*.pyc`` are excluded.
    Returns the list of subdirectories that were copied.
    """
    copied = []
    for subdir in MATRIX_ASSET_SUBDIRS:
        source = content_dir / subdir
        destination = output_dir / subdir
        if destination.exists():
            shutil.rmtree(destination)
        if source.is_dir():
            shutil.copytree(source, destination, ignore=_COPY_IGNORE)
            copied.append(subdir)
    return copied


def _load_matrix_skill_template(matrix_item, template_path=None):
    """Load the matrix skill template via the lookup chain.

    Order: local source file (checkout or bundled data) -> published URL ->
    generated stub.
    """
    if template_path is None:
        template_path, _ = _resolve_matrix_content_source(matrix_item)
    if template_path is not None:
        return template_path.read_text(encoding="utf-8")

    published = _fetch_published_matrix_skill(matrix_item["name"])
    if published is not None:
        return published

    title = matrix_item.get("display_name", matrix_item["name"])
    description = matrix_item.get("description", "")
    return (
        f"# {title}\n\n"
        f"{description}\n\n"
        f"Install with `cli-hub matrix install {matrix_item['name']}`.\n\n"
        f"Full skill content (when published): "
        f"{MATRIX_CONTENT_BASE_URL}/{matrix_item['name']}/SKILL.md"
    )


def _fetch_published_matrix_skill(name):
    """Fetch the published SKILL.md for a matrix, or None on any failure."""
    url = f"{MATRIX_CONTENT_BASE_URL}/{name}/SKILL.md"
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException:
        return None
    if resp.status_code != 200 or not resp.text.strip():
        return None
    return resp.text


def _render_injected_section(matrix_item, installed):
    """Render the injected skill reference section."""
    lines = [
        "## Installed CLI Skills",
        "",
        "Generated by `cli-hub matrix install` from the current local environment.",
        "",
        "| CLI | Entry Point | Canonical Skill | Local Skill | Status |",
        "|---|---|---|---|---|",
    ]

    for cli_name in matrix_item.get("clis", []):
        cli = get_cli(cli_name) or {"name": cli_name, "entry_point": cli_name}
        canonical_skill = cli.get("skill_md") or "—"
        local_skill = resolve_local_skill_path(cli) or "—"
        status = "installed" if cli_name in installed else "not installed"
        lines.append(
            f"| `{cli_name}` | `{cli.get('entry_point', '—')}` | "
            f"{canonical_skill} | {local_skill} | {status} |"
        )

    capability_tooling = _render_capability_tooling(matrix_item, installed)
    if capability_tooling:
        lines.append("")
        lines.append(capability_tooling)

    stage_tooling = _render_stage_tooling(matrix_item, installed)
    if stage_tooling:
        lines.append("")
        lines.append(stage_tooling)

    discovery = _render_discovery_section(matrix_item)
    if discovery:
        lines.append("")
        lines.append(discovery)

    return "\n".join(lines)


def _provider_installed(provider, installed):
    """Return whether a CLI provider appears installed by cli-hub name."""
    if provider.get("kind") not in {"harness-cli", "public-cli"}:
        return False
    name = provider.get("name", "")
    aliases = {name}
    if name.startswith("cli-anything-"):
        aliases.add(name.removeprefix("cli-anything-"))
    return any(alias in installed for alias in aliases)


def _format_requires(provider):
    requires = provider.get("requires") or {}
    parts = []
    for key in ("binary", "env", "package"):
        values = requires.get(key) or []
        if isinstance(values, str):
            values = [values]
        if values:
            parts.append(f"{key}: {', '.join(values)}")
    return "; ".join(parts) if parts else "none"


def _render_capability_tooling(matrix_item, installed):
    """Render v2 capability/provider guidance for local matrix skills."""
    capabilities = matrix_item.get("capabilities", [])
    if not capabilities:
        return ""

    lines = [
        "## Capability Provider Overview",
        "",
        "Pick providers per capability from task constraints and preflight facts. CLI providers show cli-hub install status; non-CLI providers list their preflight requirements.",
        "",
    ]

    for capability in capabilities:
        lines.append(f"### `{capability['id']}`")
        if capability.get("intent"):
            lines.append(capability["intent"])
        lines.append("")

        for provider in capability.get("providers", []):
            kind = provider.get("kind", "provider")
            quality = provider.get("quality_tier", "unknown")
            cost = provider.get("cost_tier", "unknown")
            offline = "offline" if provider.get("offline") else "online"
            status = ""
            if kind in {"harness-cli", "public-cli"}:
                status = "installed" if _provider_installed(provider, installed) else "not installed"
                status = f"; {status}"
            requires = _format_requires(provider)
            lines.append(
                f"- `{provider.get('name', '')}` ({kind}; {quality}; {cost}; {offline}{status})"
            )
            lines.append(f"  - Requires: {requires}")
            if provider.get("notes"):
                lines.append(f"  - Notes: {provider['notes']}")

        lines.append("")

    recipes = matrix_item.get("recipes", [])
    if recipes:
        lines.append("## Recipes")
        lines.append("")
        for recipe in recipes:
            capabilities_used = ", ".join(f"`{item}`" for item in recipe.get("capabilities_used", []))
            lines.append(f"- `{recipe['id']}`: {recipe.get('description', '')}")
            if capabilities_used:
                lines.append(f"  - Uses: {capabilities_used}")
        lines.append("")

    known_gaps = matrix_item.get("known_gaps", [])
    if known_gaps:
        lines.append("## Known Gaps")
        lines.append("")
        for gap in known_gaps:
            lines.append(f"- `{gap.get('capability', 'unknown')}`: {gap.get('reason', '')}")
            if gap.get("workaround"):
                lines.append(f"  - Workaround: {gap['workaround']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _render_stage_tooling(matrix_item, installed):
    """Render per-stage tooling overview with goals and alternatives."""
    stages = matrix_item.get("stages", [])
    has_goals = any(s.get("goal") for s in stages)
    if not has_goals:
        return ""

    lines = [
        "## Stage Tooling Overview",
        "",
        "What is available for each stage on this system.",
        "",
    ]

    for stage in stages:
        goal = stage.get("goal")
        if not goal:
            continue

        lines.append(f"### {stage['name']}")
        lines.append(f"**Goal:** {goal}")
        lines.append("")

        for cli_name in stage.get("clis", []):
            marker = "installed" if cli_name in installed else "not installed"
            lines.append(f"- CLI: `{cli_name}` ({marker})")

        alts = stage.get("alternatives", {})
        if alts.get("python"):
            lines.append(f"- Python: {', '.join(alts['python'])}")
        if alts.get("api"):
            lines.append(f"- APIs: {', '.join(alts['api'])}")
        if alts.get("native"):
            lines.append(f"- Native: {', '.join(alts['native'])}")

        lines.append("")

    return "\n".join(lines)


def _render_discovery_section(matrix_item):
    """Registry search hints are metadata; generated skills list concrete providers."""
    return ""
