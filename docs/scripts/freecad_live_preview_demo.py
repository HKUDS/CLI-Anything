#!/usr/bin/env python3
"""Collect and render a real FreeCAD live-preview demo video.

This script has two phases:

1. ``collect`` runs a real CLI trajectory against ``cli-anything-freecad``,
   starts poll-mode live preview, waits for real preview bundles to update,
   and saves a structured timeline plus copied preview snapshots.
2. ``render`` turns that real timeline into an editable split-screen MP4:
   terminal trajectory on the left, preview window on the right.

The composition is programmatic, but the commands, outputs, timing, and preview
artifacts are all captured from real execution.

The collected run persists:

- `session.json`
- `trajectory.json`
- copied preview bundle snapshots
- optional `live.html` rendered from the live session

Use `cli-hub previews inspect|html|watch|open` on the resulting session or
bundle paths when you want a generic viewer outside the final composed video.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]
FREECAD_WORKDIR = REPO_ROOT / "freecad" / "agent-harness"
CLI_HUB_WORKDIR = REPO_ROOT / "cli-hub"
FREECAD_CLI = shutil.which("cli-anything-freecad") or "cli-anything-freecad"
CLI_HUB = shutil.which("cli-hub") or "cli-hub"
MONO_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_BOLD_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DISPLAY_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"

VIDEO_W = 1600
VIDEO_H = 900
LEFT_W = 650
RIGHT_W = VIDEO_W - LEFT_W
FPS = 12
HOLD_TAIL_S = 2.5
DEFAULT_WAIT_TIMEOUT_S = 90.0
SHOWCASE_FRAME_COUNT = 12
SHOWCASE_DURATION_S = 7.0
SHOWCASE_HOLD_S = 1.1
TRUE_MOTION_DURATION_S = 6.0
TRUE_MOTION_KEYFRAME_COUNT = 13
SPIN_MOTION_DURATION_S = 7.0
SPIN_MOTION_KEYFRAME_COUNT = 19
COMBO_MOTION_DURATION_S = 9.0
COMBO_MOTION_KEYFRAME_COUNT = 25

COLORS = {
    "bg_top": "#030b16",
    "bg_bottom": "#081a2d",
    "grid": "#14314d",
    "grid_soft": "#0d2338",
    "panel": "#0b1522",
    "panel_soft": "#101d2f",
    "panel_line": "#224667",
    "panel_glow": "#2de2c5",
    "terminal_bg": "#07111b",
    "terminal_text": "#d9e7f5",
    "terminal_muted": "#6d839c",
    "terminal_success": "#8bf0c8",
    "terminal_error": "#ff8f98",
    "terminal_cmd": "#7ed6ff",
    "terminal_json": "#f7d488",
    "preview_shell": "#0b1220",
    "preview_stage": "#efe7da",
    "preview_stage_edge": "#cabca8",
    "preview_text": "#f2f5f8",
    "preview_muted": "#9fb2c8",
    "chip_bg": "#11263a",
    "chip_text": "#dfeaf5",
    "accent": "#23d7bb",
    "accent_warm": "#ff8a57",
    "accent_soft": "#173f40",
    "paper": "#f7f2ea",
    "paper_line": "#d2c6b5",
    "white": "#ffffff",
}


def _taipei_101_steps() -> List[Dict[str, Any]]:
    """Return a more legible tiny Taipei 101 build trajectory."""
    steps: List[Dict[str, Any]] = [
        {
            "id": "create-project",
            "label": "Create FreeCAD project",
            "argv": ["document", "new", "--name", "Taipei101", "-o", "{project_path}"],
            "wait_preview": False,
        },
        {
            "id": "start-live-preview",
            "label": "Start poll-mode live preview",
            "argv": [
                "-p",
                "{project_path}",
                "preview",
                "live",
                "start",
                "--recipe",
                "quick",
                "--mode",
                "poll",
                "--source-poll-ms",
                "500",
                "--poll-ms",
                "700",
                "--root-dir",
                "{live_root}",
            ],
            "wait_preview": True,
            "manual_session_payload": True,
        },
        {
            "id": "podium",
            "label": "Add podium",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "Podium",
                "-P",
                "length=58",
                "-P",
                "width=46",
                "-P",
                "height=16",
                "-pos",
                "-29,-23,0",
            ],
            "wait_preview": True,
        },
    ]

    z = 16.0
    for index in range(8):
        module_no = index + 1
        core_len = 24.0 - index * 1.3
        core_w = 15.0 - index * 0.5
        core_h = 8.4
        arm_w = max(5.0, core_w - 7.0)
        arm_h = 1.8
        arm_lo_len = core_len + 8.0
        arm_hi_len = core_len + 12.0

        steps.append(
            {
                "id": f"module-{module_no}",
                "label": f"Add tower module {module_no}",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    f"Core{module_no}",
                    "-P",
                    f"length={core_len:.2f}",
                    "-P",
                    f"width={core_w:.2f}",
                    "-P",
                    f"height={core_h:.2f}",
                    "-pos",
                    f"{-core_len / 2:.2f},{-core_w / 2:.2f},{z:.2f}",
                ],
                "wait_preview": True,
            }
        )
        steps.append(
            {
                "id": f"arm-low-{module_no}",
                "label": f"Add lower shoulder {module_no}",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    f"ArmLo{module_no}",
                    "-P",
                    f"length={arm_lo_len:.2f}",
                    "-P",
                    f"width={arm_w:.2f}",
                    "-P",
                    f"height={arm_h:.2f}",
                    "-pos",
                    f"{-arm_lo_len / 2:.2f},{-arm_w / 2:.2f},{z + 2.0:.2f}",
                ],
                "wait_preview": True,
            }
        )
        steps.append(
            {
                "id": f"arm-high-{module_no}",
                "label": f"Add upper shoulder {module_no}",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    f"ArmHi{module_no}",
                    "-P",
                    f"length={arm_hi_len:.2f}",
                    "-P",
                    f"width={arm_w:.2f}",
                    "-P",
                    f"height={arm_h:.2f}",
                    "-pos",
                    f"{-arm_hi_len / 2:.2f},{-arm_w / 2:.2f},{z + 5.1:.2f}",
                ],
                "wait_preview": True,
            }
        )
        z += core_h

    steps.extend(
        [
            {
                "id": "crown",
                "label": "Add crown block",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "Crown",
                    "-P",
                    "length=9",
                    "-P",
                    "width=9",
                    "-P",
                    "height=8",
                    "-pos",
                    f"-4.5,-4.5,{z:.2f}",
                ],
                "wait_preview": True,
            },
            {
                "id": "spire-lower",
                "label": "Add lower spire",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cylinder",
                    "--name",
                    "SpireLower",
                    "-P",
                    "radius=1.8",
                    "-P",
                    "height=14",
                    "-pos",
                    f"0,0,{z + 8.0:.2f}",
                ],
                "wait_preview": True,
            },
            {
                "id": "spire-upper",
                "label": "Add upper spire",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cylinder",
                    "--name",
                    "SpireUpper",
                    "-P",
                    "radius=1.0",
                    "-P",
                    "height=12",
                    "-pos",
                    f"0,0,{z + 22.0:.2f}",
                ],
                "wait_preview": True,
            },
            {
                "id": "spire-tip",
                "label": "Add spire tip",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cone",
                    "--name",
                    "SpireTip",
                    "-P",
                    "radius1=1.5",
                    "-P",
                    "radius2=0.18",
                    "-P",
                    "height=11",
                    "-pos",
                    f"0,0,{z + 34.0:.2f}",
                ],
                "wait_preview": True,
            },
        ]
    )
    return steps


def _mars_rover_steps() -> List[Dict[str, Any]]:
    """Return a modular Mars rover build trajectory tuned for live preview."""
    return [
        {
            "id": "create-project",
            "label": "Create FreeCAD project",
            "argv": ["document", "new", "--name", "MarsRover", "-o", "{project_path}"],
            "wait_preview": False,
        },
        {
            "id": "start-live-preview",
            "label": "Start poll-mode live preview",
            "argv": [
                "-p",
                "{project_path}",
                "preview",
                "live",
                "start",
                "--recipe",
                "quick",
                "--mode",
                "poll",
                "--source-poll-ms",
                "500",
                "--poll-ms",
                "700",
                "--root-dir",
                "{live_root}",
            ],
            "wait_preview": True,
            "manual_session_payload": True,
        },
        {
            "id": "chassis-belly",
            "label": "Add chassis belly",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "ChassisBelly",
                "-P",
                "length=72",
                "-P",
                "width=28",
                "-P",
                "height=6",
                "-pos",
                "-36,-14,24",
            ],
            "wait_preview": True,
        },
        {
            "id": "deck-module",
            "label": "Add upper deck module",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "DeckModule",
                "-P",
                "length=46",
                "-P",
                "width=24",
                "-P",
                "height=7",
                "-pos",
                "-14,-12,30",
            ],
            "wait_preview": True,
        },
        {
            "id": "rear-power-pack",
            "label": "Add rear power pack",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RearPowerPack",
                "-P",
                "length=24",
                "-P",
                "width=22",
                "-P",
                "height=14",
                "-pos",
                "-34,-11,37",
            ],
            "wait_preview": True,
        },
        {
            "id": "front-bumper",
            "label": "Add front bumper",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "FrontBumper",
                "-P",
                "length=12",
                "-P",
                "width=24",
                "-P",
                "height=3",
                "-pos",
                "28,-12,25",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-rocker",
            "label": "Add left suspension beam",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftRocker",
                "-P",
                "length=72",
                "-P",
                "width=4",
                "-P",
                "height=3",
                "-pos",
                "-36,-17,20",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-front-wheel",
            "label": "Add left front wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "LeftFrontWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "24,-20,12",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-mid-wheel",
            "label": "Add left middle wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "LeftMidWheel",
                "-P",
                "radius=13",
                "-P",
                "height=6",
                "-pos",
                "0,-20,12",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-rear-wheel",
            "label": "Add left rear wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "LeftRearWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "-26,-20,12",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-front-wheel",
            "label": "Mirror right front wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "mirror",
                "5",
                "--plane",
                "XZ",
                "--name",
                "RightFrontWheel",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-mid-wheel",
            "label": "Mirror right middle wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "mirror",
                "6",
                "--plane",
                "XZ",
                "--name",
                "RightMidWheel",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-rear-wheel",
            "label": "Mirror right rear wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "mirror",
                "7",
                "--plane",
                "XZ",
                "--name",
                "RightRearWheel",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-rocker",
            "label": "Mirror right suspension beam",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "mirror",
                "4",
                "--plane",
                "XZ",
                "--name",
                "RightRocker",
            ],
            "wait_preview": True,
        },
        {
            "id": "mast-base",
            "label": "Add mast base",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "MastBase",
                "-P",
                "radius=3.6",
                "-P",
                "height=12",
                "-pos",
                "8,0,37",
            ],
            "wait_preview": True,
        },
        {
            "id": "mast-neck",
            "label": "Add camera mast",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "MastNeck",
                "-P",
                "radius=1.7",
                "-P",
                "height=26",
                "-pos",
                "8,0,49",
            ],
            "wait_preview": True,
        },
        {
            "id": "camera-head",
            "label": "Add camera head",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "CameraHead",
                "-P",
                "length=16",
                "-P",
                "width=8",
                "-P",
                "height=7",
                "-pos",
                "0,-4,74",
            ],
            "wait_preview": True,
        },
        {
            "id": "sensor-bar",
            "label": "Add sensor bar",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "SensorBar",
                "-P",
                "length=24",
                "-P",
                "width=4",
                "-P",
                "height=3",
                "-pos",
                "-4,-2,81",
            ],
            "wait_preview": True,
        },
        {
            "id": "antenna-mast",
            "label": "Add high-gain antenna mast",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "AntennaMast",
                "-P",
                "radius=1.2",
                "-P",
                "height=12",
                "-pos",
                "-20,0,40",
            ],
            "wait_preview": True,
        },
        {
            "id": "antenna-dish",
            "label": "Add high-gain antenna dish",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "AntennaDish",
                "-P",
                "radius=7",
                "-P",
                "height=2",
                "-pos",
                "-21,0,48",
                "-rot",
                "0,90,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "science-boom",
            "label": "Add science boom",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "ScienceBoom",
                "-P",
                "radius=1.4",
                "-P",
                "height=24",
                "-pos",
                "16,10,30",
                "-rot",
                "0,90,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "sample-head",
            "label": "Add sample head",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "sphere",
                "--name",
                "SampleHead",
                "-P",
                "radius=4.5",
                "-pos",
                "42,10,30",
            ],
            "wait_preview": True,
        },
    ]


def _curiosity_steps() -> List[Dict[str, Any]]:
    """Return a higher-fidelity tiny Curiosity rover build trajectory."""
    return [
        {
            "id": "create-project",
            "label": "Create FreeCAD project",
            "argv": ["document", "new", "--name", "Curiosity", "-o", "{project_path}"],
            "wait_preview": False,
        },
        {
            "id": "start-live-preview",
            "label": "Start poll-mode live preview",
            "argv": [
                "-p",
                "{project_path}",
                "preview",
                "live",
                "start",
                "--recipe",
                "quick",
                "--mode",
                "poll",
                "--source-poll-ms",
                "500",
                "--poll-ms",
                "700",
                "--root-dir",
                "{live_root}",
            ],
            "wait_preview": True,
            "manual_session_payload": True,
        },
        {
            "id": "lower-chassis",
            "label": "Add lower chassis tub",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LowerChassis",
                "-P",
                "length=50",
                "-P",
                "width=34",
                "-P",
                "height=8",
                "-pos",
                "-10,-17,25",
            ],
            "wait_preview": True,
        },
        {
            "id": "upper-deck",
            "label": "Add upper instrument deck",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "UpperDeck",
                "-P",
                "length=34",
                "-P",
                "width=28",
                "-P",
                "height=8",
                "-pos",
                "-8,-14,33",
            ],
            "wait_preview": True,
        },
        {
            "id": "front-avionics",
            "label": "Add front avionics bay",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "FrontAvionics",
                "-P",
                "length=14",
                "-P",
                "width=26",
                "-P",
                "height=8",
                "-pos",
                "24,-13,31",
            ],
            "wait_preview": True,
        },
        {
            "id": "rear-bridge",
            "label": "Add rear bridge deck",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RearBridge",
                "-P",
                "length=14",
                "-P",
                "width=22",
                "-P",
                "height=5",
                "-pos",
                "-24,-11,33",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-rocker",
            "label": "Add left rocker beam",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftRocker",
                "-P",
                "length=46",
                "-P",
                "width=3.5",
                "-P",
                "height=3",
                "-pos",
                "-8,-22,22",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-rocker",
            "label": "Add right rocker beam",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightRocker",
                "-P",
                "length=46",
                "-P",
                "width=3.5",
                "-P",
                "height=3",
                "-pos",
                "-8,18.5,22",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-bogie",
            "label": "Add left bogie beam",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftBogie",
                "-P",
                "length=34",
                "-P",
                "width=3",
                "-P",
                "height=3",
                "-pos",
                "-20,-22,18",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-bogie",
            "label": "Add right bogie beam",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightBogie",
                "-P",
                "length=34",
                "-P",
                "width=3",
                "-P",
                "height=3",
                "-pos",
                "-20,19,18",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-front-link",
            "label": "Add left front suspension link",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftFrontLink",
                "-P",
                "length=18",
                "-P",
                "width=3",
                "-P",
                "height=3",
                "-pos",
                "18,-22,19",
                "-rot",
                "0,0,-28",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-front-link",
            "label": "Add right front suspension link",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightFrontLink",
                "-P",
                "length=18",
                "-P",
                "width=3",
                "-P",
                "height=3",
                "-pos",
                "18,19,19",
                "-rot",
                "0,0,28",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-rear-link",
            "label": "Add left rear suspension link",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftRearLink",
                "-P",
                "length=16",
                "-P",
                "width=3",
                "-P",
                "height=3",
                "-pos",
                "-33,-22,18",
                "-rot",
                "0,0,30",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-rear-link",
            "label": "Add right rear suspension link",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightRearLink",
                "-P",
                "length=16",
                "-P",
                "width=3",
                "-P",
                "height=3",
                "-pos",
                "-33,19,18",
                "-rot",
                "0,0,-30",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-front-wheel",
            "label": "Add left front wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "LeftFrontWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "24,-25,12",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-mid-wheel",
            "label": "Add left middle wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "LeftMidWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "-2,-25,10",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-rear-wheel",
            "label": "Add left rear wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "LeftRearWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "-26,-25,12",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-front-wheel",
            "label": "Add right front wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "RightFrontWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "24,19,12",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-mid-wheel",
            "label": "Add right middle wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "RightMidWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "-2,19,10",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-rear-wheel",
            "label": "Add right rear wheel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "RightRearWheel",
                "-P",
                "radius=12",
                "-P",
                "height=6",
                "-pos",
                "-26,19,12",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-front-wheel-outboard",
            "label": "Push right front wheel to mirrored track width",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "15",
                "0",
                "--y",
                "min",
                "--to-y",
                "max",
                "--dy",
                "8.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-mid-wheel-outboard",
            "label": "Push right middle wheel to mirrored track width",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "16",
                "0",
                "--y",
                "min",
                "--to-y",
                "max",
                "--dy",
                "8.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-rear-wheel-outboard",
            "label": "Push right rear wheel to mirrored track width",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "17",
                "0",
                "--y",
                "min",
                "--to-y",
                "max",
                "--dy",
                "8.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-rocker-wheel-plane",
            "label": "Seat left rocker into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "4",
                "12",
                "--y",
                "min",
                "--to-y",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-rocker-wheel-plane",
            "label": "Seat right rocker into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "5",
                "15",
                "--y",
                "max",
                "--to-y",
                "min",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-bogie-wheel-plane",
            "label": "Seat left bogie into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "6",
                "13",
                "--y",
                "min",
                "--to-y",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-bogie-wheel-plane",
            "label": "Seat right bogie into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "7",
                "16",
                "--y",
                "max",
                "--to-y",
                "min",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-front-link-wheel-plane",
            "label": "Seat left front link into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "8",
                "12",
                "--y",
                "min",
                "--to-y",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-front-link-wheel-plane",
            "label": "Seat right front link into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "9",
                "15",
                "--y",
                "max",
                "--to-y",
                "min",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-rear-link-wheel-plane",
            "label": "Seat left rear link into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "10",
                "14",
                "--y",
                "min",
                "--to-y",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-rear-link-wheel-plane",
            "label": "Seat right rear link into wheel plane",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "11",
                "17",
                "--y",
                "max",
                "--to-y",
                "min",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-front-axle-block",
            "label": "Add left front axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftFrontAxleBlock",
                "-P",
                "length=6",
                "-P",
                "width=8",
                "-P",
                "height=8",
                "-pos",
                "21,-24,16",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-front-axle-block",
            "label": "Attach left front axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "18",
                "12",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "min",
                "--to-y",
                "max",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "1.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-mid-axle-block",
            "label": "Add left middle axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftMidAxleBlock",
                "-P",
                "length=6",
                "-P",
                "width=8",
                "-P",
                "height=8",
                "-pos",
                "-5,-24,14",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-mid-axle-block",
            "label": "Attach left middle axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "19",
                "13",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "min",
                "--to-y",
                "max",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "3.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-rear-axle-block",
            "label": "Add left rear axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftRearAxleBlock",
                "-P",
                "length=6",
                "-P",
                "width=8",
                "-P",
                "height=8",
                "-pos",
                "-29,-24,16",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-rear-axle-block",
            "label": "Attach left rear axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "20",
                "14",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "min",
                "--to-y",
                "max",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "1.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-front-axle-block",
            "label": "Add right front axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightFrontAxleBlock",
                "-P",
                "length=6",
                "-P",
                "width=8",
                "-P",
                "height=8",
                "-pos",
                "21,17,16",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-front-axle-block",
            "label": "Attach right front axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "21",
                "15",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "max",
                "--to-y",
                "min",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "1.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-mid-axle-block",
            "label": "Add right middle axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightMidAxleBlock",
                "-P",
                "length=6",
                "-P",
                "width=8",
                "-P",
                "height=8",
                "-pos",
                "-5,17,14",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-mid-axle-block",
            "label": "Attach right middle axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "22",
                "16",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "max",
                "--to-y",
                "min",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "3.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-rear-axle-block",
            "label": "Add right rear axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightRearAxleBlock",
                "-P",
                "length=6",
                "-P",
                "width=8",
                "-P",
                "height=8",
                "-pos",
                "-29,17,16",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-rear-axle-block",
            "label": "Attach right rear axle block",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "23",
                "17",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "max",
                "--to-y",
                "min",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "1.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-rocker-pivot-housing",
            "label": "Add left rocker pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftRockerPivotHousing",
                "-P",
                "length=8",
                "-P",
                "width=8",
                "-P",
                "height=6",
                "-pos",
                "11,-22,21",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-rocker-pivot-housing",
            "label": "Seat left rocker pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "24",
                "4",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "min",
                "--to-y",
                "min",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "3.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-rocker-pivot-housing",
            "label": "Add right rocker pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightRockerPivotHousing",
                "-P",
                "length=8",
                "-P",
                "width=8",
                "-P",
                "height=6",
                "-pos",
                "11,17,21",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-rocker-pivot-housing",
            "label": "Seat right rocker pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "25",
                "5",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "max",
                "--to-y",
                "max",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "3.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "left-bogie-pivot-housing",
            "label": "Add left bogie pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftBogiePivotHousing",
                "-P",
                "length=8",
                "-P",
                "width=8",
                "-P",
                "height=6",
                "-pos",
                "-7,-22,17",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-left-bogie-pivot-housing",
            "label": "Seat left bogie pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "26",
                "6",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "min",
                "--to-y",
                "min",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "5.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-bogie-pivot-housing",
            "label": "Add right bogie pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightBogiePivotHousing",
                "-P",
                "length=8",
                "-P",
                "width=8",
                "-P",
                "height=6",
                "-pos",
                "-7,17,17",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-bogie-pivot-housing",
            "label": "Seat right bogie pivot housing",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "27",
                "7",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "max",
                "--to-y",
                "max",
                "--z",
                "max",
                "--to-z",
                "max",
                "--dz",
                "5.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "mast-pedestal",
            "label": "Add mast pedestal",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "MastPedestal",
                "-P",
                "radius=3.8",
                "-P",
                "height=10",
                "-pos",
                "2,0,41",
            ],
            "wait_preview": True,
        },
        {
            "id": "mast-column",
            "label": "Add mast column",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "MastColumn",
                "-P",
                "radius=1.7",
                "-P",
                "height=28",
                "-pos",
                "2,0,51",
            ],
            "wait_preview": True,
        },
        {
            "id": "camera-bar",
            "label": "Add mast camera bridge",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "CameraBridge",
                "-P",
                "length=18",
                "-P",
                "width=4",
                "-P",
                "height=3",
                "-pos",
                "-5,-2,79",
            ],
            "wait_preview": True,
        },
        {
            "id": "camera-pods",
            "label": "Add stereo camera pods",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "LeftCameraPod",
                "-P",
                "length=7",
                "-P",
                "width=6",
                "-P",
                "height=7",
                "-pos",
                "-11,-7,73",
            ],
            "wait_preview": True,
        },
        {
            "id": "chemcam-barrel",
            "label": "Add ChemCam barrel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "ChemCamBarrel",
                "-P",
                "radius=0.9",
                "-P",
                "height=9",
                "-pos",
                "-2,-0.5,75",
                "-rot",
                "0,90,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "right-camera-pod",
            "label": "Add right camera pod",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RightCameraPod",
                "-P",
                "length=7",
                "-P",
                "width=6",
                "-P",
                "height=7",
                "-pos",
                "4,1,73",
            ],
            "wait_preview": True,
        },
        {
            "id": "rtg-body",
            "label": "Add rear RTG body",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "RTGBody",
                "-P",
                "radius=6.5",
                "-P",
                "height=18",
                "-pos",
                "-28,13,35",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "rtg-cap",
            "label": "Add RTG cap",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cone",
                "--name",
                "RTGCap",
                "-P",
                "radius1=6.2",
                "-P",
                "radius2=2.8",
                "-P",
                "height=6",
                "-pos",
                "-32,13,35",
                "-rot",
                "90,0,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "rtg-strut",
            "label": "Add RTG support strut",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "RTGStrut",
                "-P",
                "length=11",
                "-P",
                "width=3",
                "-P",
                "height=3",
                "-pos",
                "-20,11,35",
                "-rot",
                "0,0,-18",
            ],
            "wait_preview": True,
        },
        {
            "id": "hga-stem",
            "label": "Add high-gain antenna stem",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "HGAStem",
                "-P",
                "radius=1.2",
                "-P",
                "height=14",
                "-pos",
                "-1,11,43",
            ],
            "wait_preview": True,
        },
        {
            "id": "hga-dish",
            "label": "Add high-gain antenna dish",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "HGADish",
                "-P",
                "radius=6.3",
                "-P",
                "height=1.3",
                "-pos",
                "1,14,56",
                "-rot",
                "0,90,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "arm-shoulder",
            "label": "Add robotic arm shoulder",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "ArmShoulder",
                "-P",
                "radius=2.4",
                "-P",
                "height=8",
                "-pos",
                "32,0,30",
                "-rot",
                "0,90,0",
            ],
            "wait_preview": True,
        },
        {
            "id": "arm-upper",
            "label": "Add robotic arm upper segment",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "ArmUpper",
                "-P",
                "radius=1.6",
                "-P",
                "height=16",
                "-pos",
                "35,0,28",
                "-rot",
                "0,90,-26",
            ],
            "wait_preview": True,
        },
        {
            "id": "arm-fore",
            "label": "Add robotic forearm",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "cylinder",
                "--name",
                "ArmFore",
                "-P",
                "radius=1.4",
                "-P",
                "height=15",
                "-pos",
                "46,0,19",
                "-rot",
                "0,90,18",
            ],
            "wait_preview": True,
        },
        {
            "id": "turret",
            "label": "Add drill turret",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "sphere",
                "--name",
                "ToolTurret",
                "-P",
                "radius=4.1",
                "-pos",
                "56,0,13",
            ],
            "wait_preview": True,
        },
        {
            "id": "deck-sensor-pack",
            "label": "Add deck sensor pack",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "add",
                "box",
                "--name",
                "DeckSensorPack",
                "-P",
                "length=12",
                "-P",
                "width=7",
                "-P",
                "height=4",
                "-pos",
                "-10,-3,41",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-upper-deck",
            "label": "Seat upper deck on chassis",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "1",
                "0",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "min",
                "--to-z",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-front-avionics",
            "label": "Seat front avionics",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "2",
                "1",
                "--x",
                "min",
                "--to-x",
                "max",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "min",
                "--to-z",
                "min",
                "--dz",
                "-2",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-rear-bridge",
            "label": "Seat rear bridge",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "3",
                "1",
                "--x",
                "max",
                "--to-x",
                "min",
                "--dx",
                "-1.5",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "min",
                "--to-z",
                "min",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-mast-column",
            "label": "Attach mast column to pedestal",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "29",
                "28",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "min",
                "--to-z",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-camera-bridge",
            "label": "Attach camera bridge to mast",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "30",
                "29",
                "--x",
                "center",
                "--to-x",
                "center",
                "--dx",
                "-1.0",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "min",
                "--to-z",
                "max",
                "--dz",
                "-3.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-camera-pods",
            "label": "Hang camera pods under bridge",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "31",
                "30",
                "--x",
                "center",
                "--to-x",
                "min",
                "--dx",
                "2.0",
                "--z",
                "max",
                "--to-z",
                "min",
                "--dz",
                "1.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-right-camera-pod",
            "label": "Hang right camera pod under bridge",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "33",
                "30",
                "--x",
                "center",
                "--to-x",
                "max",
                "--dx",
                "-2.0",
                "--z",
                "max",
                "--to-z",
                "min",
                "--dz",
                "1.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-chemcam",
            "label": "Attach ChemCam barrel",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "32",
                "30",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "center",
                "--to-z",
                "center",
                "--dz",
                "-2.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-rtg-body",
            "label": "Attach RTG body to rear bridge",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "34",
                "3",
                "--x",
                "max",
                "--to-x",
                "min",
                "--dx",
                "-2.0",
                "--y",
                "center",
                "--to-y",
                "center",
                "--dy",
                "9.0",
                "--z",
                "center",
                "--to-z",
                "center",
                "--dz",
                "2.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-rtg-cap",
            "label": "Cap the RTG body",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "35",
                "34",
                "--x",
                "max",
                "--to-x",
                "min",
                "--dx",
                "0.5",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "center",
                "--to-z",
                "center",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-rtg-strut",
            "label": "Support the RTG",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "36",
                "34",
                "--x",
                "max",
                "--to-x",
                "max",
                "--dx",
                "8.0",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "center",
                "--to-z",
                "center",
                "--dz",
                "-3.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-hga-stem",
            "label": "Attach antenna stem",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "37",
                "1",
                "--x",
                "center",
                "--to-x",
                "center",
                "--dx",
                "10.0",
                "--y",
                "center",
                "--to-y",
                "center",
                "--dy",
                "11.0",
                "--z",
                "min",
                "--to-z",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-hga-dish",
            "label": "Attach antenna dish",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "38",
                "37",
                "--x",
                "center",
                "--to-x",
                "center",
                "--y",
                "center",
                "--to-y",
                "center",
                "--dy",
                "3.0",
                "--z",
                "min",
                "--to-z",
                "max",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-arm-shoulder",
            "label": "Attach arm shoulder to front bay",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "39",
                "2",
                "--x",
                "min",
                "--to-x",
                "max",
                "--dx",
                "-1.0",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "center",
                "--to-z",
                "center",
                "--dz",
                "-3.0",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-arm-upper",
            "label": "Attach upper arm",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "40",
                "39",
                "--x",
                "min",
                "--to-x",
                "max",
                "--dx",
                "-1.5",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "center",
                "--to-z",
                "center",
                "--dz",
                "-1.5",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-arm-fore",
            "label": "Attach forearm",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "41",
                "40",
                "--x",
                "min",
                "--to-x",
                "max",
                "--dx",
                "-1.5",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "center",
                "--to-z",
                "center",
                "--dz",
                "-2.5",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-turret",
            "label": "Attach tool turret",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "42",
                "41",
                "--x",
                "min",
                "--to-x",
                "max",
                "--dx",
                "-0.5",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "center",
                "--to-z",
                "center",
                "--dz",
                "-1.5",
            ],
            "wait_preview": True,
        },
        {
            "id": "align-sensor-pack",
            "label": "Seat sensor pack on deck",
            "argv": [
                "-p",
                "{project_path}",
                "part",
                "align",
                "43",
                "1",
                "--x",
                "center",
                "--to-x",
                "center",
                "--dx",
                "-7.0",
                "--y",
                "center",
                "--to-y",
                "center",
                "--z",
                "min",
                "--to-z",
                "max",
            ],
            "wait_preview": True,
        },
    ]


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "curiosity": {
        "title": "Curiosity",
        "subtitle": "high-fidelity tiny Curiosity rover built with cli-anything-freecad and live preview",
        "project_name": "Curiosity",
        "project_file": "curiosity.json",
        "steps": _curiosity_steps(),
    },
    "mars-rover": {
        "title": "Mars Rover",
        "subtitle": "modular six-wheel rover built with cli-anything-freecad and live preview",
        "project_name": "MarsRover",
        "project_file": "mars_rover.json",
        "steps": _mars_rover_steps(),
    },
    "orbital-relay": {
        "title": "Orbital Relay",
        "subtitle": "fictional sci-fi station built with FreeCAD primitives",
        "project_name": "OrbitalRelay",
        "project_file": "orbital_relay.json",
        "steps": [
            {
                "id": "create-project",
                "label": "Create FreeCAD project",
                "argv": ["document", "new", "--name", "OrbitalRelay", "-o", "{project_path}"],
                "wait_preview": False,
            },
            {
                "id": "start-live-preview",
                "label": "Start poll-mode live preview",
                "argv": [
                    "-p",
                    "{project_path}",
                    "preview",
                    "live",
                    "start",
                    "--recipe",
                    "quick",
                    "--mode",
                    "poll",
                    "--source-poll-ms",
                    "500",
                    "--poll-ms",
                    "700",
                    "--root-dir",
                    "{live_root}",
                ],
                "wait_preview": True,
                "manual_session_payload": True,
            },
            {
                "id": "base-deck",
                "label": "Add base deck",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "BaseDeck",
                    "-P",
                    "length=60",
                    "-P",
                    "width=40",
                    "-P",
                    "height=8",
                ],
                "wait_preview": True,
            },
            {
                "id": "core-spine",
                "label": "Add core spine",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cylinder",
                    "--name",
                    "CoreSpine",
                    "-P",
                    "radius=9",
                    "-P",
                    "height=24",
                    "-pos",
                    "0,0,8",
                ],
                "wait_preview": True,
            },
            {
                "id": "tail-fin",
                "label": "Add tail fin",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "TailFin",
                    "-P",
                    "length=10",
                    "-P",
                    "width=6",
                    "-P",
                    "height=24",
                    "-pos",
                    "0,-18,8",
                ],
                "wait_preview": True,
            },
            {
                "id": "sensor-dome",
                "label": "Add sensor dome",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "sphere",
                    "--name",
                    "SensorDome",
                    "-P",
                    "radius=12",
                    "-pos",
                    "0,0,34",
                ],
                "wait_preview": True,
            },
            {
                "id": "port-wing",
                "label": "Add port wing",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "PortWing",
                    "-P",
                    "length=18",
                    "-P",
                    "width=28",
                    "-P",
                    "height=5",
                    "-pos",
                    "-28,0,14",
                ],
                "wait_preview": True,
            },
            {
                "id": "starboard-wing",
                "label": "Add starboard wing",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "StarboardWing",
                    "-P",
                    "length=18",
                    "-P",
                    "width=28",
                    "-P",
                    "height=5",
                    "-pos",
                    "28,0,14",
                ],
                "wait_preview": True,
            },
            {
                "id": "beacon-cone",
                "label": "Add beacon cone",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cone",
                    "--name",
                    "BeaconCone",
                    "-P",
                    "radius1=10",
                    "-P",
                    "radius2=3",
                    "-P",
                    "height=16",
                    "-pos",
                    "0,18,8",
                ],
                "wait_preview": True,
            },
            {
                "id": "antenna",
                "label": "Add antenna mast",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cylinder",
                    "--name",
                    "AntennaMast",
                    "-P",
                    "radius=2",
                    "-P",
                    "height=18",
                    "-pos",
                    "0,0,48",
                ],
                "wait_preview": True,
            },
            {
                "id": "halo-ring",
                "label": "Add halo ring",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "torus",
                    "--name",
                    "HaloRing",
                    "-P",
                    "radius1=20",
                    "-P",
                    "radius2=2.5",
                    "-pos",
                    "0,0,28",
                ],
                "wait_preview": True,
            },
        ],
    },
    "empire-state-building": {
        "title": "Empire State Building",
        "subtitle": "tiny iconic skyscraper model built with cli-anything-freecad",
        "project_name": "EmpireStateBuilding",
        "project_file": "empire_state_building.json",
        "steps": [
            {
                "id": "create-project",
                "label": "Create FreeCAD project",
                "argv": ["document", "new", "--name", "EmpireStateBuilding", "-o", "{project_path}"],
                "wait_preview": False,
            },
            {
                "id": "start-live-preview",
                "label": "Start poll-mode live preview",
                "argv": [
                    "-p",
                    "{project_path}",
                    "preview",
                    "live",
                    "start",
                    "--recipe",
                    "quick",
                    "--mode",
                    "poll",
                    "--source-poll-ms",
                    "500",
                    "--poll-ms",
                    "700",
                    "--root-dir",
                    "{live_root}",
                ],
                "wait_preview": True,
                "manual_session_payload": True,
            },
            {
                "id": "podium",
                "label": "Add podium base",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "Podium",
                    "-P",
                    "length=52",
                    "-P",
                    "width=88",
                    "-P",
                    "height=10",
                ],
                "wait_preview": True,
            },
            {
                "id": "lower-mass",
                "label": "Add lower tower mass",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "LowerMass",
                    "-P",
                    "length=36",
                    "-P",
                    "width=64",
                    "-P",
                    "height=20",
                    "-pos",
                    "0,0,10",
                ],
                "wait_preview": True,
            },
            {
                "id": "mid-mass",
                "label": "Add mid setback mass",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "MidMass",
                    "-P",
                    "length=28",
                    "-P",
                    "width=44",
                    "-P",
                    "height=22",
                    "-pos",
                    "0,0,30",
                ],
                "wait_preview": True,
            },
            {
                "id": "upper-shaft",
                "label": "Add upper shaft",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "UpperShaft",
                    "-P",
                    "length=20",
                    "-P",
                    "width=28",
                    "-P",
                    "height=24",
                    "-pos",
                    "0,0,52",
                ],
                "wait_preview": True,
            },
            {
                "id": "left-crown-pier",
                "label": "Add left crown pier",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "LeftCrownPier",
                    "-P",
                    "length=16",
                    "-P",
                    "width=10",
                    "-P",
                    "height=26",
                    "-pos",
                    "-12,0,76",
                ],
                "wait_preview": True,
            },
            {
                "id": "right-crown-pier",
                "label": "Add right crown pier",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "RightCrownPier",
                    "-P",
                    "length=16",
                    "-P",
                    "width=10",
                    "-P",
                    "height=26",
                    "-pos",
                    "12,0,76",
                ],
                "wait_preview": True,
            },
            {
                "id": "central-crown",
                "label": "Add central crown tower",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "CentralCrown",
                    "-P",
                    "length=16",
                    "-P",
                    "width=16",
                    "-P",
                    "height=32",
                    "-pos",
                    "0,0,76",
                ],
                "wait_preview": True,
            },
            {
                "id": "upper-crown",
                "label": "Add upper crown",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "box",
                    "--name",
                    "UpperCrown",
                    "-P",
                    "length=10",
                    "-P",
                    "width=12",
                    "-P",
                    "height=18",
                    "-pos",
                    "0,0,108",
                ],
                "wait_preview": True,
            },
            {
                "id": "mast-lower",
                "label": "Add mast base",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cylinder",
                    "--name",
                    "MastLower",
                    "-P",
                    "radius=2.2",
                    "-P",
                    "height=14",
                    "-pos",
                    "0,0,126",
                ],
                "wait_preview": True,
            },
            {
                "id": "mast-upper",
                "label": "Add upper antenna mast",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cylinder",
                    "--name",
                    "MastUpper",
                    "-P",
                    "radius=1.3",
                    "-P",
                    "height=12",
                    "-pos",
                    "0,0,140",
                ],
                "wait_preview": True,
            },
            {
                "id": "spire-tip",
                "label": "Add spire tip",
                "argv": [
                    "-p",
                    "{project_path}",
                    "part",
                    "add",
                    "cone",
                    "--name",
                    "SpireTip",
                    "-P",
                    "radius1=2.0",
                    "-P",
                    "radius2=0.2",
                    "-P",
                    "height=10",
                    "-pos",
                    "0,0,152",
                ],
                "wait_preview": True,
            },
        ],
    },
    "taipei-101": {
        "title": "Taipei 101",
        "subtitle": "tiny stacked-shoulder skyscraper model built with cli-anything-freecad",
        "project_name": "Taipei101",
        "project_file": "taipei_101.json",
        "steps": _taipei_101_steps(),
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_scenario(name: str) -> Dict[str, Any]:
    try:
        return SCENARIOS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario: {name!r}. Available: {', '.join(sorted(SCENARIOS))}") from exc


def ensure_clean_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def format_cmd(argv: List[str]) -> str:
    return " ".join(shlex_quote(arg) for arg in argv)


def shlex_quote(value: str) -> str:
    if not value or any(c in value for c in " \t\n\"'`$&|;()[]{}<>"):
        return "'" + value.replace("'", "'\"'\"'") + "'"
    return value


def run_cli(argv: List[str], *, timeout: int = 300) -> Dict[str, Any]:
    cmd = [FREECAD_CLI, "--json"] + argv
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=FREECAD_WORKDIR,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    finished = time.time()
    payload: Dict[str, Any] = {
        "argv": cmd,
        "display_cmd": format_cmd(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "started_at": started,
        "finished_at": finished,
        "duration_s": round(finished - started, 3),
    }
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {payload['display_cmd']}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    try:
        payload["json"] = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError:
        payload["json"] = None
    return payload


def _load_motion_module():
    if str(FREECAD_WORKDIR) not in sys.path:
        sys.path.insert(0, str(FREECAD_WORKDIR))
    from cli_anything.freecad.core import motion as motion_mod

    return motion_mod


def _is_noop_alignment(result: Dict[str, Any]) -> bool:
    """Return True when a part-align command produced no placement delta."""
    payload = result.get("json") or {}
    delta = payload.get("delta")
    if not isinstance(delta, dict):
        return False
    try:
        return all(abs(float(delta.get(axis, 0.0))) <= 1e-9 for axis in ("x", "y", "z"))
    except (TypeError, ValueError):
        return False


def wait_for_bundle_update(
    session_path: Path,
    expected_count: int,
    timeout_s: float,
    *,
    previous_bundle_id: Optional[str] = None,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    latest = None
    while time.time() < deadline:
        latest = load_json(session_path)
        current_bundle_id = latest.get("current_bundle_id")
        if latest.get("bundle_count", 0) >= expected_count:
            return latest
        if previous_bundle_id and current_bundle_id and current_bundle_id != previous_bundle_id:
            return latest
        time.sleep(0.4)
    raise TimeoutError(
        f"Timed out waiting for bundle update >= {expected_count} in {session_path}: {latest}"
    )


def extract_bundle_artifacts(session_payload: Dict[str, Any], snapshot_dir: Path) -> Dict[str, Any]:
    current_manifest_path = Path(session_payload["current_manifest_path"]).resolve()
    manifest = load_json(current_manifest_path)
    bundle_dir = current_manifest_path.parent
    summary_path = bundle_dir / manifest.get("summary_path", "summary.json")
    if summary_path.is_file():
        shutil.copy2(summary_path, snapshot_dir / "summary.json")
    shutil.copy2(current_manifest_path, snapshot_dir / "manifest.json")
    copied: Dict[str, str] = {}
    for artifact in manifest.get("artifacts", []):
        artifact_id = artifact.get("artifact_id")
        artifact_src = (bundle_dir / artifact.get("path", "")).resolve()
        if not artifact_id or not artifact_src.is_file():
            continue
        dest = snapshot_dir / f"{artifact_id}{artifact_src.suffix.lower()}"
        shutil.copy2(artifact_src, dest)
        copied[artifact_id] = str(dest)
    return {
        "bundle_id": manifest.get("bundle_id"),
        "bundle_dir": str(bundle_dir),
        "manifest_path": str(snapshot_dir / "manifest.json"),
        "summary_path": str(snapshot_dir / "summary.json"),
        "artifacts": copied,
    }


def generate_live_html(session_dir: Path, output_path: Path) -> None:
    cmd = [CLI_HUB, "preview", "html", str(session_dir), "-o", str(output_path)]
    subprocess.run(
        cmd,
        cwd=CLI_HUB_WORKDIR,
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )


def collect_demo(output_dir: Path, scenario_name: str) -> Path:
    scenario = get_scenario(scenario_name)
    run_dir = ensure_clean_dir(output_dir)
    snapshots_dir = run_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    project_path = run_dir / scenario["project_file"]
    live_root = run_dir / "live-root"

    trajectory: Dict[str, Any] = {
        "protocol": "freecad-live-demo/v1",
        "created_at": now_iso(),
        "scenario": scenario_name,
        "scenario_title": scenario["title"],
        "scenario_subtitle": scenario["subtitle"],
        "repo_root": str(REPO_ROOT),
        "freecad_workdir": str(FREECAD_WORKDIR),
        "project_path": str(project_path),
        "live_root": str(live_root),
        "commands": [],
        "preview_events": [],
        "notes": [
            "All commands were executed against the real cli-anything-freecad entry point.",
            "All preview images came from the real FreeCAD live-preview poll session.",
            "The final video is a programmatic composition of these real artifacts.",
        ],
    }

    started_at = time.time()
    session_path: Optional[Path] = None
    session_dir: Optional[Path] = None
    live_recipe = "quick"
    expected_bundle_count = 0
    failure: Optional[BaseException] = None
    partial_timeline_path = run_dir / "trajectory.partial.json"

    try:
        for idx, step in enumerate(scenario["steps"]):
            argv = [arg.format(project_path=project_path, live_root=live_root) for arg in step["argv"]]
            result = run_cli(argv)
            result["index"] = idx
            result["id"] = step["id"]
            result["label"] = step["label"]
            result["timeline_start_s"] = round(result["started_at"] - started_at, 3)
            result["timeline_end_s"] = round(result["finished_at"] - started_at, 3)
            trajectory["commands"].append(result)
            write_json(partial_timeline_path, trajectory)

            if step.get("manual_session_payload"):
                payload = result.get("json") or {}
                session_path = Path(payload["_session_path"]).resolve()
                session_dir = Path(payload["_session_dir"]).resolve()
                expected_bundle_count = int(payload.get("bundle_count", 0))
                preview_sequence = len(trajectory["preview_events"]) + 1
                snapshot_dir = snapshots_dir / f"{preview_sequence:02d}_{step['id']}"
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                copied = extract_bundle_artifacts(payload, snapshot_dir)
                preview_event = {
                    "sequence_index": preview_sequence,
                    "step_index": idx,
                    "step_id": step["id"],
                    "step_label": step["label"],
                    "ready_at": time.time(),
                    "timeline_ready_s": round(time.time() - started_at, 3),
                    "latency_s": round(time.time() - result["finished_at"], 3),
                    "bundle_count": expected_bundle_count,
                    "publish_reason": (payload.get("source_state") or {}).get("last_publish_reason"),
                    "session_path": str(session_path),
                    "session_dir": str(session_dir),
                    "snapshot_dir": str(snapshot_dir),
                    "copied_bundle": copied,
                }
                trajectory["preview_events"].append(preview_event)
                write_json(partial_timeline_path, trajectory)
                continue

            if step.get("wait_preview"):
                if session_path is None or session_dir is None:
                    raise RuntimeError(f"Step {step['id']} expected an active live session")
                if _is_noop_alignment(result):
                    continue
                expected_bundle_count += 1
                previous_bundle_id = trajectory["preview_events"][-1]["copied_bundle"]["bundle_id"] if trajectory["preview_events"] else None
                payload = wait_for_bundle_update(
                    session_path,
                    expected_bundle_count,
                    DEFAULT_WAIT_TIMEOUT_S,
                    previous_bundle_id=previous_bundle_id,
                )
                observed_bundle_count = int(payload.get("bundle_count", expected_bundle_count))
                expected_bundle_count = observed_bundle_count
                preview_sequence = len(trajectory["preview_events"]) + 1
                snapshot_dir = snapshots_dir / f"{preview_sequence:02d}_{step['id']}"
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                copied = extract_bundle_artifacts(payload, snapshot_dir)
                ready_at = time.time()
                preview_event = {
                    "sequence_index": preview_sequence,
                    "step_index": idx,
                    "step_id": step["id"],
                    "step_label": step["label"],
                    "ready_at": ready_at,
                    "timeline_ready_s": round(ready_at - started_at, 3),
                    "latency_s": round(ready_at - result["finished_at"], 3),
                    "bundle_count": int(payload.get("bundle_count", 0)),
                    "publish_reason": (payload.get("source_state") or {}).get("last_publish_reason"),
                    "session_path": str(session_path),
                    "session_dir": str(session_dir),
                    "snapshot_dir": str(snapshot_dir),
                    "copied_bundle": copied,
                }
                trajectory["preview_events"].append(preview_event)
                write_json(partial_timeline_path, trajectory)

        if session_dir is not None:
            generate_live_html(session_dir, run_dir / "live.html")
            trajectory["final_session_dir"] = str(session_dir)
            trajectory["final_session_path"] = str(session_dir / "session.json")
            trajectory["final_live_html"] = str(run_dir / "live.html")
    except Exception as exc:
        failure = exc
        trajectory["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    finally:
        if project_path.is_file():
            try:
                stop_result = run_cli(
                    [
                        "-p",
                        str(project_path),
                        "preview",
                        "live",
                        "stop",
                        "--recipe",
                        live_recipe,
                        "--root-dir",
                        str(live_root),
                    ],
                    timeout=120,
                )
                trajectory["stop_command"] = {
                    "display_cmd": stop_result["display_cmd"],
                    "returncode": stop_result["returncode"],
                    "stdout": stop_result["stdout"],
                    "stderr": stop_result["stderr"],
                }
            except Exception as exc:  # pragma: no cover - cleanup best effort
                trajectory["stop_error"] = str(exc)

    trajectory["completed_at"] = now_iso()
    timeline_path = write_json(run_dir / "trajectory.json", trajectory)
    if failure is not None:
        raise RuntimeError(
            f"collect_demo failed for scenario {scenario_name!r}; partial trajectory written to {timeline_path}"
        ) from failure
    return timeline_path


def fit_image(img: Image.Image, box: tuple[int, int], *, background: str) -> Image.Image:
    target_w, target_h = box
    canvas = Image.new("RGB", (target_w, target_h), background)
    src = img.convert("RGB")
    scale = min(target_w / src.width, target_h / src.height)
    new_size = (max(1, int(src.width * scale)), max(1, int(src.height * scale)))
    resized = src.resize(new_size, Image.Resampling.LANCZOS)
    x = (target_w - resized.width) // 2
    y = (target_h - resized.height) // 2
    canvas.paste(resized, (x, y))
    return canvas


def _make_box_part(
    *,
    part_id: int,
    name: str,
    length: float,
    width: float,
    height: float,
    position: List[float],
) -> Dict[str, Any]:
    return {
        "id": part_id,
        "name": name,
        "type": "box",
        "params": {
            "length": float(length),
            "width": float(width),
            "height": float(height),
        },
        "placement": {
            "position": [float(v) for v in position],
            "rotation": [0.0, 0.0, 0.0],
        },
        "material_index": None,
        "visible": True,
    }


def _curiosity_showcase_project(base_project: Dict[str, Any]) -> Dict[str, Any]:
    project = copy.deepcopy(base_project)
    parts = [part for part in project.get("parts", []) if not str(part.get("name", "")).startswith("Showcase")]
    next_id = max((int(part.get("id", 0)) for part in parts), default=0) + 1
    extras = [
        _make_box_part(
            part_id=next_id,
            name="ShowcaseGround",
            length=184.0,
            width=96.0,
            height=4.0,
            position=[-72.0, -48.0, -4.0],
        ),
        _make_box_part(
            part_id=next_id + 1,
            name="ShowcaseMarkerA",
            length=12.0,
            width=8.0,
            height=2.0,
            position=[-18.0, -10.0, 0.0],
        ),
        _make_box_part(
            part_id=next_id + 2,
            name="ShowcaseMarkerB",
            length=16.0,
            width=10.0,
            height=3.0,
            position=[24.0, 10.0, 0.0],
        ),
        _make_box_part(
            part_id=next_id + 3,
            name="ShowcaseMarkerC",
            length=18.0,
            width=8.0,
            height=2.0,
            position=[58.0, -4.0, 0.0],
        ),
    ]
    project["parts"] = parts + extras
    return project


def _apply_curiosity_showcase_pose(project: Dict[str, Any], progress: float) -> Dict[str, Any]:
    rover_shift_x = -38.0 + 78.0 * progress
    rover_shift_y = -7.0 + 11.0 * progress
    bump_a = math.exp(-((progress - 0.32) ** 2) / (2 * 0.12 ** 2))
    bump_b = math.exp(-((progress - 0.74) ** 2) / (2 * 0.10 ** 2))
    rover_shift_z = 1.2 + 0.55 * math.sin(progress * math.tau) + 0.85 * bump_a + 0.65 * bump_b
    arm_sway = 0.75 * math.sin(progress * math.tau)
    mast_sway = 0.35 * math.cos(progress * math.pi)
    dish_sway = 0.55 * math.cos(progress * math.tau)

    for part in project.get("parts", []):
        name = str(part.get("name", ""))
        if name.startswith("Showcase"):
            continue
        placement = part.setdefault("placement", {})
        position = placement.setdefault("position", [0.0, 0.0, 0.0])
        while len(position) < 3:
            position.append(0.0)
        position[0] = float(position[0]) + rover_shift_x
        position[1] = float(position[1]) + rover_shift_y
        position[2] = float(position[2]) + rover_shift_z

        if name in {"ArmFore", "ToolTurret"}:
            position[1] += arm_sway
            position[2] += 0.35 * arm_sway
        elif name in {"ArmUpper", "ArmShoulder"}:
            position[1] += 0.35 * arm_sway
        elif name in {"HGADish", "HGAStem"}:
            position[1] += dish_sway
        elif name in {"MastColumn", "CameraBridge", "LeftCameraPod", "RightCameraPod", "ChemCamBarrel"}:
            position[1] += mast_sway
    return project


def generate_curiosity_showcase_sequence(trajectory: Dict[str, Any], run_dir: Path) -> Optional[Dict[str, Any]]:
    if trajectory.get("scenario") != "curiosity":
        return None

    showcase_dir = run_dir / "showcase"
    manifest_path = showcase_dir / "sequence.json"
    if manifest_path.is_file():
        cached = load_json(manifest_path)
        frames = cached.get("frames") or []
        if frames and all(Path(frame.get("hero_path", "")).is_file() for frame in frames):
            return cached

    source_project_path = Path(trajectory["project_path"]).expanduser().resolve()
    if not source_project_path.is_file():
        return None

    ensure_clean_dir(showcase_dir)
    projects_dir = ensure_clean_dir(showcase_dir / "projects")
    captures_root = ensure_clean_dir(showcase_dir / "captures")

    base_project = _curiosity_showcase_project(load_json(source_project_path))
    write_json(projects_dir / "showcase_base.json", base_project)

    frames: List[Dict[str, Any]] = []
    for idx in range(SHOWCASE_FRAME_COUNT):
        progress = idx / max(1, SHOWCASE_FRAME_COUNT - 1)
        posed_project = _apply_curiosity_showcase_pose(copy.deepcopy(base_project), progress)
        posed_path = write_json(projects_dir / f"pose_{idx:02d}.json", posed_project)
        capture = run_cli(
            ["-p", str(posed_path), "preview", "capture", "--root-dir", str(captures_root)],
            timeout=180,
        )
        payload = capture.get("json") or {}
        bundle_dir = Path(payload.get("_bundle_dir", "")).expanduser()
        hero_path = bundle_dir / "artifacts" / "hero.png"
        if not hero_path.is_file():
            raise RuntimeError(f"Missing hero artifact for showcase frame {idx}: {bundle_dir}")
        frames.append(
            {
                "index": idx,
                "progress": round(progress, 4),
                "project_path": str(posed_path),
                "bundle_dir": str(bundle_dir),
                "hero_path": str(hero_path),
                "capture_cmd": capture["display_cmd"],
            }
        )

    manifest = {
        "protocol": "freecad-showcase-sequence/v1",
        "created_at": now_iso(),
        "scenario": "curiosity",
        "title": "Curiosity Showcase Drive",
        "subtitle": "real extra FreeCAD hero captures generated from the final Curiosity v6 project",
        "source_timeline": str(run_dir / "trajectory.json"),
        "source_project_path": str(source_project_path),
        "duration_s": SHOWCASE_DURATION_S,
        "hold_s": SHOWCASE_HOLD_S,
        "frames": frames,
        "notes": [
            "The ending showcase uses real preview captures from the final Curiosity v6 project.",
            "A staged ground and marker bed are added as extra geometry so whole-rover translation reads visually in hero view.",
            "No GUI screen recording or synthetic CAD viewport frames are used.",
        ],
    }
    write_json(manifest_path, manifest)
    return manifest


def _apply_curiosity_true_motion_pose(project: Dict[str, Any], progress: float) -> Dict[str, Any]:
    drive_x = -46.0 + 96.0 * progress
    drive_y = -10.0 + 15.0 * progress + 2.2 * math.sin(progress * math.pi * 1.2)
    bump_a = math.exp(-((progress - 0.28) ** 2) / (2 * 0.11 ** 2))
    bump_b = math.exp(-((progress - 0.71) ** 2) / (2 * 0.10 ** 2))
    body_heave = 1.15 + 0.45 * math.sin(progress * math.tau) + 0.85 * bump_a + 0.65 * bump_b
    arm_sway = 0.9 * math.sin(progress * math.tau)
    mast_sway = 0.45 * math.cos(progress * math.pi)
    dish_sway = 0.65 * math.cos(progress * math.tau)

    for part in project.get("parts", []):
        name = str(part.get("name", ""))
        if name.startswith("Showcase"):
            continue
        placement = part.setdefault("placement", {})
        position = placement.setdefault("position", [0.0, 0.0, 0.0])
        while len(position) < 3:
            position.append(0.0)

        position[0] = float(position[0]) + drive_x
        position[1] = float(position[1]) + drive_y
        position[2] = float(position[2]) + body_heave

        if name in {"ArmFore", "ToolTurret"}:
            position[1] += arm_sway
            position[2] += 0.35 * arm_sway
        elif name in {"ArmUpper", "ArmShoulder"}:
            position[1] += 0.35 * arm_sway
        elif name in {"HGADish", "HGAStem"}:
            position[1] += dish_sway
            position[2] += 0.18 * dish_sway
        elif name in {"MastColumn", "CameraBridge", "LeftCameraPod", "RightCameraPod", "ChemCamBarrel"}:
            position[1] += mast_sway
            position[2] += 0.12 * mast_sway
    return project


def _curiosity_motion_pivot(project: Dict[str, Any]) -> List[float]:
    xs: List[float] = []
    ys: List[float] = []
    zs: List[float] = []
    for part in project.get("parts", []):
        name = str(part.get("name", ""))
        if name.startswith("Showcase"):
            continue
        placement = part.get("placement") or {}
        position = placement.get("position") or [0.0, 0.0, 0.0]
        if len(position) >= 3:
            xs.append(float(position[0]))
            ys.append(float(position[1]))
            zs.append(float(position[2]))
    if not xs:
        return [0.0, 0.0, 0.0]
    return [
        (min(xs) + max(xs)) / 2.0,
        (min(ys) + max(ys)) / 2.0,
        (min(zs) + max(zs)) / 2.0,
    ]


def _rotate_xy(x: float, y: float, cx: float, cy: float, angle_deg: float) -> List[float]:
    angle = math.radians(angle_deg)
    dx = x - cx
    dy = y - cy
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return [
        cx + dx * cos_a - dy * sin_a,
        cy + dx * sin_a + dy * cos_a,
    ]


def _apply_curiosity_spin_motion_pose(project: Dict[str, Any], progress: float) -> Dict[str, Any]:
    pivot = _curiosity_motion_pivot(project)
    target_center_x = 10.0
    target_center_y = 0.0
    shift_x = target_center_x - pivot[0]
    shift_y = target_center_y - pivot[1]
    spin_deg = -20.0 + 380.0 * progress
    body_heave = 1.05 + 0.25 * math.sin(progress * math.tau * 2.0)
    mast_sway = 0.35 * math.cos(progress * math.tau)
    arm_sway = 0.75 * math.sin(progress * math.tau * 1.5)
    dish_sway = 0.45 * math.sin(progress * math.tau + math.pi / 6.0)

    for part in project.get("parts", []):
        name = str(part.get("name", ""))
        if name.startswith("Showcase"):
            continue
        placement = part.setdefault("placement", {})
        position = placement.setdefault("position", [0.0, 0.0, 0.0])
        rotation = placement.setdefault("rotation", [0.0, 0.0, 0.0])
        while len(position) < 3:
            position.append(0.0)
        while len(rotation) < 3:
            rotation.append(0.0)

        base_x = float(position[0]) + shift_x
        base_y = float(position[1]) + shift_y
        rotated_x, rotated_y = _rotate_xy(base_x, base_y, target_center_x, target_center_y, spin_deg)
        position[0] = rotated_x
        position[1] = rotated_y
        position[2] = float(position[2]) + body_heave

        rotation[2] = float(rotation[2]) + spin_deg

        if name in {"ArmFore", "ToolTurret"}:
            position[1] += 0.6 * arm_sway
            position[2] += 0.25 * arm_sway
        elif name in {"ArmUpper", "ArmShoulder"}:
            position[1] += 0.3 * arm_sway
        elif name in {"HGADish", "HGAStem"}:
            position[1] += 0.35 * dish_sway
            position[2] += 0.12 * dish_sway
        elif name in {"MastColumn", "CameraBridge", "LeftCameraPod", "RightCameraPod", "ChemCamBarrel"}:
            position[1] += 0.3 * mast_sway
            position[2] += 0.10 * mast_sway
    return project


def _apply_curiosity_combo_motion_pose(project: Dict[str, Any], progress: float) -> Dict[str, Any]:
    pivot = _curiosity_motion_pivot(project)
    target_center_x = 10.0
    target_center_y = 0.0
    shift_x = target_center_x - pivot[0]
    shift_y = target_center_y - pivot[1]

    spin_phase = min(1.0, progress / 0.56)
    drive_phase = 0.0 if progress <= 0.56 else min(1.0, (progress - 0.56) / 0.44)
    spin_deg = -18.0 + 360.0 * spin_phase
    drive_ease = 1.0 - pow(1.0 - drive_phase, 2.2)
    drive_dx = 28.0 * drive_ease
    drive_dy = -11.0 * drive_ease
    body_heave = 0.95 + 0.18 * math.sin(progress * math.tau * 2.5)
    mast_sway = 0.25 * math.cos(progress * math.tau * 1.25)
    arm_sway = 0.42 * math.sin(progress * math.tau * 1.7)
    dish_sway = 0.24 * math.sin(progress * math.tau + math.pi / 5.0)

    for part in project.get("parts", []):
        name = str(part.get("name", ""))
        if name.startswith("Showcase"):
            continue
        placement = part.setdefault("placement", {})
        position = placement.setdefault("position", [0.0, 0.0, 0.0])
        rotation = placement.setdefault("rotation", [0.0, 0.0, 0.0])
        while len(position) < 3:
            position.append(0.0)
        while len(rotation) < 3:
            rotation.append(0.0)

        base_x = float(position[0]) + shift_x
        base_y = float(position[1]) + shift_y
        rotated_x, rotated_y = _rotate_xy(base_x, base_y, target_center_x, target_center_y, spin_deg)
        position[0] = rotated_x + drive_dx
        position[1] = rotated_y + drive_dy
        position[2] = float(position[2]) + body_heave

        rotation[2] = float(rotation[2]) + spin_deg

        if name in {"ArmFore", "ToolTurret"}:
            position[1] += 0.35 * arm_sway
            position[2] += 0.20 * arm_sway
        elif name in {"ArmUpper", "ArmShoulder"}:
            position[1] += 0.18 * arm_sway
        elif name in {"HGADish", "HGAStem"}:
            position[1] += 0.18 * dish_sway
            position[2] += 0.10 * dish_sway
        elif name in {"MastColumn", "CameraBridge", "LeftCameraPod", "RightCameraPod", "ChemCamBarrel"}:
            position[1] += 0.18 * mast_sway
            position[2] += 0.08 * mast_sway
    return project


def generate_curiosity_true_motion_showcase(
    timeline_path: Path,
    output_dir: Path,
    *,
    fps: int = FPS,
    keep_frames: bool = True,
    motion_style: str = "drive",
) -> Dict[str, Any]:
    trajectory = load_json(timeline_path)
    if trajectory.get("scenario") != "curiosity":
        raise ValueError("True motion showcase is currently implemented for the curiosity scenario only.")
    if motion_style not in {"drive", "spin", "combo"}:
        raise ValueError("motion_style must be 'drive', 'spin', or 'combo'")

    motion_mod = _load_motion_module()
    output_dir = output_dir.expanduser().resolve()
    ensure_clean_dir(output_dir)
    stills_dir = ensure_clean_dir(output_dir / "stills")
    source_project_path = Path(trajectory["project_path"]).expanduser().resolve()
    if not source_project_path.is_file():
        raise FileNotFoundError(f"Missing Curiosity project: {source_project_path}")

    base_project = _curiosity_showcase_project(load_json(source_project_path))
    motion_project = copy.deepcopy(base_project)
    if motion_style == "drive":
        duration_s = TRUE_MOTION_DURATION_S
        keyframe_count = TRUE_MOTION_KEYFRAME_COUNT
        motion_name = "CuriosityTrueDrive"
        motion_title = "Curiosity True Motion Showcase"
        motion_subtitle = "real frame-by-frame FreeCAD motion render from the final Curiosity v6 project"
        apply_pose = _apply_curiosity_true_motion_pose
        project_stem = "curiosity_true_motion"
        video_name = "curiosity_true_motion.mp4"
    elif motion_style == "spin":
        duration_s = SPIN_MOTION_DURATION_S
        keyframe_count = SPIN_MOTION_KEYFRAME_COUNT
        motion_name = "CuriosityTurntable"
        motion_title = "Curiosity Turntable Motion"
        motion_subtitle = "real frame-by-frame FreeCAD turntable render from the final Curiosity v6 project"
        apply_pose = _apply_curiosity_spin_motion_pose
        project_stem = "curiosity_turntable_motion"
        video_name = "curiosity_turntable_motion.mp4"
    else:
        duration_s = COMBO_MOTION_DURATION_S
        keyframe_count = COMBO_MOTION_KEYFRAME_COUNT
        motion_name = "CuriosityComboShowcase"
        motion_title = "Curiosity Rotation + Drive Motion"
        motion_subtitle = "real frame-by-frame FreeCAD combo motion: one full turntable rotation followed by forward travel"
        apply_pose = _apply_curiosity_combo_motion_pose
        project_stem = "curiosity_combo_motion"
        video_name = "curiosity_combo_motion.mp4"

    motion_mod.create_motion(
        motion_project,
        name=motion_name,
        duration=duration_s,
        fps=int(fps),
        camera="hero",
        width=1600,
        height=900,
        background="White",
        fit_mode="initial",
    )
    motion_index = len(motion_project.get("motions", [])) - 1

    keyframes: List[Dict[str, Any]] = []
    for idx in range(keyframe_count):
        progress = idx / max(1, keyframe_count - 1)
        time_value = round(progress * duration_s, 4)
        posed_project = apply_pose(copy.deepcopy(base_project), progress)
        for part_index, part in enumerate(posed_project.get("parts", [])):
            placement = part.get("placement") or {}
            motion_mod.add_keyframe(
                motion_project,
                motion_index,
                target_kind="part",
                target_index=part_index,
                time_value=time_value,
                position=placement.get("position"),
                rotation=placement.get("rotation"),
            )
        keyframes.append(
            {
                "index": idx,
                "progress": round(progress, 4),
                "time": time_value,
            }
        )

    project_path = write_json(output_dir / f"{project_stem}.json", motion_project)
    frames_dir = output_dir / "frames"
    video_path = output_dir / video_name
    cli_args = [
        "-p",
        str(project_path),
        "motion",
        "render-video",
        str(motion_index),
        str(video_path),
        "--overwrite",
    ]
    if keep_frames:
        cli_args += ["--frames-dir", str(frames_dir)]
    render = run_cli(cli_args, timeout=600)
    render_payload = render.get("json") or {}

    sequence_path = Path(render_payload.get("sequence_path", "")).expanduser()
    sequence: Dict[str, Any] = {}
    if sequence_path and sequence_path.is_file():
        sequence = load_json(sequence_path)
        frames = sequence.get("frames", [])
        if frames:
            still_indices = {
                "start": 0,
                "mid": len(frames) // 2,
                "final": len(frames) - 1,
            }
            for label, frame_index in still_indices.items():
                rel_path = frames[frame_index]["path"]
                source = sequence_path.parent / rel_path
                shutil.copy2(source, stills_dir / f"{label}.png")

    manifest = {
        "protocol": "freecad-true-motion-showcase/v1",
        "created_at": now_iso(),
        "scenario": "curiosity",
        "motion_style": motion_style,
        "title": motion_title,
        "subtitle": motion_subtitle,
        "source_timeline": str(timeline_path),
        "source_project_path": str(source_project_path),
        "motion_project_path": str(project_path),
        "video_path": str(video_path),
        "frames_dir": str(frames_dir) if keep_frames else None,
        "sequence_path": render_payload.get("sequence_path"),
        "duration_s": duration_s,
        "fps": int(fps),
        "keyframe_count": keyframe_count,
        "render": render_payload,
        "sequence": sequence,
        "keyframes": keyframes,
        "notes": [
            "This sequence uses the final Curiosity v6 project as source geometry.",
            "Motion is rendered frame-by-frame through cli-anything-freecad motion render-video.",
            "No synthetic in-between frames or blend-based motion are used.",
        ],
    }
    write_json(output_dir / "motion_manifest.json", manifest)
    return manifest


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[idx:idx + 2], 16) for idx in (0, 2, 4))


def _rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = _hex_rgb(value)
    return (r, g, b, alpha)


def _mix(color_a: str, color_b: str, t: float) -> tuple[int, int, int]:
    a = _hex_rgb(color_a)
    b = _hex_rgb(color_b)
    t = max(0.0, min(1.0, t))
    return tuple(int(a[idx] + (b[idx] - a[idx]) * t) for idx in range(3))


def _trim_middle(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    keep = max(4, (max_len - 1) // 2)
    return f"{text[:keep]}…{text[-keep:]}"


def _wrap_trimmed(text: str, *, width_chars: int, max_lines: int) -> List[str]:
    wrapped = textwrap.wrap(text, width=width_chars, replace_whitespace=False, drop_whitespace=False) or [text]
    if len(wrapped) > max_lines:
        wrapped = wrapped[:max_lines]
        wrapped[-1] = _trim_middle(wrapped[-1].strip(), width_chars)
    return [line.rstrip() for line in wrapped]


def _readable_command_text(cmd_text: str) -> str:
    normalized = cmd_text.strip()
    replacements = {
        str(Path(FREECAD_CLI)): "cli-anything-freecad",
        str(Path(CLI_HUB)): "cli-hub",
        "/root/miniconda3/bin/cli-anything-freecad": "cli-anything-freecad",
        "/root/miniconda3/bin/cli-hub": "cli-hub",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _draw_text_right(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    *,
    font: ImageFont.FreeTypeFont,
    fill: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((x - (bbox[2] - bbox[0]), y), text, fill=fill, font=font)


def _alpha_box(
    canvas: Image.Image,
    area: tuple[int, int, int, int],
    *,
    radius: int,
    fill: tuple[int, int, int, int],
    outline: Optional[tuple[int, int, int, int]] = None,
    width: int = 1,
) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(area, radius=radius, fill=fill, outline=outline, width=width)
    canvas.alpha_composite(overlay)


def _draw_panel(
    canvas: Image.Image,
    area: tuple[int, int, int, int],
    *,
    radius: int,
    fill: str,
    outline: str,
    accent: Optional[str] = None,
) -> None:
    x0, y0, x1, y1 = area
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    for offset, alpha in ((20, 24), (10, 40), (4, 72)):
        draw.rounded_rectangle(
            (x0 + offset, y0 + offset, x1 + offset, y1 + offset),
            radius=radius,
            fill=(0, 0, 0, alpha),
        )
    canvas.alpha_composite(shadow)
    _alpha_box(canvas, area, radius=radius, fill=_rgba(fill, 238), outline=_rgba(outline, 255), width=2)
    if accent:
        _alpha_box(canvas, (x0 + 14, y0 + 12, x1 - 14, y0 + 18), radius=6, fill=_rgba(accent, 220))


def _draw_chip(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    *,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    text_fill: str,
    outline: Optional[str] = None,
) -> None:
    x0, y0, x1, y1 = box
    _alpha_box(
        canvas,
        box,
        radius=min(14, (y1 - y0) // 2),
        fill=_rgba(fill, 245),
        outline=_rgba(outline or fill, 255),
        width=1,
    )
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x0 + ((x1 - x0) - tw) / 2, y0 + ((y1 - y0) - th) / 2 - 1), text, fill=text_fill, font=font)


def _draw_segment_bar(
    canvas: Image.Image,
    box: tuple[int, int, int, int],
    *,
    done: int,
    total: int,
    fill: str,
    empty: str,
) -> None:
    x0, y0, x1, y1 = box
    if total <= 0:
        return
    available_w = max(1, x1 - x0)
    min_seg_w = 1 if total > 28 else 2
    target_gap = 4 if total <= 18 else 2
    if total > 1:
        max_gap = max(0, (available_w - total * min_seg_w) // (total - 1))
        gap = min(target_gap, max_gap)
    else:
        gap = 0
    seg_w = max(min_seg_w, int((available_w - gap * (total - 1)) / total))
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for idx in range(total):
        sx0 = x0 + idx * (seg_w + gap)
        if sx0 >= x1:
            break
        sx1 = min(x1, max(sx0 + 1, sx0 + seg_w))
        color = fill if idx < done else empty
        alpha = 235 if idx < done else 125
        draw.rounded_rectangle((sx0, y0, sx1, y1), radius=4, fill=_rgba(color, alpha))
    canvas.alpha_composite(overlay)


def _draw_soft_glow(
    canvas: Image.Image,
    *,
    center: tuple[int, int],
    radius: int,
    color: str,
    strength: int,
) -> None:
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = center
    for idx, scale in enumerate((1.0, 0.72, 0.45)):
        r = int(radius * scale)
        alpha = max(0, strength - idx * (strength // 3))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_rgba(color, alpha))
    canvas.alpha_composite(overlay)


def build_static_backdrop() -> Image.Image:
    image = Image.new("RGBA", (VIDEO_W, VIDEO_H), _rgba(COLORS["bg_bottom"]))
    pixels = image.load()
    for y in range(VIDEO_H):
        row = _mix(COLORS["bg_top"], COLORS["bg_bottom"], y / max(1, VIDEO_H - 1))
        for x in range(VIDEO_W):
            pixels[x, y] = (*row, 255)

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for x in range(0, VIDEO_W, 42):
        draw.line((x, 0, x, VIDEO_H), fill=_rgba(COLORS["grid_soft"], 48), width=1)
    for y in range(0, VIDEO_H, 42):
        draw.line((0, y, VIDEO_W, y), fill=_rgba(COLORS["grid_soft"], 40), width=1)

    for x in range(0, VIDEO_W, 168):
        draw.line((x, 0, x, VIDEO_H), fill=_rgba(COLORS["grid"], 42), width=1)
    for y in range(0, VIDEO_H, 168):
        draw.line((0, y, VIDEO_W, y), fill=_rgba(COLORS["grid"], 38), width=1)

    draw.arc((-180, 560, 430, 1170), start=272, end=18, fill=_rgba(COLORS["accent"], 46), width=2)
    draw.arc((1180, -220, 1840, 420), start=156, end=292, fill=_rgba(COLORS["accent_warm"], 38), width=2)
    draw.line((0, VIDEO_H - 88, VIDEO_W, VIDEO_H - 88), fill=_rgba(COLORS["grid"], 55), width=1)
    draw.line((0, 74, VIDEO_W, 74), fill=_rgba(COLORS["grid"], 32), width=1)
    image.alpha_composite(overlay)

    _draw_soft_glow(image, center=(270, 180), radius=180, color=COLORS["accent"], strength=26)
    _draw_soft_glow(image, center=(1310, 160), radius=240, color=COLORS["accent_warm"], strength=22)
    _draw_soft_glow(image, center=(1130, 710), radius=200, color=COLORS["panel_glow"], strength=16)
    return image


def text_lines(text: str, width_chars: int) -> List[str]:
    lines: List[str] = []
    for raw in text.splitlines():
        if not raw:
            lines.append("")
            continue
        wrapped = textwrap.wrap(raw, width=width_chars, replace_whitespace=False, drop_whitespace=False)
        lines.extend(wrapped or [""])
    return lines


def build_terminal_lines(trajectory: Dict[str, Any], t_real: float, *, width_chars: int) -> List[Dict[str, str]]:
    lines: List[Dict[str, str]] = []
    active_cmd: Optional[Dict[str, Any]] = None

    for cmd in trajectory["commands"]:
        if cmd["timeline_start_s"] > t_real:
            break
        lines.append({"text": f"$ {cmd['display_cmd']}", "kind": "cmd"})
        if t_real < cmd["timeline_end_s"]:
            active_cmd = cmd
            dots = "." * (1 + (int(t_real * 3) % 3))
            lines.append({"text": f"# running{dots}", "kind": "muted"})
            break
        stdout = cmd.get("stdout", "")
        stderr = cmd.get("stderr", "")
        if stdout.strip():
            for line in text_lines(stdout.rstrip(), width_chars):
                stripped = line.strip()
                kind = "json" if stripped.startswith(("{", "}", "[", "]", "\"")) else "out"
                lines.append({"text": line, "kind": kind})
        if stderr.strip():
            for line in text_lines(stderr.rstrip(), width_chars):
                lines.append({"text": line, "kind": "err"})
        lines.append({"text": "", "kind": "out"})

    if active_cmd is None and trajectory["commands"]:
        last_cmd = trajectory["commands"][-1]
        if t_real > last_cmd["timeline_end_s"] + 0.8:
            lines.append({"text": "# trajectory complete", "kind": "success"})
    return lines[-30:]


def pick_preview_event(trajectory: Dict[str, Any], t_real: float) -> Optional[Dict[str, Any]]:
    latest = None
    for event in trajectory["preview_events"]:
        if event["timeline_ready_s"] <= t_real:
            latest = event
        else:
            break
    return latest


def progress_snapshot(trajectory: Dict[str, Any], t_real: float) -> Dict[str, Any]:
    completed_cmds = sum(1 for cmd in trajectory["commands"] if cmd["timeline_end_s"] <= t_real)
    completed_previews = sum(1 for event in trajectory["preview_events"] if event["timeline_ready_s"] <= t_real)
    active_cmd = None
    for cmd in trajectory["commands"]:
        if cmd["timeline_start_s"] <= t_real < cmd["timeline_end_s"]:
            active_cmd = cmd
            break
    return {
        "completed_cmds": completed_cmds,
        "total_cmds": len(trajectory["commands"]),
        "completed_previews": completed_previews,
        "total_previews": len(trajectory["preview_events"]),
        "active_cmd": active_cmd,
        "current_event": pick_preview_event(trajectory, t_real),
    }


def build_command_cards(trajectory: Dict[str, Any], t_real: float, *, max_cards: int = 6) -> List[Dict[str, Any]]:
    commands = trajectory.get("commands", [])
    if not commands:
        return []

    active_idx: Optional[int] = None
    completed = 0
    for idx, cmd in enumerate(commands):
        if t_real >= cmd["timeline_end_s"]:
            completed += 1
        elif cmd["timeline_start_s"] <= t_real < cmd["timeline_end_s"]:
            active_idx = idx
            break

    if active_idx is None:
        focus_idx = min(len(commands) - 1, completed)
    else:
        focus_idx = active_idx

    start = max(0, focus_idx - 2)
    start = min(start, max(0, len(commands) - max_cards))
    selected = commands[start:start + max_cards]

    cards: List[Dict[str, Any]] = []
    for idx, cmd in enumerate(selected, start=start):
        if t_real >= cmd["timeline_end_s"]:
            status = "done"
        elif cmd["timeline_start_s"] <= t_real < cmd["timeline_end_s"]:
            status = "live"
        else:
            status = "queued"

        cards.append(
            {
                "index": idx,
                "status": status,
                "label": cmd.get("label") or cmd.get("id") or f"Step {idx + 1}",
                "command": _readable_command_text(cmd.get("display_cmd", "")),
                "duration_s": float(cmd.get("duration_s") or 0.0),
            }
        )
    return cards


def draw_global_header(
    canvas: Image.Image,
    trajectory: Dict[str, Any],
    t_real: float,
    fonts: Dict[str, ImageFont.FreeTypeFont],
) -> None:
    draw = ImageDraw.Draw(canvas)
    snapshot = progress_snapshot(trajectory, t_real)
    title = trajectory.get("scenario_title", "FreeCAD Live Demo").upper()
    subtitle = trajectory.get("scenario_subtitle", "real CLI trajectory + real preview bundles")

    draw.text((34, 20), "CLI-ANYTHING / FREECAD / LIVE PREVIEW PROTOCOL", fill="#88a9c8", font=fonts["small"])
    draw.text((34, 36), title, fill=COLORS["white"], font=fonts["display"])
    draw.text((34, 68), subtitle, fill="#97abc2", font=fonts["body"])

    chip_y = 20
    chips = [
        f"T+ {t_real:05.1f}s",
        f"{snapshot['completed_cmds']:02d}/{snapshot['total_cmds']:02d} cmds",
        f"{snapshot['completed_previews']:02d}/{snapshot['total_previews']:02d} bundles",
    ]
    x = VIDEO_W - 34
    for text in reversed(chips):
        bbox = draw.textbbox((0, 0), text, font=fonts["mono_small"])
        chip_w = (bbox[2] - bbox[0]) + 26
        _draw_chip(
            canvas,
            (x - chip_w, chip_y, x, chip_y + 26),
            text=text,
            font=fonts["mono_small"],
            fill=COLORS["chip_bg"],
            text_fill=COLORS["chip_text"],
            outline=COLORS["panel_line"],
        )
        x -= chip_w + 10

    draw.line((30, 98, VIDEO_W - 30, 98), fill=_rgba(COLORS["grid"], 120), width=1)


def draw_terminal_panel(
    canvas: Image.Image,
    area: tuple[int, int, int, int],
    trajectory: Dict[str, Any],
    t_real: float,
    fonts: Dict[str, ImageFont.FreeTypeFont],
) -> None:
    x0, y0, x1, y1 = area
    draw = ImageDraw.Draw(canvas)
    snapshot = progress_snapshot(trajectory, t_real)
    _draw_panel(canvas, area, radius=30, fill=COLORS["panel"], outline=COLORS["panel_line"], accent=COLORS["accent"])

    draw.text((x0 + 24, y0 + 24), "Agent Command Stream", fill=COLORS["white"], font=fonts["title"])
    _draw_chip(
        canvas,
        (x1 - 190, y0 + 24, x1 - 24, y0 + 50),
        text="REAL COMMAND TRACE",
        font=fonts["mono_small"],
        fill=COLORS["accent_soft"],
        text_fill=COLORS["accent"],
        outline=COLORS["accent"],
    )

    active_label = snapshot["active_cmd"]["label"] if snapshot["active_cmd"] else (
        snapshot["current_event"]["step_label"] if snapshot["current_event"] else "waiting for first command"
    )
    draw.text((x0 + 24, y0 + 58), _trim_middle(active_label, 46), fill="#9bb4ce", font=fonts["body"])
    _draw_segment_bar(
        canvas,
        (x0 + 24, y0 + 90, x1 - 24, y0 + 101),
        done=snapshot["completed_cmds"],
        total=max(1, snapshot["total_cmds"]),
        fill=COLORS["accent"],
        empty=COLORS["panel_line"],
    )

    chip_y = y0 + 116
    chip_specs = [
        (f"cmd {snapshot['completed_cmds']:02d}/{snapshot['total_cmds']:02d}", COLORS["chip_bg"], COLORS["chip_text"]),
        (f"preview {snapshot['completed_previews']:02d}/{snapshot['total_previews']:02d}", COLORS["chip_bg"], COLORS["chip_text"]),
        ("poll-mode live", COLORS["accent_soft"], COLORS["accent"]),
    ]
    chip_x = x0 + 24
    for text, fill, text_fill in chip_specs:
        bbox = draw.textbbox((0, 0), text, font=fonts["mono_small"])
        chip_w = (bbox[2] - bbox[0]) + 24
        _draw_chip(canvas, (chip_x, chip_y, chip_x + chip_w, chip_y + 24), text=text, font=fonts["mono_small"], fill=fill, text_fill=text_fill, outline=COLORS["panel_line"])
        chip_x += chip_w + 10

    body_area = (x0 + 16, y0 + 154, x1 - 16, y1 - 44)
    _alpha_box(canvas, body_area, radius=22, fill=_rgba(COLORS["terminal_bg"], 246), outline=_rgba(COLORS["panel_line"], 255), width=1)

    draw.text((body_area[0] + 18, body_area[1] + 16), "Recent commands", fill=COLORS["white"], font=fonts["body"])
    draw.text((body_area[2] - 168, body_area[1] + 16), "normalized real CLI", fill=COLORS["terminal_muted"], font=fonts["small"])

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
        _alpha_box(canvas, box, radius=18, fill=_rgba(fill, 248), outline=_rgba(outline, 255), width=2 if status == "live" else 1)
        _alpha_box(canvas, (box[0] + 10, box[1] + 10, box[0] + 14, box[3] - 10), radius=2, fill=_rgba(outline, 255))
        if status == "live":
            _draw_soft_glow(canvas, center=(box[2] - 34, box[1] + 24), radius=26, color=COLORS["accent"], strength=34)

        _draw_chip(
            canvas,
            (box[0] + 22, box[1] + 12, box[0] + 74, box[1] + 34),
            text=f"{card['index'] + 1:02d}",
            font=fonts["mono_small"],
            fill=COLORS["chip_bg"],
            text_fill=COLORS["chip_text"],
            outline=COLORS["panel_line"],
        )
        _draw_chip(
            canvas,
            (box[2] - 114, box[1] + 12, box[2] - 18, box[1] + 34),
            text=status.upper(),
            font=fonts["mono_small"],
            fill=status_fill,
            text_fill=status_text,
            outline=outline,
        )
        draw.text((box[0] + 84, box[1] + 10), _trim_middle(card["label"], 38), fill=label_fill, font=fonts["body"])
        draw.text((box[2] - 182, box[3] - 26), f"{card['duration_s']:.2f}s", fill=COLORS["terminal_muted"], font=fonts["mono_small"])

        command_lines = _wrap_trimmed(card["command"], width_chars=54, max_lines=2)
        cmd_y = box[1] + 38
        for line in command_lines:
            draw.text((box[0] + 22, cmd_y), line, fill=COLORS["terminal_cmd"] if status != "queued" else "#6e8aa6", font=fonts["mono_small"])
            cmd_y += 17

        card_y += card_height + card_gap

    footer = "Real command strings from the captured trajectory, styled as an agent operations panel."
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
    _alpha_box(canvas, box, radius=18 if main else 14, fill=_rgba(COLORS["paper"], 255), outline=_rgba(COLORS["paper_line"], 255), width=2)
    if img_path and Path(img_path).is_file():
        fit = fit_image(Image.open(img_path), (max(1, x1 - x0 - 18), max(1, y1 - y0 - 18)), background=COLORS["paper"])
        canvas.paste(fit.convert("RGBA"), (x0 + 9, y0 + 9))
    _draw_chip(
        canvas,
        (x0 + 12, y0 + 12, x0 + 100, y0 + 36),
        text=label,
        font=fonts["mono_small"],
        fill="#fffaf3",
        text_fill="#5b5145",
        outline=COLORS["paper_line"],
    )
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.line((x0 + 10, y0 + 10, x0 + 30, y0 + 10), fill=_rgba(COLORS["accent_warm"], 160), width=2)
    draw.line((x0 + 10, y0 + 10, x0 + 10, y0 + 30), fill=_rgba(COLORS["accent_warm"], 160), width=2)
    draw.line((x1 - 10, y1 - 10, x1 - 30, y1 - 10), fill=_rgba(COLORS["accent"], 160), width=2)
    draw.line((x1 - 10, y1 - 10, x1 - 10, y1 - 30), fill=_rgba(COLORS["accent"], 160), width=2)
    canvas.alpha_composite(overlay)


def compose_preview_dashboard(
    event: Dict[str, Any],
    size: tuple[int, int],
    *,
    scenario: str,
    fonts: Dict[str, ImageFont.FreeTypeFont],
) -> Image.Image:
    width, height = size
    canvas = Image.new("RGBA", size, _rgba(COLORS["preview_shell"], 255))
    _alpha_box(canvas, (0, 0, width - 1, height - 1), radius=22, fill=_rgba(COLORS["preview_shell"], 255), outline=_rgba(COLORS["panel_line"], 255), width=2)

    copied = event["copied_bundle"]["artifacts"]
    primary = "front" if scenario in {"empire-state-building", "taipei-101"} else "hero"
    secondary = ["hero", "right", "top"] if primary == "front" else ["front", "top", "right"]

    main_box = (18, 18, width - 18, int(height * 0.74))
    _paste_preview_card(canvas, main_box, img_path=copied.get(primary), label=primary.upper(), fonts=fonts, main=True)

    thumb_y = int(height * 0.77)
    thumb_h = height - thumb_y - 18
    thumb_w = (width - 48) // len(secondary)
    for idx, key in enumerate(secondary):
        x0 = 18 + idx * (thumb_w + 6)
        _paste_preview_card(
            canvas,
            (x0, thumb_y, x0 + thumb_w, thumb_y + thumb_h),
            img_path=copied.get(key),
            label=key.upper(),
            fonts=fonts,
        )
    return canvas


def draw_preview_panel(
    canvas: Image.Image,
    area: tuple[int, int, int, int],
    trajectory: Dict[str, Any],
    t_real: float,
    fonts: Dict[str, ImageFont.FreeTypeFont],
) -> None:
    x0, y0, x1, y1 = area
    draw = ImageDraw.Draw(canvas)
    _draw_panel(canvas, area, radius=30, fill=COLORS["panel"], outline=COLORS["panel_line"], accent=COLORS["accent_warm"])
    draw.text((x0 + 24, y0 + 24), "Preview Monitor", fill=COLORS["white"], font=fonts["title"])
    _draw_chip(
        canvas,
        (x1 - 140, y0 + 24, x1 - 24, y0 + 50),
        text="POLL MODE",
        font=fonts["mono_small"],
        fill="#351d17",
        text_fill=COLORS["accent_warm"],
        outline=COLORS["accent_warm"],
    )
    draw.text((x0 + 24, y0 + 58), "Bundle stream from the active FreeCAD live session", fill=COLORS["preview_muted"], font=fonts["body"])

    event = pick_preview_event(trajectory, t_real)
    if event is None:
        draw.text((x0 + 28, y0 + 96), "Waiting for first live preview bundle...", fill=COLORS["preview_muted"], font=fonts["body"])
        return

    command = trajectory["commands"][event["step_index"]]
    info_w = 246
    stage_area = (x0 + 20, y0 + 96, x1 - info_w - 18, y1 - 20)
    info_area = (x1 - info_w, y0 + 96, x1 - 20, y1 - 20)
    _alpha_box(canvas, info_area, radius=20, fill=_rgba(COLORS["panel_soft"], 252), outline=_rgba(COLORS["panel_line"], 255), width=1)

    scenario = trajectory.get("scenario")
    stage = compose_preview_dashboard(
        event,
        (stage_area[2] - stage_area[0], stage_area[3] - stage_area[1]),
        scenario=scenario or "",
        fonts=fonts,
    )
    canvas.paste(stage, (stage_area[0], stage_area[1]))

    meta_lines = [
        ("STEP", event["step_label"]),
        ("BUNDLE", _trim_middle(event["copied_bundle"]["bundle_id"], 18)),
        ("CAUSE", event.get("publish_reason") or "n/a"),
        ("LATENCY", f"{event['latency_s']:.2f}s"),
        ("CMD TIME", f"{command['duration_s']:.2f}s"),
        ("STREAM", f"{event.get('sequence_index', event['bundle_count']):02d}/{len(trajectory['preview_events']):02d}"),
    ]

    draw.text((info_area[0] + 16, info_area[1] + 16), "Telemetry", fill=COLORS["white"], font=fonts["body"])
    meta_y = info_area[1] + 46
    for label, value in meta_lines:
        _draw_chip(
            canvas,
            (info_area[0] + 16, meta_y, info_area[2] - 16, meta_y + 28),
            text=label,
            font=fonts["mono_small"],
            fill=COLORS["chip_bg"],
            text_fill=COLORS["chip_text"],
            outline=COLORS["panel_line"],
        )
        draw.text((info_area[0] + 18, meta_y + 36), value, fill=COLORS["white"], font=fonts["body"])
        meta_y += 74

    step_progress = event.get("sequence_index", event["bundle_count"])
    _draw_segment_bar(
        canvas,
        (info_area[0] + 16, info_area[3] - 52, info_area[2] - 16, info_area[3] - 38),
        done=step_progress,
        total=max(1, len(trajectory["preview_events"])),
        fill=COLORS["accent_warm"],
        empty=COLORS["panel_line"],
    )
    draw.text((info_area[0] + 16, info_area[3] - 80), "Real preview artifacts only. No synthetic viewport frames.", fill=COLORS["preview_muted"], font=fonts["small"])


def compose_showcase_frame(
    trajectory: Dict[str, Any],
    showcase: Dict[str, Any],
    showcase_t: float,
    final_t_real: float,
    fonts: Dict[str, ImageFont.FreeTypeFont],
    backdrop: Image.Image,
    image_cache: Dict[int, Image.Image],
) -> Image.Image:
    sequence = showcase.get("sequence") or {}
    frames = sequence.get("frames") or []
    if not frames:
        raise RuntimeError("Showcase sequence is empty")

    total_duration = float(showcase.get("duration_s") or 0.0)
    if total_duration <= 0.0:
        last_time = float(frames[-1].get("time") or 0.0)
        fps = int(sequence.get("fps") or FPS)
        total_duration = last_time if last_time > 0 else max(0.01, (len(frames) - 1) / max(1, fps))
    clamped_t = max(0.0, min(showcase_t, total_duration))
    sequence_pos = (clamped_t / max(0.01, total_duration)) * (len(frames) - 1)
    frame_index = min(len(frames) - 1, int(round(sequence_pos)))

    stage_size = (VIDEO_W - 180, VIDEO_H - 250)

    def _stage_image(idx: int) -> Image.Image:
        cached = image_cache.get(idx)
        if cached is not None:
            return cached
        sequence_path = Path(showcase["sequence_path"]).expanduser().resolve()
        source_path = sequence_path.parent / frames[idx]["path"]
        stage = fit_image(Image.open(source_path), stage_size, background=COLORS["paper"])
        cached = stage.convert("RGBA")
        image_cache[idx] = cached
        return cached

    stage = _stage_image(frame_index)

    canvas = backdrop.copy()
    overlay = Image.new("RGBA", canvas.size, _rgba("#050913", 138))
    canvas.alpha_composite(overlay)
    draw_global_header(canvas, trajectory, final_t_real, fonts)

    panel = (54, 118, VIDEO_W - 54, VIDEO_H - 54)
    _draw_panel(canvas, panel, radius=34, fill=COLORS["panel"], outline=COLORS["panel_line"], accent=COLORS["accent_warm"])

    draw = ImageDraw.Draw(canvas)
    draw.text((panel[0] + 26, panel[1] + 24), "Final Showcase", fill=COLORS["white"], font=fonts["title"])
    _draw_chip(
        canvas,
        (panel[2] - 246, panel[1] + 22, panel[2] - 24, panel[1] + 50),
        text="TRUE FREECAD MOTION",
        font=fonts["mono_small"],
        fill="#351d17",
        text_fill=COLORS["accent_warm"],
        outline=COLORS["accent_warm"],
    )

    subtitle = showcase.get("subtitle") or "real frame-by-frame FreeCAD motion render from the final project"
    draw.text((panel[0] + 26, panel[1] + 56), subtitle, fill=COLORS["preview_muted"], font=fonts["body"])

    stage_box = (panel[0] + 26, panel[1] + 92, panel[2] - 26, panel[3] - 88)
    _alpha_box(canvas, stage_box, radius=28, fill=_rgba(COLORS["preview_shell"], 255), outline=_rgba(COLORS["panel_line"], 255), width=2)
    inset = (stage_box[0] + 16, stage_box[1] + 16)
    canvas.paste(stage, inset, stage)

    frame_label = f"frame {frame_index + 1:03d}/{len(frames):03d}"
    progress_label = f"showcase {showcase_t:04.1f}s / {total_duration:04.1f}s"
    _draw_chip(
        canvas,
        (stage_box[0] + 20, stage_box[1] + 18, stage_box[0] + 150, stage_box[1] + 42),
        text=frame_label.upper(),
        font=fonts["mono_small"],
        fill="#fffaf3",
        text_fill="#5b5145",
        outline=COLORS["paper_line"],
    )
    _draw_chip(
        canvas,
        (stage_box[2] - 190, stage_box[1] + 18, stage_box[2] - 20, stage_box[1] + 42),
        text=progress_label.upper(),
        font=fonts["mono_small"],
        fill=COLORS["chip_bg"],
        text_fill=COLORS["chip_text"],
        outline=COLORS["panel_line"],
    )

    _draw_segment_bar(
        canvas,
        (panel[0] + 26, panel[3] - 52, panel[2] - 26, panel[3] - 38),
        done=max(1, frame_index + 1),
        total=max(1, len(frames)),
        fill=COLORS["accent_warm"],
        empty=COLORS["panel_line"],
    )

    footer = "Real ending sequence: final project JSON + cli-anything-freecad motion render-video + programmatic composition"
    draw.text((panel[0] + 26, panel[3] - 74), footer, fill=COLORS["preview_muted"], font=fonts["small"])
    return canvas


def render_video(timeline_path: Path, *, output_path: Optional[Path] = None, fps: int = FPS, speed: float = 1.0, keep_frames: bool = True) -> Path:
    trajectory = load_json(timeline_path)
    run_dir = timeline_path.parent
    output_file = output_path or (run_dir / "demo.mp4")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    frames_dir = run_dir / "frames"
    ensure_clean_dir(frames_dir)

    fonts = {
        "display": load_font(DISPLAY_FONT_PATH, 38),
        "title": load_font(DISPLAY_FONT_PATH, 24),
        "body": load_font(SANS_FONT_PATH, 17),
        "small": load_font(SANS_FONT_PATH, 13),
        "mono": load_font(MONO_FONT_PATH, 15),
        "mono_small": load_font(MONO_BOLD_FONT_PATH, 12),
    }
    backdrop = build_static_backdrop()
    if trajectory.get("scenario") == "curiosity":
        showcase = generate_curiosity_true_motion_showcase(
            timeline_path,
            run_dir / "showcase-motion",
            fps=fps,
            keep_frames=True,
            motion_style="combo",
        )
    else:
        showcase = generate_curiosity_showcase_sequence(trajectory, run_dir)
    showcase_cache: Dict[int, Image.Image] = {}

    last_t = 0.0
    if trajectory["commands"]:
        last_t = max(last_t, max(cmd["timeline_end_s"] for cmd in trajectory["commands"]))
    if trajectory["preview_events"]:
        last_t = max(last_t, max(event["timeline_ready_s"] for event in trajectory["preview_events"]))
    main_duration_s = (last_t + HOLD_TAIL_S) / max(speed, 0.01)
    showcase_duration_s = float(showcase.get("duration_s", SHOWCASE_DURATION_S)) if showcase else 0.0
    duration_s = main_duration_s + showcase_duration_s
    frame_count = int(math.ceil(duration_s * fps))

    for frame_idx in range(frame_count):
        t_display = frame_idx / fps
        if showcase and t_display >= main_duration_s:
            showcase_t = t_display - main_duration_s
            image = compose_showcase_frame(
                trajectory,
                showcase,
                showcase_t,
                last_t + HOLD_TAIL_S,
                fonts,
                backdrop,
                showcase_cache,
            )
            footer_left = "REAL CLI trajectory · REAL live preview bundles · REAL FreeCAD motion ending"
        else:
            t_real = t_display * speed
            image = backdrop.copy()
            draw_global_header(image, trajectory, t_real, fonts)
            draw_terminal_panel(image, (26, 116, LEFT_W - 14, VIDEO_H - 34), trajectory, t_real, fonts)
            draw_preview_panel(image, (LEFT_W + 10, 116, VIDEO_W - 26, VIDEO_H - 34), trajectory, t_real, fonts)
            footer_left = "REAL CLI trajectory · REAL live preview bundles · programmatic composition"

        draw = ImageDraw.Draw(image)
        footer_right = _trim_middle(str(timeline_path), 56)
        draw.text((34, VIDEO_H - 26), footer_left, fill="#7891ab", font=fonts["small"])
        _draw_text_right(draw, VIDEO_W - 34, VIDEO_H - 26, footer_right, font=fonts["mono_small"], fill="#7891ab")

        image.convert("RGB").save(frames_dir / f"frame_{frame_idx:05d}.png")

    ffmpeg_cmd = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%05d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_file),
    ]
    subprocess.run(ffmpeg_cmd, cwd=run_dir, capture_output=True, text=True, timeout=600, check=True)

    if not keep_frames:
        shutil.rmtree(frames_dir)
    return output_file


def parse_args() -> argparse.Namespace:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    default_output = Path.home() / "preview-artifacts" / today / "freecad-live-video"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=["collect", "render", "run-all", "motion-showcase"],
        help="Collect a real trajectory, render a video from an existing trajectory, or do both.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory for collected artifacts, live preview state, trajectory.json, and rendered video.",
    )
    parser.add_argument(
        "--scenario",
        default="orbital-relay",
        choices=sorted(SCENARIOS),
        help="Demo scenario to collect.",
    )
    parser.add_argument(
        "--timeline",
        default=None,
        help="Existing trajectory.json path for render or motion-showcase mode.",
    )
    parser.add_argument("--fps", type=int, default=FPS, help="Output video framerate.")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier.")
    parser.add_argument("--no-frames", action="store_true", help="Delete intermediate frame PNGs after encoding.")
    parser.add_argument(
        "--motion-style",
        default="drive",
        choices=["drive", "spin", "combo"],
        help="Motion showcase style for motion-showcase mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if args.mode == "collect":
        timeline = collect_demo(output_dir, args.scenario)
        print(timeline)
        return 0

    if args.mode == "render":
        if not args.timeline:
            raise SystemExit("--timeline is required for render mode")
        output_path = render_video(
            Path(args.timeline).expanduser().resolve(),
            fps=args.fps,
            speed=args.speed,
            keep_frames=not args.no_frames,
        )
        print(output_path)
        return 0

    if args.mode == "motion-showcase":
        if not args.timeline:
            raise SystemExit("--timeline is required for motion-showcase mode")
        manifest = generate_curiosity_true_motion_showcase(
            Path(args.timeline).expanduser().resolve(),
            output_dir,
            fps=args.fps,
            keep_frames=not args.no_frames,
            motion_style=args.motion_style,
        )
        print(json.dumps(manifest, indent=2))
        return 0

    timeline = collect_demo(output_dir, args.scenario)
    output_path = render_video(
        timeline,
        fps=args.fps,
        speed=args.speed,
        keep_frames=not args.no_frames,
    )
    print(json.dumps({"timeline": str(timeline), "video": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
