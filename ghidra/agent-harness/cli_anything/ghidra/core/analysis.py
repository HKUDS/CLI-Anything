"""Import and analyze a binary into a Ghidra project."""

from cli_anything.ghidra.utils.ghidra_backend import GhidraBackend


def analyze(backend: GhidraBackend, binary: str, loader: str | None = None, processor: str | None = None,
            entry: str | None = None, timeout: int = 600) -> dict:
    return backend.analyze(binary, loader, processor, entry, timeout)


def info(backend: GhidraBackend, binary: str) -> dict:
    return backend.query(binary, "info")
