"""Eval task: effects registry."""

from cli_anything.audacity.core.project import create_project
from cli_anything.audacity.core.tracks import add_track
from cli_anything.audacity.core.effects import EFFECT_REGISTRY, add_effect, list_effects


TASK = {
    "id": "effects_registry",
    "name": "Effects registry",
    "description": "Validate core effects and apply to track",
}


def run(ctx):
    _ = ctx.task_work_dir()

    project = create_project(
        name="Eval Effects",
        sample_rate=44100,
        bit_depth=16,
        channels=2,
    )
    add_track(project, name="Track 1")

    has_normalize = "normalize" in EFFECT_REGISTRY
    has_fade_in = "fade_in" in EFFECT_REGISTRY

    add_effect(project, "normalize", track_index=0, params={"target_db": -3.0})
    add_effect(project, "fade_in", track_index=0, params={"duration": 0.2})

    effects = list_effects(project, track_index=0)
    ok = has_normalize and has_fade_in and len(effects) == 2

    metrics = {
        "effects_count": len(effects),
        "has_normalize": has_normalize,
        "has_fade_in": has_fade_in,
    }

    return {
        "ok": ok,
        "metrics": metrics,
        "artifacts": [],
    }
