"""Cleanup and archive functionality"""

import os
import shutil
import tarfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def delete_model(project: Dict[str, Any], run_id: str,
                confirm: bool = True) -> bool:
    """
    Delete a model and its associated files

    Args:
        project: Project dict
        run_id: Run ID to delete
        confirm: Whether to ask for confirmation (for interactive use)

    Returns:
        True if deleted, False otherwise
    """
    # Find run
    run = next((r for r in project.get("runs", []) if r["run_id"] == run_id), None)
    if not run:
        return False

    # Support both model_dir and save_path
    model_dir = run.get("model_dir") or run.get("save_path", "")
    if not model_dir or not os.path.exists(model_dir):
        return False

    # Calculate size before deletion
    from .storage import get_directory_size
    space_to_free = get_directory_size(model_dir)

    if confirm:
        print(f"\n⚠️  About to delete: {run_id}")
        print(f"   Directory: {model_dir}")
        print(f"   Size: {space_to_free / (1024**2):.1f}MB")
        response = input("\n   Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            return False

    # Delete directory
    try:
        shutil.rmtree(model_dir)

        # Remove from project runs
        project["runs"] = [r for r in project["runs"] if r["run_id"] != run_id]

        return True
    except Exception as e:
        print(f"Error deleting {run_id}: {e}")
        return False


def archive_model(project: Dict[str, Any], run_id: str,
                 archive_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Archive a model to compressed tar.gz

    Args:
        project: Project dict
        run_id: Run ID to archive
        archive_dir: Archive directory (default: ~/.unimol-archive/)

    Returns:
        {
            "status": "archived" | "error",
            "archive_path": str,
            "original_size": int,
            "archive_size": int,
            "compression_ratio": float
        }
    """
    # Find run
    run = next((r for r in project.get("runs", []) if r["run_id"] == run_id), None)
    if not run:
        return {
            "status": "error",
            "message": f"Run not found: {run_id}"
        }

    model_dir = run.get("model_dir", "")
    if not os.path.exists(model_dir):
        return {
            "status": "error",
            "message": f"Model directory not found: {model_dir}"
        }

    # Setup archive directory
    if archive_dir is None:
        archive_dir = os.path.expanduser("~/.unimol-archive")

    os.makedirs(archive_dir, exist_ok=True)

    # Create archive filename
    project_name = project.get("metadata", {}).get("name", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d")
    archive_filename = f"{project_name}_{run_id}_{timestamp}.tar.gz"
    archive_path = os.path.join(archive_dir, archive_filename)

    # Get original size
    from .storage import get_directory_size
    original_size = get_directory_size(model_dir)

    try:
        # Create tar.gz archive
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(model_dir, arcname=run_id)

        # Get archive size
        archive_size = os.path.getsize(archive_path)
        compression_ratio = (1 - archive_size / original_size) * 100 if original_size > 0 else 0

        # Delete original after successful archive
        shutil.rmtree(model_dir)

        # Update project metadata
        run["archived"] = True
        run["archive_path"] = archive_path

        return {
            "status": "archived",
            "run_id": run_id,
            "archive_path": archive_path,
            "original_size": original_size,
            "archive_size": archive_size,
            "compression_ratio": compression_ratio
        }

    except Exception as e:
        # Clean up partial archive on error
        if os.path.exists(archive_path):
            os.remove(archive_path)

        return {
            "status": "error",
            "message": f"Failed to archive: {str(e)}"
        }


def restore_model(project: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    """
    Restore an archived model

    Args:
        project: Project dict
        run_id: Run ID to restore

    Returns:
        {
            "status": "restored" | "error",
            "model_dir": str
        }
    """
    # Find run
    run = next((r for r in project.get("runs", []) if r["run_id"] == run_id), None)
    if not run:
        return {
            "status": "error",
            "message": f"Run not found: {run_id}"
        }

    if not run.get("archived"):
        return {
            "status": "error",
            "message": f"Run {run_id} is not archived"
        }

    archive_path = run.get("archive_path")
    if not archive_path or not os.path.exists(archive_path):
        return {
            "status": "error",
            "message": f"Archive not found: {archive_path}"
        }

    # Determine restore location
    project_dir = project.get("_project_dir", ".")
    experiments_dir = os.path.join(project_dir, "experiments")
    restore_dir = os.path.join(experiments_dir, run_id)

    if os.path.exists(restore_dir):
        return {
            "status": "error",
            "message": f"Restore directory already exists: {restore_dir}"
        }

    try:
        # Extract archive
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(experiments_dir)

        # Update project metadata
        run["archived"] = False
        run["model_dir"] = restore_dir

        return {
            "status": "restored",
            "run_id": run_id,
            "model_dir": restore_dir
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to restore: {str(e)}"
        }


def batch_cleanup(project: Dict[str, Any],
                 delete_ids: List[str],
                 archive_ids: List[str] = None,
                 confirm: bool = True) -> Dict[str, Any]:
    """
    Batch delete models (archiving not supported in simplified version)

    Args:
        project: Project dict
        delete_ids: List of run IDs to delete
        archive_ids: Ignored (for backward compatibility)
        confirm: Whether to ask for confirmation

    Returns:
        {
            "deleted": [...],
            "failed": [...],
            "space_freed_mb": float
        }
    """
    if archive_ids is None:
        archive_ids = []

    if confirm:
        print(f"\n📋 Cleanup Plan:")
        print(f"   Delete: {len(delete_ids)} models")
        print(f"   Archive: {len(archive_ids)} models")
        response = input("\n   Proceed? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            return {
                "status": "cancelled",
                "deleted": [],
                "archived": [],
                "failed": []
            }

    deleted = []
    failed = []
    total_space_freed = 0

    # Delete models
    for run_id in delete_ids:
        # Find run to calculate space
        run = next((r for r in project.get("runs", []) if r["run_id"] == run_id), None)
        if run:
            model_dir = run.get("model_dir") or run.get("save_path", "")
            if model_dir and os.path.exists(model_dir):
                from .storage import get_directory_size
                space_freed = get_directory_size(model_dir)
            else:
                space_freed = 0
        else:
            space_freed = 0

        success = delete_model(project, run_id, confirm=False)
        if success:
            deleted.append(run_id)
            total_space_freed += space_freed
        else:
            failed.append(run_id)

    # Archive not supported - add to failed
    for run_id in archive_ids:
        failed.append(run_id)

    return {
        "deleted": deleted,
        "archived": [],  # Not supported
        "failed": failed,
        "space_freed_mb": total_space_freed / (1024 ** 2)
    }


def list_archives(archive_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all archived models

    Args:
        archive_dir: Archive directory (default: ~/.unimol-archive/)

    Returns:
        List of archive info dicts
    """
    if archive_dir is None:
        archive_dir = os.path.expanduser("~/.unimol-archive")

    if not os.path.exists(archive_dir):
        return []

    archives = []
    for filename in os.listdir(archive_dir):
        if filename.endswith('.tar.gz'):
            filepath = os.path.join(archive_dir, filename)
            size = os.path.getsize(filepath)
            mtime = os.path.getmtime(filepath)

            # Parse filename: project_runid_date.tar.gz
            parts = filename[:-7].split('_')  # Remove .tar.gz
            if len(parts) >= 2:
                project_name = '_'.join(parts[:-2])
                run_id = parts[-2]
                date = parts[-1]
            else:
                project_name = "unknown"
                run_id = "unknown"
                date = "unknown"

            archives.append({
                "filename": filename,
                "path": filepath,
                "project_name": project_name,
                "run_id": run_id,
                "date": date,
                "size": size,
                "modified": datetime.fromtimestamp(mtime).isoformat()
            })

    # Sort by modified time (newest first)
    archives.sort(key=lambda x: x["modified"], reverse=True)

    return archives
