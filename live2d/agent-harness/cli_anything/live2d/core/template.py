"""Generate a Live2D model template/skeleton."""

import json
from pathlib import Path


def generate_template(name: str, output_dir: Path) -> Path:
    """Generate a minimal Live2D model skeleton.

    Creates:
    - <name>.model3.json (main descriptor)
    - <name>.moc3 (empty placeholder)
    - textures/ (empty dir)
    - motions/ (empty dir)
    - expressions/ (empty dir)
    - <name>.physics3.json (minimal physics)

    Returns the path to the model3.json file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Model3.json
    model3 = {
        "Version": 3,
        "FileReferences": {
            "Moc": f"{name}.moc3",
            "Textures": [f"textures/texture_00.png"],
            "Physics": f"{name}.physics3.json",
            "Pose": "",
            "UserData": "",
            "Expressions": [],
            "Motions": {
                "Idle": [
                    {
                        "File": "motions/idle_01.motion3.json",
                        "FadeInTime": 0.5,
                        "FadeOutTime": 0.5,
                    }
                ]
            },
        },
        "Groups": [
            {
                "Target": "Parameter",
                "Name": "EyeBlink",
                "Ids": "ParamEyeLOpen,ParamEyeROpen",
            },
            {
                "Target": "Parameter",
                "Name": "LipSync",
                "Ids": "ParamMouthOpenY",
            },
        ],
    }

    model3_path = output_dir / f"{name}.model3.json"
    model3_path.write_text(json.dumps(model3, indent=2, ensure_ascii=False), encoding="utf-8")

    # Minimal physics
    physics = {
        "Version": 3,
        "PhysicsSettings": [],
    }
    phys_path = output_dir / f"{name}.physics3.json"
    phys_path.write_text(json.dumps(physics, indent=2), encoding="utf-8")

    # Empty motion
    motion = {
        "Version": 3,
        "Meta": {
            "Duration": 2.0,
            "Fps": 30.0,
            "Loop": True,
            "AreBeziersRestricted": False,
            "CurveCount": 0,
            "TotalSegmentCount": 0,
            "TotalPointCount": 0,
            "UserDataCount": 0,
            "TotalUserDataSize": 0,
        },
        "Curves": [],
    }
    motions_dir = output_dir / "motions"
    motions_dir.mkdir(exist_ok=True)
    (motions_dir / "idle_01.motion3.json").write_text(
        json.dumps(motion, indent=2), encoding="utf-8"
    )

    # Empty directories
    (output_dir / "textures").mkdir(exist_ok=True)
    (output_dir / "expressions").mkdir(exist_ok=True)

    # Placeholder moc3 (empty file with just the header)
    moc3_path = output_dir / f"{name}.moc3"
    moc3_path.write_bytes(b"MOC3\x03\x00\x00\x00")

    return model3_path
