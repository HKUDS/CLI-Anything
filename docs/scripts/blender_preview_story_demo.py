#!/usr/bin/env python3
"""Render a polished Blender build-story video from a real preview demo run.

The source build run must already contain real preview bundles, a persisted live
session, and a `trajectory.json`. This script turns that trajectory into a
split-screen story video, then appends the real turntable ending from the
source run.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
FREECAD_DEMO_SCRIPT = Path(__file__).with_name("freecad_live_preview_demo.py")


def _load_style_module():
    spec = importlib.util.spec_from_file_location("freecad_live_preview_demo", FREECAD_DEMO_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


STYLE = _load_style_module()
VIDEO_W = STYLE.VIDEO_W
VIDEO_H = STYLE.VIDEO_H
LEFT_W = STYLE.LEFT_W
FPS = STYLE.FPS
COLORS = STYLE.COLORS
HOLD_TAIL_S = 1.4
BASELINE_START_S = 0.55
PREVIEW_SWITCH_LATENCY_S = 0.0
FINAL_STILL_STEP_S = 0.85
TURNTABLE_STEP_S = 0.7

DISPLAY_FONT_PATH = STYLE.DISPLAY_FONT_PATH
SANS_FONT_PATH = STYLE.SANS_FONT_PATH
MONO_FONT_PATH = STYLE.MONO_FONT_PATH
MONO_BOLD_FONT_PATH = STYLE.MONO_BOLD_FONT_PATH


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _stage_title(stage: Dict[str, Any]) -> str:
    stage_id = str(stage.get("stage") or "stage").strip()
    label = str(stage.get("label") or stage_id.replace("_", " ")).strip()
    prefix = stage_id.split("_", 1)[0]
    if prefix.isdigit():
        return f"Stage {prefix} · {label}"
    return label


def _stage_story(stage: Dict[str, Any]) -> str:
    return str(stage.get("story") or stage.get("label") or stage.get("stage") or "Build stage").strip()


def _stage_display_cmd(stage: Dict[str, Any]) -> str:
    return str(stage.get("display_cmd") or f"publish {stage.get('stage') or 'stage'}").strip()


def build_trajectory(build_manifest_path: Path, output_dir: Path) -> Dict[str, Any]:
    build_manifest = load_json(build_manifest_path)
    project_path = Path(build_manifest["project_path"]).expanduser().resolve()
    live_root = Path(build_manifest["preview_root"]).expanduser().resolve()
    final_render_path = Path(build_manifest["final_render"]["output"]).expanduser().resolve()
    turntable_path = Path(build_manifest["motion"]["video"]["video_path"]).expanduser().resolve()
    live_session = build_manifest.get("live_session") or {}
    stage_log = build_manifest.get("stage_log") or []
    if not stage_log:
        raise RuntimeError(f"No stage_log entries found in {build_manifest_path}")

    commands: List[Dict[str, Any]] = []
    t = 0.0

    def add_command(cmd_id: str, label: str, display_cmd: str, duration_s: float) -> Dict[str, Any]:
        nonlocal t
        command = {
            "index": len(commands),
            "id": cmd_id,
            "label": label,
            "display_cmd": display_cmd,
            "duration_s": float(duration_s),
            "timeline_start_s": round(t, 3),
            "timeline_end_s": round(t + float(duration_s), 3),
            "stdout": "",
            "stderr": "",
            "returncode": 0,
        }
        commands.append(command)
        t += float(duration_s)
        return command

    def bundle_payload(stage: Dict[str, Any]) -> Dict[str, Any]:
        bundle_dir = Path(stage["current_bundle_dir"]).expanduser().resolve()
        manifest_path = Path(stage["current_manifest_path"]).expanduser().resolve()
        summary_path = bundle_dir / "summary.json"
        manifest = load_json(manifest_path)
        summary = load_json(summary_path)
        artifacts = {
            item["artifact_id"]: str((bundle_dir / item["path"]).resolve())
            for item in manifest.get("artifacts", [])
        }
        return {
            "bundle_id": manifest["bundle_id"],
            "bundle_dir": str(bundle_dir),
            "manifest_path": str(manifest_path),
            "summary_path": str(summary_path),
            "artifacts": artifacts,
            "summary": summary,
        }

    baseline_command = add_command(
        "live-baseline",
        "Bring live preview online from the launch-platform baseline",
        str(
            live_session.get("start_command")
            or f"cli-anything-blender --project {project_path} preview live start --recipe quick --mode manual --root-dir {live_root}"
        ),
        BASELINE_START_S,
    )

    preview_events: List[Dict[str, Any]] = []
    baseline_stage = stage_log[0]
    preview_events.append(
        {
            "sequence_index": 1,
            "step_index": baseline_command["index"],
            "step_id": baseline_command["id"],
            "step_label": baseline_command["label"],
            "stage_id": baseline_stage["stage"],
            "stage_title": _stage_title(baseline_stage),
            "stage_story": _stage_story(baseline_stage),
            "timeline_ready_s": 0.0,
            "latency_s": 0.0,
            "bundle_count": int(baseline_stage.get("bundle_count") or 1),
            "publish_reason": f"stage:{baseline_stage['stage']}",
            "session_path": baseline_stage["session_path"],
            "session_dir": str(Path(baseline_stage["session_path"]).expanduser().resolve().parent),
            "copied_bundle": bundle_payload(baseline_stage),
        }
    )

    for sequence_index, stage in enumerate(stage_log[1:], start=2):
        command = add_command(
            f"stage-{stage['stage']}",
            str(stage.get("label") or stage["stage"]).strip(),
            _stage_display_cmd(stage),
            float(stage.get("duration_s") or 0.9),
        )
        ready_t = round(float(command["timeline_end_s"]) + PREVIEW_SWITCH_LATENCY_S, 3)
        preview_events.append(
            {
                "sequence_index": sequence_index,
                "step_index": command["index"],
                "step_id": command["id"],
                "step_label": command["label"],
                "stage_id": stage["stage"],
                "stage_title": _stage_title(stage),
                "stage_story": _stage_story(stage),
                "timeline_ready_s": ready_t,
                "latency_s": PREVIEW_SWITCH_LATENCY_S,
                "bundle_count": int(stage["bundle_count"]),
                "publish_reason": f"stage:{stage['stage']}",
                "session_path": stage["session_path"],
                "session_dir": str(Path(stage["session_path"]).expanduser().resolve().parent),
                "copied_bundle": bundle_payload(stage),
            }
        )

    add_command(
        "final-still",
        "Render final hero still",
        f"render_scene(..., output='{final_render_path}')",
        FINAL_STILL_STEP_S,
    )
    add_command(
        "turntable",
        "Package the real turntable ending",
        f"ffmpeg -> {turntable_path}",
        TURNTABLE_STEP_S,
    )

    trajectory = {
        "protocol": "blender-preview-trajectory/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "orbital-relay-drone",
        "scenario_title": "Orbital Relay Drone",
        "scenario_subtitle": "launch-platform baseline, step-aligned real preview checkpoints, then a real turntable ending",
        "build_manifest_path": str(build_manifest_path.resolve()),
        "project_path": str(project_path),
        "live_root": str(live_root),
        "final_render": str(final_render_path),
        "turntable_video": str(turntable_path),
        "commands": commands,
        "preview_events": preview_events,
        "notes": [
            "The first preview shown on the right is the real stage-00 launch-platform bundle, used as a live baseline instead of leaving the monitor empty.",
            "Every later preview switch is keyed from the matching real stage_log entry, so command completion and preview refresh stay aligned.",
            "The ending appends the existing real turntable video from the same run.",
        ],
    }
    write_json(output_dir / "trajectory.json", trajectory)
    return trajectory


def _fonts() -> Dict[str, ImageFont.FreeTypeFont]:
    return {
        "display": STYLE.load_font(DISPLAY_FONT_PATH, 38),
        "title": STYLE.load_font(DISPLAY_FONT_PATH, 24),
        "body": STYLE.load_font(SANS_FONT_PATH, 17),
        "small": STYLE.load_font(SANS_FONT_PATH, 13),
        "mono": STYLE.load_font(MONO_FONT_PATH, 15),
        "mono_small": STYLE.load_font(MONO_BOLD_FONT_PATH, 12),
    }


def _draw_text_right(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, *, font: ImageFont.FreeTypeFont, fill: str) -> None:
    STYLE._draw_text_right(draw, x, y, text, font=font, fill=fill)


def progress_snapshot(trajectory: Dict[str, Any], t_real: float) -> Dict[str, Any]:
    return STYLE.progress_snapshot(trajectory, t_real)


def pick_preview_event(trajectory: Dict[str, Any], t_real: float) -> Optional[Dict[str, Any]]:
    return STYLE.pick_preview_event(trajectory, t_real)


def build_command_cards(trajectory: Dict[str, Any], t_real: float, *, max_cards: int = 6) -> List[Dict[str, Any]]:
    return STYLE.build_command_cards(trajectory, t_real, max_cards=max_cards)


def draw_global_header(
    canvas: Image.Image,
    trajectory: Dict[str, Any],
    t_real: float,
    fonts: Dict[str, ImageFont.FreeTypeFont],
) -> None:
    draw = ImageDraw.Draw(canvas)
    snapshot = progress_snapshot(trajectory, t_real)
    title = trajectory.get("scenario_title", "Blender Live Demo").upper()
    subtitle = trajectory.get("scenario_subtitle", "scripted build trace + real preview bundles")

    draw.text((34, 20), "CLI-ANYTHING / BLENDER / LIVE PREVIEW PROTOCOL", fill="#88a9c8", font=fonts["small"])
    draw.text((34, 36), title, fill=COLORS["white"], font=fonts["display"])
    draw.text((34, 68), subtitle, fill="#97abc2", font=fonts["body"])

    chip_y = 20
    chips = [
        f"T+ {t_real:05.1f}s",
        f"{snapshot['completed_cmds']:02d}/{snapshot['total_cmds']:02d} steps",
        f"{snapshot['completed_previews']:02d}/{snapshot['total_previews']:02d} bundles",
    ]
    x = VIDEO_W - 34
    for text in reversed(chips):
        bbox = draw.textbbox((0, 0), text, font=fonts["mono_small"])
        chip_w = (bbox[2] - bbox[0]) + 26
        STYLE._draw_chip(
            canvas,
            (x - chip_w, chip_y, x, chip_y + 26),
            text=text,
            font=fonts["mono_small"],
            fill=COLORS["chip_bg"],
            text_fill=COLORS["chip_text"],
            outline=COLORS["panel_line"],
        )
        x -= chip_w + 10

    draw.line((30, 98, VIDEO_W - 30, 98), fill=STYLE._rgba(COLORS["grid"], 120), width=1)


def draw_trace_panel(
    canvas: Image.Image,
    area: tuple[int, int, int, int],
    trajectory: Dict[str, Any],
    t_real: float,
    fonts: Dict[str, ImageFont.FreeTypeFont],
) -> None:
    x0, y0, x1, y1 = area
    draw = ImageDraw.Draw(canvas)
    snapshot = progress_snapshot(trajectory, t_real)
    STYLE._draw_panel(canvas, area, radius=30, fill=COLORS["panel"], outline=COLORS["panel_line"], accent=COLORS["accent"])

    draw.text((x0 + 24, y0 + 24), "Agent Build Trace", fill=COLORS["white"], font=fonts["title"])
    STYLE._draw_chip(
        canvas,
        (x1 - 178, y0 + 24, x1 - 24, y0 + 50),
        text="REAL SCRIPT TRACE",
        font=fonts["mono_small"],
        fill=COLORS["accent_soft"],
        text_fill=COLORS["accent"],
        outline=COLORS["accent"],
    )

    active_label = snapshot["active_cmd"]["label"] if snapshot["active_cmd"] else (
        snapshot["current_event"]["step_label"] if snapshot["current_event"] else "waiting for first build step"
    )
    draw.text((x0 + 24, y0 + 58), STYLE._trim_middle(active_label, 46), fill="#9bb4ce", font=fonts["body"])
    STYLE._draw_segment_bar(
        canvas,
        (x0 + 24, y0 + 90, x1 - 24, y0 + 101),
        done=snapshot["completed_cmds"],
        total=max(1, snapshot["total_cmds"]),
        fill=COLORS["accent"],
        empty=COLORS["panel_line"],
    )

    chip_y = y0 + 116
    chip_specs = [
        (f"step {snapshot['completed_cmds']:02d}/{snapshot['total_cmds']:02d}", COLORS["chip_bg"], COLORS["chip_text"]),
        (f"preview {snapshot['completed_previews']:02d}/{snapshot['total_previews']:02d}", COLORS["chip_bg"], COLORS["chip_text"]),
        ("manual live preview", COLORS["accent_soft"], COLORS["accent"]),
    ]
    chip_x = x0 + 24
    for text, fill, text_fill in chip_specs:
        bbox = draw.textbbox((0, 0), text, font=fonts["mono_small"])
        chip_w = (bbox[2] - bbox[0]) + 24
        STYLE._draw_chip(
            canvas,
            (chip_x, chip_y, chip_x + chip_w, chip_y + 24),
            text=text,
            font=fonts["mono_small"],
            fill=fill,
            text_fill=text_fill,
            outline=COLORS["panel_line"],
        )
        chip_x += chip_w + 10

    body_area = (x0 + 16, y0 + 154, x1 - 16, y1 - 44)
    STYLE._alpha_box(canvas, body_area, radius=22, fill=STYLE._rgba(COLORS["terminal_bg"], 246), outline=STYLE._rgba(COLORS["panel_line"], 255), width=1)

    draw.text((body_area[0] + 18, body_area[1] + 16), "Recent steps", fill=COLORS["white"], font=fonts["body"])
    draw.text((body_area[2] - 166, body_area[1] + 16), "scripted build flow", fill=COLORS["terminal_muted"], font=fonts["small"])

    cards = build_command_cards(trajectory, t_real, max_cards=6)
    card_gap = 10
    card_height = 82
    card_x0 = body_area[0] + 14
    card_x1 = body_area[2] - 14
    card_y = body_area[1] + 48
    for card in cards:
        status = card["status"]
        if status == "live":
            fill = "#0d2630"
            outline = COLORS["accent"]
            status_fill = COLORS["accent_soft"]
            status_text = COLORS["accent"]
            label_fill = COLORS["white"]
        elif status == "done":
            fill = "#0e1826"
            outline = COLORS["panel_line"]
            status_fill = "#123648"
            status_text = "#9ddfff"
            label_fill = "#dbe6f3"
        else:
            fill = "#0a111a"
            outline = "#173049"
            status_fill = "#111f30"
            status_text = "#6f87a2"
            label_fill = "#9bb0c7"

        box = (card_x0, card_y, card_x1, card_y + card_height)
        STYLE._alpha_box(canvas, box, radius=18, fill=STYLE._rgba(fill, 248), outline=STYLE._rgba(outline, 255), width=2 if status == "live" else 1)
        STYLE._alpha_box(canvas, (box[0] + 10, box[1] + 10, box[0] + 14, box[3] - 10), radius=2, fill=STYLE._rgba(outline, 255))
        if status == "live":
            STYLE._draw_soft_glow(canvas, center=(box[2] - 34, box[1] + 24), radius=26, color=COLORS["accent"], strength=34)

        STYLE._draw_chip(
            canvas,
            (box[0] + 22, box[1] + 12, box[0] + 74, box[1] + 34),
            text=f"{card['index'] + 1:02d}",
            font=fonts["mono_small"],
            fill=COLORS["chip_bg"],
            text_fill=COLORS["chip_text"],
            outline=COLORS["panel_line"],
        )
        STYLE._draw_chip(
            canvas,
            (box[2] - 114, box[1] + 12, box[2] - 18, box[1] + 34),
            text=status.upper(),
            font=fonts["mono_small"],
            fill=status_fill,
            text_fill=status_text,
            outline=outline,
        )
        draw.text((box[0] + 84, box[1] + 10), STYLE._trim_middle(card["label"], 38), fill=label_fill, font=fonts["body"])
        draw.text((box[2] - 182, box[3] - 26), f"{card['duration_s']:.2f}s", fill=COLORS["terminal_muted"], font=fonts["mono_small"])

        command_lines = STYLE._wrap_trimmed(STYLE._readable_command_text(card["command"]), width_chars=54, max_lines=2)
        cmd_y = box[1] + 38
        for line in command_lines:
            draw.text((box[0] + 22, cmd_y), line, fill=COLORS["terminal_cmd"] if status != "queued" else "#6e8aa6", font=fonts["mono_small"])
            cmd_y += 17

        card_y += card_height + card_gap

    footer = "Step-aligned build trace driven by the real Blender stage_log; preview captures remain real artifacts."
    draw.text((x0 + 24, y1 - 28), footer, fill=COLORS["terminal_muted"], font=fonts["small"])


def _paste_preview_card(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    *,
    img_path: Optional[str],
    label: str,
    fonts: Dict[str, ImageFont.FreeTypeFont],
    main: bool = False,
) -> None:
    x0, y0, x1, y1 = box
    STYLE._alpha_box(canvas, box, radius=18 if main else 14, fill=STYLE._rgba(COLORS["paper"], 255), outline=STYLE._rgba(COLORS["paper_line"], 255), width=2)
    if img_path and Path(img_path).is_file():
        fit = STYLE.fit_image(Image.open(img_path), (max(1, x1 - x0 - 18), max(1, y1 - y0 - 18)), background=COLORS["paper"])
        canvas.paste(fit.convert("RGBA"), (x0 + 9, y0 + 9))
    STYLE._draw_chip(
        canvas,
        (x0 + 12, y0 + 12, x0 + 112, y0 + 36),
        text=label,
        font=fonts["mono_small"],
        fill="#fffaf3",
        text_fill="#5b5145",
        outline=COLORS["paper_line"],
    )
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.line((x0 + 10, y0 + 10, x0 + 30, y0 + 10), fill=STYLE._rgba(COLORS["accent_warm"], 160), width=2)
    draw.line((x0 + 10, y0 + 10, x0 + 10, y0 + 30), fill=STYLE._rgba(COLORS["accent_warm"], 160), width=2)
    draw.line((x1 - 10, y1 - 10, x1 - 30, y1 - 10), fill=STYLE._rgba(COLORS["accent"], 160), width=2)
    draw.line((x1 - 10, y1 - 10, x1 - 10, y1 - 30), fill=STYLE._rgba(COLORS["accent"], 160), width=2)
    canvas.alpha_composite(overlay)


def draw_preview_panel(
    canvas: Image.Image,
    area: tuple[int, int, int, int],
    trajectory: Dict[str, Any],
    t_real: float,
    fonts: Dict[str, ImageFont.FreeTypeFont],
    image_cache: Dict[str, Image.Image],
) -> None:
    x0, y0, x1, y1 = area
    draw = ImageDraw.Draw(canvas)
    snapshot = progress_snapshot(trajectory, t_real)
    STYLE._draw_panel(canvas, area, radius=30, fill=COLORS["panel"], outline=COLORS["panel_line"], accent=COLORS["accent_warm"])
    draw.text((x0 + 24, y0 + 24), "Preview Monitor", fill=COLORS["white"], font=fonts["title"])
    STYLE._draw_chip(
        canvas,
        (x1 - 152, y0 + 24, x1 - 24, y0 + 50),
        text="LIVE BUNDLES",
        font=fonts["mono_small"],
        fill="#351d17",
        text_fill=COLORS["accent_warm"],
        outline=COLORS["accent_warm"],
    )
    draw.text((x0 + 24, y0 + 58), "Real Blender quick-preview bundles from the active build run", fill=COLORS["preview_muted"], font=fonts["body"])

    event = pick_preview_event(trajectory, t_real)
    if event is None:
        draw.text((x0 + 28, y0 + 96), "Waiting for first Blender preview bundle...", fill=COLORS["preview_muted"], font=fonts["body"])
        return

    current = event["copied_bundle"]
    summary = current.get("summary") or {}
    facts = summary.get("facts") or {}
    previous_event = None
    if event["sequence_index"] > 1:
        previous_event = trajectory["preview_events"][event["sequence_index"] - 2]

    stage_area = (x0 + 20, y0 + 96, x1 - 260, y1 - 20)
    info_area = (x1 - 244, y0 + 96, x1 - 20, y1 - 20)
    STYLE._alpha_box(canvas, info_area, radius=20, fill=STYLE._rgba(COLORS["panel_soft"], 252), outline=STYLE._rgba(COLORS["panel_line"], 255), width=1)

    main_box = (stage_area[0], stage_area[1], stage_area[2], int(stage_area[1] + (stage_area[3] - stage_area[1]) * 0.73))
    _paste_preview_card(canvas, main_box, img_path=current["artifacts"].get("hero"), label="HERO", fonts=fonts, main=True)

    thumb_y = main_box[3] + 10
    thumb_h = stage_area[3] - thumb_y
    thumb_w = (stage_area[2] - stage_area[0] - 12) // 2
    _paste_preview_card(
        canvas,
        (stage_area[0], thumb_y, stage_area[0] + thumb_w, thumb_y + thumb_h),
        img_path=current["artifacts"].get("workbench"),
        label="WORKBENCH",
        fonts=fonts,
    )
    secondary_label = "FINAL STILL"
    secondary_img = trajectory.get("final_render")
    if previous_event is not None:
        secondary_label = "PREV HERO"
        secondary_img = previous_event["copied_bundle"]["artifacts"].get("hero")
    _paste_preview_card(
        canvas,
        (stage_area[0] + thumb_w + 12, thumb_y, stage_area[2], thumb_y + thumb_h),
        img_path=secondary_img,
        label=secondary_label,
        fonts=fonts,
    )

    draw.text((info_area[0] + 16, info_area[1] + 16), "Telemetry", fill=COLORS["white"], font=fonts["body"])
    meta_lines = [
        ("STAGE", event["stage_title"]),
        ("BUNDLE", STYLE._trim_middle(current["bundle_id"], 18)),
        ("CAUSE", STYLE._trim_middle(str(event.get("publish_reason") or "n/a"), 18)),
        ("LATENCY", f"{event.get('latency_s', 0.0):.2f}s"),
        ("FRAME", str(facts.get("frame_current", "n/a"))),
        ("STREAM", f"{event['sequence_index']:02d}/{len(trajectory['preview_events']):02d}"),
    ]
    meta_y = info_area[1] + 46
    for label, value in meta_lines:
        STYLE._draw_chip(
            canvas,
            (info_area[0] + 16, meta_y, info_area[2] - 16, meta_y + 28),
            text=label,
            font=fonts["mono_small"],
            fill=COLORS["chip_bg"],
            text_fill=COLORS["chip_text"],
            outline=COLORS["panel_line"],
        )
        draw.text((info_area[0] + 18, meta_y + 36), STYLE._trim_middle(str(value), 26), fill=COLORS["white"], font=fonts["body"])
        meta_y += 74

    story_lines = STYLE._wrap_trimmed(event["stage_story"], width_chars=24, max_lines=5)
    note_title = "Stage note"
    if snapshot["active_cmd"] and snapshot["active_cmd"]["id"] in {"final-still", "turntable"}:
        note_title = "Handoff note"
    draw.text((info_area[0] + 16, info_area[3] - 176), note_title, fill=COLORS["white"], font=fonts["body"])
    story_y = info_area[3] - 148
    for line in story_lines:
        draw.text((info_area[0] + 16, story_y), line, fill=COLORS["preview_muted"], font=fonts["small"])
        story_y += 18

    STYLE._draw_segment_bar(
        canvas,
        (info_area[0] + 16, info_area[3] - 32, info_area[2] - 16, info_area[3] - 18),
        done=max(1, event["sequence_index"]),
        total=max(1, len(trajectory["preview_events"])),
        fill=COLORS["accent_warm"],
        empty=COLORS["panel_line"],
    )


def render_process_video(
    trajectory: Dict[str, Any],
    *,
    output_dir: Path,
    fps: int,
    keep_frames: bool,
) -> Dict[str, Any]:
    frames_dir = STYLE.ensure_clean_dir(output_dir / "process-frames")
    stills_dir = STYLE.ensure_clean_dir(output_dir / "stills")
    process_video_path = output_dir / "process.mp4"

    fonts = _fonts()
    backdrop = STYLE.build_static_backdrop()
    image_cache: Dict[str, Image.Image] = {}

    last_t = max(cmd["timeline_end_s"] for cmd in trajectory["commands"])
    duration_s = last_t + HOLD_TAIL_S
    frame_count = int(math.ceil(duration_s * fps))

    early_idx = max(0, min(frame_count - 1, fps * 2))
    mid_idx = max(0, min(frame_count - 1, frame_count // 2))
    late_idx = max(0, frame_count - fps)
    still_targets = {
        early_idx: stills_dir / "early-command-stream.png",
        mid_idx: stills_dir / "mid-preview-monitor.png",
        late_idx: stills_dir / "late-build-state.png",
    }

    for frame_idx in range(frame_count):
        t_real = frame_idx / fps
        image = backdrop.copy()
        draw_global_header(image, trajectory, t_real, fonts)
        draw_trace_panel(image, (26, 116, LEFT_W - 14, VIDEO_H - 34), trajectory, t_real, fonts)
        draw_preview_panel(image, (LEFT_W + 10, 116, VIDEO_W - 26, VIDEO_H - 34), trajectory, t_real, fonts, image_cache)

        draw = ImageDraw.Draw(image)
        footer_left = "STEP-ALIGNED build trace · REAL Blender preview bundles · real turntable ending appended"
        footer_right = STYLE._trim_middle(str(output_dir / "trajectory.json"), 64)
        draw.text((34, VIDEO_H - 26), footer_left, fill="#7891ab", font=fonts["small"])
        _draw_text_right(draw, VIDEO_W - 34, VIDEO_H - 26, footer_right, font=fonts["mono_small"], fill="#7891ab")

        frame_path = frames_dir / f"frame_{frame_idx:05d}.png"
        rgb = image.convert("RGB")
        rgb.save(frame_path)
        target = still_targets.get(frame_idx)
        if target is not None:
            rgb.save(target)

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    process_cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%05d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(process_video_path),
    ]
    subprocess.run(process_cmd, cwd=output_dir, capture_output=True, text=True, timeout=600, check=True)

    if not keep_frames:
        shutil.rmtree(frames_dir)

    return {
        "process_video": str(process_video_path),
        "frames_dir": str(frames_dir) if keep_frames else None,
        "duration_s": duration_s,
        "frame_count": frame_count,
        "stills": {key.stem: str(key) for key in sorted(stills_dir.glob("*.png"))},
    }


def transform_turntable(turntable_video: Path, output_dir: Path, fps: int) -> Path:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    transformed = output_dir / "turntable-ending.mp4"
    vf = (
        f"fps={fps},"
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color=0x030b16"
    )
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(turntable_video),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(transformed),
    ]
    subprocess.run(cmd, cwd=output_dir, capture_output=True, text=True, timeout=600, check=True)
    return transformed


def concat_videos(process_video: Path, turntable_video: Path, output_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    concat_list = output_path.parent / "concat.txt"
    concat_list.write_text(
        f"file '{process_video.as_posix()}'\nfile '{turntable_video.as_posix()}'\n",
        encoding="utf-8",
    )
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(cmd, cwd=output_path.parent, capture_output=True, text=True, timeout=600, check=True)


def render_story(build_manifest_path: Path, output_dir: Path, *, fps: int = FPS, keep_frames: bool = True) -> Dict[str, Any]:
    build_manifest = load_json(build_manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = build_trajectory(build_manifest_path, output_dir)
    process_payload = render_process_video(trajectory, output_dir=output_dir, fps=fps, keep_frames=keep_frames)
    turntable_src = Path(trajectory["turntable_video"]).expanduser().resolve()
    transformed_turntable = transform_turntable(turntable_src, output_dir, fps)
    final_video = output_dir / "demo-polished.mp4"
    concat_videos(Path(process_payload["process_video"]), transformed_turntable, final_video)

    showcase_turntable = Path(build_manifest["motion"]["stills"]["mid"]).expanduser().resolve()
    showcase_turntable_copy = output_dir / "stills" / "showcase-turntable.png"
    shutil.copy2(showcase_turntable, showcase_turntable_copy)
    process_payload["stills"]["showcase-turntable"] = str(showcase_turntable_copy)

    manifest = {
        "protocol": "blender-preview-story/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "build_manifest_path": str(build_manifest_path.resolve()),
        "trajectory_path": str((output_dir / "trajectory.json").resolve()),
        "process": process_payload,
        "turntable_source": str(turntable_src),
        "turntable_transformed": str(transformed_turntable),
        "final_video": str(final_video),
        "notes": [
            "The process section is a programmatic composition of a scripted agent build trace and real Blender preview bundles.",
            "The ending is the existing real turntable video from the same Blender run, transformed only for resolution consistency before concatenation.",
        ],
    }
    write_json(output_dir / "story_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-manifest",
        default=f"/root/preview-artifacts/{today}/blender-orbital-relay-drone-v6/build_manifest.json",
        help="Existing Blender build_manifest.json path from the orbital relay drone demo.",
    )
    parser.add_argument(
        "--output-dir",
        default=f"/root/preview-artifacts/{today}/blender-orbital-relay-drone-story-v5",
        help="Directory for trajectory.json, process frames, stills, and the final polished video assembled from real preview bundles.",
    )
    parser.add_argument("--fps", type=int, default=FPS, help="Output video FPS.")
    parser.add_argument(
        "--discard-frames",
        action="store_true",
        help="Delete intermediate composed process frames after MP4 encoding.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = render_story(
        Path(args.build_manifest).expanduser().resolve(),
        Path(args.output_dir).expanduser().resolve(),
        fps=int(args.fps),
        keep_frames=not args.discard_frames,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
