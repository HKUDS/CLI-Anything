"""Eval task: project roundtrip."""

from cli_anything.audacity.core.project import (
    create_project,
    get_project_info,
    open_project,
    save_project,
)


TASK = {
    "id": "project_roundtrip",
    "name": "Project roundtrip",
    "description": "Create -> save -> open -> info validation",
}


def run(ctx):
    work_dir = ctx.task_work_dir()
    project_path = work_dir / "project.json"

    project = create_project(
        name="Eval Project",
        sample_rate=44100,
        bit_depth=16,
        channels=2,
    )
    save_project(project, str(project_path))
    loaded = open_project(str(project_path))
    info = get_project_info(loaded)

    ok = (
        info.get("name") == "Eval Project"
        and info.get("settings", {}).get("sample_rate") == 44100
        and info.get("track_count") == 0
    )

    metrics = {
        "track_count": info.get("track_count"),
        "clip_count": info.get("clip_count"),
        "duration": info.get("duration"),
    }

    return {
        "ok": ok,
        "metrics": metrics,
        "artifacts": [],
    }
