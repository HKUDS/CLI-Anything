"""Auto-backup before edits, with undo support."""

import json
import shutil
import filecmp
from datetime import datetime
from pathlib import Path


BACKUP_DIR = ".live2d-backups"


def _backup_dir_for(model_path: Path) -> Path:
    return model_path.parent / BACKUP_DIR / model_path.stem


def snapshot(model_path: Path) -> Path:
    """Create a timestamped backup of a model file. Returns backup path."""
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    bdir = _backup_dir_for(model_path)
    bdir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = bdir / f"{ts}.model3.json"
    shutil.copy2(model_path, dest)

    # Also copy a snapshot of the raw JSON for diff
    return dest


def list_backups(model_path: Path) -> list[dict]:
    """List available backups for a model."""
    bdir = _backup_dir_for(model_path)
    if not bdir.exists():
        return []

    backups = []
    for f in sorted(bdir.glob("*.model3.json"), reverse=True):
        backups.append({
            "file": f.name,
            "path": str(f),
            "time": f.stem,
            "size": f.stat().st_size,
        })
    return backups


def restore(model_path: Path, backup_name: str | None = None) -> Path:
    """Restore a model from backup. If no name given, restores the latest."""
    bdir = _backup_dir_for(model_path)
    if not bdir.exists():
        raise FileNotFoundError(f"No backups found for {model_path.name}")

    if backup_name:
        src = bdir / backup_name
    else:
        backups = sorted(bdir.glob("*.model3.json"), reverse=True)
        if not backups:
            raise FileNotFoundError(f"No backups found for {model_path.name}")
        src = backups[0]

    if not src.exists():
        raise FileNotFoundError(f"Backup not found: {src}")

    shutil.copy2(src, model_path)
    return src


def auto_backup(model_path: Path) -> Path | None:
    """Auto-backup before edit. Skips only when content is unchanged."""
    bdir = _backup_dir_for(model_path)
    if bdir.exists():
        backups = sorted(bdir.glob("*.model3.json"), reverse=True)
        if backups:
            last = backups[0]
            if filecmp.cmp(model_path, last, shallow=False):
                return None

    return snapshot(model_path)
