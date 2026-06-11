"""Generate HTML preview of a Live2D model."""

from pathlib import Path
import json
import base64
from datetime import datetime

from cli_anything.live2d.core.parser import ModelInfo


def _texture_to_data_uri(tex_path: Path) -> str:
    """Convert a texture file to a base64 data URI for embedding."""
    if not tex_path.exists():
        return ""
    data = tex_path.read_bytes()
    b64 = base64.b64encode(data).decode()
    suffix = tex_path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(suffix.lstrip("."), "image/png")
    return f"data:{mime};base64,{b64}"


def generate_html(info: ModelInfo, embed_textures: bool = False) -> str:
    """Generate an HTML preview page for a Live2D model."""
    model_dir = info.path.parent
    textures = []
    for tex in info.textures:
        tex_path = model_dir / tex
        if embed_textures:
            src = _texture_to_data_uri(tex_path)
        else:
            src = str(tex_path.relative_to(model_dir)) if tex_path.exists() else ""
        textures.append({"path": tex, "src": src, "exists": tex_path.exists()})

    motions_html = ""
    for group, motions in info.motions.items():
        rows = ""
        for i, m in enumerate(motions):
            motion_path = model_dir / m.file
            exists = motion_path.exists()
            status = "✅" if exists else "❌"
            rows += f"<tr><td>{i}</td><td>{m.file}</td><td>{m.fade_in}s</td><td>{m.fade_out}s</td><td>{status}</td></tr>\n"
        motions_html += f"""
        <h3>[{group}] ({len(motions)} motions)</h3>
        <table>
            <tr><th>#</th><th>File</th><th>Fade In</th><th>Fade Out</th><th>Status</th></tr>
            {rows}
        </table>"""

    expr_html = ""
    if info.expressions:
        rows = ""
        for e in info.expressions:
            expr_path = model_dir / e.file
            exists = expr_path.exists()
            status = "✅" if exists else "❌"
            rows += f"<tr><td>{e.name}</td><td>{e.file}</td><td>{status}</td></tr>\n"
        expr_html = f"""
        <h3>Expressions ({len(info.expressions)})</h3>
        <table>
            <tr><th>Name</th><th>File</th><th>Status</th></tr>
            {rows}
        </table>"""

    tex_html = ""
    for t in textures:
        if t["exists"]:
            tex_html += f"""
            <div class="tex-card">
                <img src="{t['src']}" alt="{t['path']}" />
                <p>{t['path']}</p>
            </div>"""
        else:
            tex_html += f"""
            <div class="tex-card missing">
                <p>❌ {t['path']}</p>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Live2D Preview — {info.path.stem}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; padding: 24px; }}
    h1 {{ font-size: 24px; margin-bottom: 8px; color: #e94560; }}
    .meta {{ color: #888; margin-bottom: 24px; font-size: 14px; }}
    .stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
    .stat {{ background: #16213e; padding: 16px 24px; border-radius: 12px; text-align: center; min-width: 100px; }}
    .stat .num {{ font-size: 28px; font-weight: bold; color: #e94560; }}
    .stat .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
    h2 {{ font-size: 18px; margin: 24px 0 12px; color: #0f3460; }}
    h2 {{ color: #e94560; }}
    h3 {{ font-size: 14px; margin: 12px 0 8px; color: #aaa; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 13px; }}
    th {{ background: #16213e; padding: 8px 12px; text-align: left; font-weight: 600; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #2a2a4a; }}
    tr:hover {{ background: #16213e; }}
    .tex-grid {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .tex-card {{ background: #16213e; border-radius: 8px; padding: 12px; text-align: center; }}
    .tex-card img {{ max-width: 200px; max-height: 200px; border-radius: 4px; }}
    .tex-card p {{ font-size: 12px; color: #888; margin-top: 8px; word-break: break-all; }}
    .tex-card.missing {{ border: 1px dashed #e94560; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
    .badge.ok {{ background: #1b4332; color: #95d5b2; }}
    .badge.missing {{ background: #3d0000; color: #ff6b6b; }}
    footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #2a2a4a; color: #555; font-size: 12px; }}
</style>
</head>
<body>
    <h1>🎭 {info.path.stem}</h1>
    <div class="meta">
        {info.path.name} · Version {info.version or 'N/A'} · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </div>

    <div class="stats">
        <div class="stat"><div class="num">{info.texture_count}</div><div class="label">Textures</div></div>
        <div class="stat"><div class="num">{info.motion_count}</div><div class="label">Motions</div></div>
        <div class="stat"><div class="num">{info.expression_count}</div><div class="label">Expressions</div></div>
        <div class="stat"><div class="num">{info.motion_group_count}</div><div class="label">Groups</div></div>
    </div>

    <div class="meta">
        Moc3: <span class="badge {'ok' if info.moc3 else 'missing'}">{info.moc3 or 'none'}</span>
        Physics: <span class="badge {'ok' if info.physics else 'missing'}">{info.physics or 'none'}</span>
        Pose: <span class="badge {'ok' if info.pose else 'missing'}">{info.pose or 'none'}</span>
    </div>

    <h2>🖼️ Textures</h2>
    <div class="tex-grid">{tex_html}</div>

    <h2>🎬 Motions</h2>
    {motions_html}

    <h2>😊 Expressions</h2>
    {expr_html if expr_html else '<p style="color:#888">No expressions defined.</p>'}

    <footer>
        Generated by cli-anything-live2d · {info.path}
    </footer>
</body>
</html>"""
    return html


def write_snapshot(info: ModelInfo, out_path: Path, embed_textures: bool = False) -> Path:
    """Write HTML snapshot to file."""
    html = generate_html(info, embed_textures=embed_textures)
    out_path.write_text(html, encoding="utf-8")
    return out_path
