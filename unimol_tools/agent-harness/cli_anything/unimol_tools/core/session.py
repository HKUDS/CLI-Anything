"""Session management - REPL state and file locking"""

import json
import fcntl
import os
from typing import Optional, Dict, Any


def _locked_save_json(path: str, data: Dict[str, Any]):
    """
    Atomically save JSON file with file lock

    Prevents concurrent write corruption
    """
    # Create empty file if not exists
    if not os.path.exists(path):
        with open(path, 'w') as f:
            json.dump({}, f)

    with open(path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class UniMolSession:
    """Session state management"""

    def __init__(self, project_path: Optional[str] = None):
        self.project_path = project_path
        self.project = None
        self.history = []

        if project_path and os.path.exists(project_path):
            self.load_project(project_path)

    def load_project(self, path: str):
        """Load project"""
        from .project import load_project
        result = load_project(path)
        self.project = result["project"]
        self.project_path = path

    def save_project(self):
        """Save project"""
        if not self.project or not self.project_path:
            raise ValueError("No project loaded")

        from .project import save_project
        save_project(self.project_path, self.project)

    def get_project_name(self) -> str:
        """Get current project name"""
        if self.project:
            return self.project["metadata"]["name"]
        return ""

    def is_modified(self) -> bool:
        """Check if there are unsaved changes"""
        # TODO: Implement modification detection
        return False
