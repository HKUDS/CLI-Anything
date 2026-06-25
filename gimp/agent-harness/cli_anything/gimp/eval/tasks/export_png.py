"""Eval task: render a project to PNG via the GIMP harness (Pillow backend)."""

from cli_anything.gimp.core.project import create_project
from cli_anything.gimp.core.layers import add_layer
from cli_anything.gimp.core.export import render

TASK = {
    "id": "export_png",
    "name": "PNG export",
    "description": "Create a 1024x768 project with a solid layer and render to PNG",
    "prompt": "Create a 1024x768 image with a solid white background and export it to PNG.",
}


def precheck(ctx):
    try:
        import PIL  # noqa: F401
    except ImportError:
        return "Pillow not installed (pip install Pillow)"
    return None


def run(ctx):
    project = create_project(width=1024, height=768, name="eval")
    add_layer(project, name="white_bg", layer_type="solid", fill="#ffffff")
    out = ctx.task_artifact_path("out.png")
    result = render(project, str(out), preset="png", overwrite=True)
    return {"metrics": {"method": result.get("method"), "file_size": result.get("file_size")},
            "artifacts": [str(out)]}


def verify(ctx):
    out = ctx.task_artifact_path("out.png")
    size = out.stat().st_size if out.exists() else 0
    return {"ok": out.exists() and size > 0, "metrics": {"file_size": size}}
