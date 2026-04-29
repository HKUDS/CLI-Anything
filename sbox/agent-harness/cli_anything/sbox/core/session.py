"""Manages CLI session state with undo/redo support."""

import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# Default session directory and file
_DEFAULT_SESSION_DIR = os.path.join( Path.home(), ".cli-anything-sbox" )
_DEFAULT_SESSION_FILE = os.path.join( _DEFAULT_SESSION_DIR, "session.json" )

# Valid operation types for record_operation
VALID_OP_TYPES = frozenset( {
    "scene_modify",
    "project_modify",
    "input_modify",
    "collision_modify",
    "file_create",
    "codegen",
} )


def _empty_session_data() -> Dict[str, Any]:
    """Return a blank session data structure."""
    now = time.time()
    return {
        "project_path": None,
        "scene_path": None,
        "modified": False,
        "undo_stack": [],
        "redo_stack": [],
        "created_at": now,
        "updated_at": now,
    }


class Session:
    """Manages CLI session state with undo/redo support.

    Session file is stored at ~/.cli-anything-sbox/session.json by default.

    Tracks:
    - Current project path
    - Current scene path
    - Operation history (undo/redo stacks)
    - Modified flag
    """

    def __init__( self, session_path: Optional[str] = None ) -> None:
        """Initialize or load an existing session.

        Args:
            session_path: Path to the session JSON file.
                          Defaults to ~/.cli-anything-sbox/session.json
        """
        self._session_path: str = session_path or _DEFAULT_SESSION_FILE
        self._data: Dict[str, Any] = _empty_session_data()

        if os.path.isfile( self._session_path ):
            self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load( self ) -> None:
        """Load session from disk.

        If the file does not exist or is malformed, resets to empty state. A
        malformed file is preserved as ``<path>.corrupt`` so the user's undo
        history is not silently destroyed.
        """
        try:
            with open( self._session_path, "r", encoding="utf-8" ) as f:
                raw = json.load( f )
            if isinstance( raw, dict ):
                merged = _empty_session_data()
                merged.update( raw )
                self._data = merged
            else:
                self._data = _empty_session_data()
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            # Preserve the malformed file before resetting so the user can
            # recover state if needed; emit a stderr warning so the reset is
            # not silent. Use a timestamp suffix so a second corruption does
            # not silently overwrite the first preserved copy.
            backup = f"{self._session_path}.corrupt.{int( time.time() )}"
            preserved = False
            try:
                if os.path.isfile( self._session_path ):
                    os.replace( self._session_path, backup )
                    preserved = True
            except OSError as backup_exc:
                # Couldn't move the file - still warn the user that the
                # session is being reset, just note the preservation failed.
                try:
                    sys.stderr.write(
                        f"warning: session file at {self._session_path} could not be "
                        f"read ({exc}) and preservation failed ({backup_exc}); "
                        f"resetting to empty state\n"
                    )
                except (OSError, ValueError):
                    pass
            else:
                try:
                    location = backup if preserved else self._session_path
                    sys.stderr.write(
                        f"warning: session file at {self._session_path} could not be read "
                        f"({exc}); preserved as {location} and reset to empty state\n"
                    )
                except (OSError, ValueError):
                    pass
            self._data = _empty_session_data()

    def save( self ) -> None:
        """Save session to disk.

        Creates parent directories if needed. Writes atomically by
        writing to a temporary file first, then renaming.
        """
        self._data["updated_at"] = time.time()

        session_dir = os.path.dirname( self._session_path )
        os.makedirs( session_dir, exist_ok=True )

        tmp_path = self._session_path + ".tmp"
        try:
            with open( tmp_path, "w", encoding="utf-8" ) as f:
                json.dump( self._data, f, indent=2, ensure_ascii=False )
                f.write( "\n" )
                f.flush()
                os.fsync( f.fileno() )

            # Atomic rename (on Windows, need to remove target first)
            if os.path.exists( self._session_path ):
                os.replace( tmp_path, self._session_path )
            else:
                os.rename( tmp_path, self._session_path )
        except OSError:
            # Clean up temp file on failure
            if os.path.exists( tmp_path ):
                try:
                    os.remove( tmp_path )
                except OSError:
                    pass
            raise

    # ------------------------------------------------------------------
    # Project and scene
    # ------------------------------------------------------------------

    def set_project( self, sbproj_path: str ) -> None:
        """Set the active project.

        Args:
            sbproj_path: Path to the .sbproj file.
        """
        self._data["project_path"] = os.path.abspath( sbproj_path )
        self._data["modified"] = True
        self.save()

    def set_scene( self, scene_path: str ) -> None:
        """Set the active scene.

        Args:
            scene_path: Path to the .scene file.
        """
        self._data["scene_path"] = os.path.abspath( scene_path )
        self._data["modified"] = True
        self.save()

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def snapshot(
        self,
        op_type: str,
        description: str,
        before_state: Optional[Any] = None,
        after_state: Optional[Any] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Alias for ``record_operation`` matching HARNESS naming convention.

        Records a snapshot of an operation onto the undo stack. See
        :meth:`record_operation` for full documentation.
        """
        self.record_operation(
            op_type=op_type,
            description=description,
            before_state=before_state,
            after_state=after_state,
            file_path=file_path,
        )

    def record_operation(
        self,
        op_type: str,
        description: str,
        before_state: Optional[Any] = None,
        after_state: Optional[Any] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Record an operation for undo/redo.

        Args:
            op_type: One of 'scene_modify', 'project_modify', 'input_modify',
                     'collision_modify', 'file_create', 'codegen'.
            description: Human-readable description of what was done.
            before_state: Serializable state before the operation (for undo).
            after_state: Serializable state after the operation (for redo).
            file_path: The file that was modified.

        Raises:
            ValueError: If op_type is not a recognised operation type.
        """
        if op_type not in VALID_OP_TYPES:
            raise ValueError(
                f"Invalid op_type '{op_type}'. "
                f"Must be one of: {', '.join( sorted( VALID_OP_TYPES ) )}"
            )

        entry: Dict[str, Any] = {
            "op_type": op_type,
            "description": description,
            "timestamp": time.time(),
            "file_path": os.path.abspath( file_path ) if file_path else None,
            "before_state": copy.deepcopy( before_state ),
            "after_state": copy.deepcopy( after_state ),
        }

        self._data["undo_stack"].append( entry )
        # Recording a new operation clears the redo stack
        self._data["redo_stack"].clear()
        self._data["modified"] = True
        self.save()

    def undo( self ) -> Optional[Dict[str, Any]]:
        """Undo the last operation.

        If the operation has a before_state and file_path, the caller is
        responsible for actually restoring the file contents. This method
        manages the stack bookkeeping.

        Returns:
            Dict describing what was undone (the operation entry), or None
            if the undo stack is empty.
        """
        undo_stack: List[Dict[str, Any]] = self._data["undo_stack"]
        if not undo_stack:
            return None

        entry = undo_stack.pop()
        self._data["redo_stack"].append( copy.deepcopy( entry ) )
        self._data["modified"] = True
        self.save()

        return {
            "undone": True,
            "op_type": entry["op_type"],
            "description": entry["description"],
            "file_path": entry.get( "file_path" ),
            "before_state": entry.get( "before_state" ),
            "after_state": entry.get( "after_state" ),
        }

    def redo( self ) -> Optional[Dict[str, Any]]:
        """Redo the last undone operation.

        Returns:
            Dict describing what was redone (the operation entry), or None
            if the redo stack is empty.
        """
        redo_stack: List[Dict[str, Any]] = self._data["redo_stack"]
        if not redo_stack:
            return None

        entry = redo_stack.pop()
        self._data["undo_stack"].append( copy.deepcopy( entry ) )
        self._data["modified"] = True
        self.save()

        return {
            "redone": True,
            "op_type": entry["op_type"],
            "description": entry["description"],
            "file_path": entry.get( "file_path" ),
            "before_state": entry.get( "before_state" ),
            "after_state": entry.get( "after_state" ),
        }

    # ------------------------------------------------------------------
    # Status and reset
    # ------------------------------------------------------------------

    def get_status( self ) -> Dict[str, Any]:
        """Return a dict with current session status.

        Returns:
            Dict with keys: project_path, scene_path, modified,
            undo_count, redo_count, created_at, updated_at.
        """
        return {
            "project_path": self._data.get( "project_path" ),
            "scene_path": self._data.get( "scene_path" ),
            "modified": self._data.get( "modified", False ),
            "undo_count": len( self._data.get( "undo_stack", [] ) ),
            "redo_count": len( self._data.get( "redo_stack", [] ) ),
            "created_at": self._data.get( "created_at" ),
            "updated_at": self._data.get( "updated_at" ),
            "session_file": self._session_path,
        }

    def clear( self ) -> None:
        """Clear session state and save to disk."""
        self._data = _empty_session_data()
        self.save()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def project_path( self ) -> Optional[str]:
        """Current project .sbproj path."""
        return self._data.get( "project_path" )

    @property
    def scene_path( self ) -> Optional[str]:
        """Current scene path."""
        return self._data.get( "scene_path" )

    @property
    def is_modified( self ) -> bool:
        """Whether there are unsaved changes."""
        return bool( self._data.get( "modified", False ) )
