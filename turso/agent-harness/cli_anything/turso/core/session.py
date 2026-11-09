"""Optional selection persistence. No implicit database or home-directory state."""
import json
from pathlib import Path

from .values import TursoError


def database_path(path, *, exists=True):
    if not path or path == ":memory:" or "://" in str(path) or str(path).startswith("file:"):
        raise TursoError("Select a local database file path; URLs and :memory: are unsupported")
    target = Path(path).expanduser().resolve()
    if exists and not target.is_file():
        raise TursoError(f"Database does not exist: {target}. Use db create explicitly.")
    if not exists and not target.parent.is_dir():
        raise TursoError(f"Database parent directory does not exist: {target.parent}")
    return str(target)


class SessionStore:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()

    @staticmethod
    def _decode(text):
        try:
            state = json.loads(text)
        except ValueError as exc:
            raise TursoError(f"Invalid session JSON: {exc}") from exc
        if (not isinstance(state, dict) or state.get("version") != 1
                or set(state) != {"version", "database"}
                or not (state["database"] is None or isinstance(state["database"], str))):
            raise TursoError("Invalid session schema; expected version=1 and database path/null")
        return state

    def load(self):
        if not self.path.exists():
            return None
        try:
            import fcntl
        except ImportError as exc:
            raise TursoError("Persistent sessions require Unix flock; omit --session on this host") from exc
        with self.path.open("r", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return self._decode(stream.read())["database"]

    def save(self, database):
        # Lock before reading/truncating. Never overwrite malformed existing files.
        # flock is used on supported Unix hosts; Windows selection is memory-only.
        try:
            import fcntl
        except ImportError as exc:
            raise TursoError("Persistent sessions require Unix flock; omit --session on this host") from exc
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            stream.seek(0)
            old = stream.read()
            if old:
                self._decode(old)
            stream.seek(0)
            stream.truncate()
            json.dump({"version": 1, "database": database}, stream)
            stream.write("\n")
            stream.flush()
