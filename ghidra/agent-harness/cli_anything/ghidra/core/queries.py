"""Read-only queries against an analyzed binary."""

from cli_anything.ghidra.utils.ghidra_backend import GhidraBackend


def list_functions(backend: GhidraBackend, binary: str, name_filter: str | None = None,
                   limit: int = 0) -> list:
    items = backend.query(binary, "functions")
    if name_filter:
        items = [f for f in items if name_filter.lower() in f["name"].lower()]
    return items[:limit] if limit else items


def decompile(backend: GhidraBackend, binary: str, target: str) -> dict:
    return backend.query(binary, "decompile", target)


def list_strings(backend: GhidraBackend, binary: str, min_length: int = 4, limit: int = 0) -> list:
    items = [s for s in backend.query(binary, "strings", str(min_length)) if s["length"] >= min_length]
    return items[:limit] if limit else items


def list_imports(backend: GhidraBackend, binary: str, limit: int = 0) -> list:
    items = backend.query(binary, "imports")
    return items[:limit] if limit else items


def xrefs(backend: GhidraBackend, binary: str, target: str) -> dict:
    return backend.query(binary, "xrefs", target)
