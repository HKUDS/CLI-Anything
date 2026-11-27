"""Stdlib-only TOML 1.0 fallback parser for Python 3.10 (where tomllib is absent).

Shared by verify_harness.py and list_harnesses.py so Python 3.10 and Python 3.11+
interpret inline tables, dotted keys, arrays, strings, and syntax errors identically.
"""

from __future__ import annotations

import re
from typing import Any


class _TomlFlags:
    """Track explicit table declarations and frozen inline containers (mirroring tomllib._parser.Flags)."""

    FROZEN = 0
    EXPLICIT_NEST = 1

    def __init__(self) -> None:
        self._flags: dict[str, dict[str, Any]] = {}
        self._pending_flags: set[tuple[tuple[str, ...], int]] = set()

    def add_pending(self, key: tuple[str, ...], flag: int) -> None:
        self._pending_flags.add((key, flag))

    def finalize_pending(self) -> None:
        for key, flag in self._pending_flags:
            self.set(key, flag, recursive=False)
        self._pending_flags.clear()

    def unset_all(self, key: tuple[str, ...]) -> None:
        cont = self._flags
        for k in key[:-1]:
            if k not in cont:
                return
            cont = cont[k]["nested"]
        cont.pop(key[-1], None)

    def set(self, key: tuple[str, ...], flag: int, *, recursive: bool) -> None:
        cont = self._flags
        for k in key[:-1]:
            if k not in cont:
                cont[k] = {"flags": set(), "recursive_flags": set(), "nested": {}}
            cont = cont[k]["nested"]
        stem = key[-1]
        if stem not in cont:
            cont[stem] = {"flags": set(), "recursive_flags": set(), "nested": {}}
        cont[stem]["recursive_flags" if recursive else "flags"].add(flag)

    def is_(self, key: tuple[str, ...], flag: int) -> bool:
        if not key:
            return False
        cont = self._flags
        for k in key[:-1]:
            if k not in cont:
                return False
            inner = cont[k]
            if flag in inner["recursive_flags"]:
                return True
            cont = inner["nested"]
        stem = key[-1]
        if stem in cont:
            inner = cont[stem]
            return flag in inner["flags"] or flag in inner["recursive_flags"]
        return False


class _TomlFallbackParser:
    """Minimal stdlib-only TOML 1.0 parser for Python 3.10 where tomllib is absent."""

    _ESCAPES = {
        "b": "\b",
        "t": "\t",
        "n": "\n",
        "f": "\f",
        "r": "\r",
        '"': '"',
        "\\": "\\",
    }

    def __init__(self, text: str) -> None:
        cleaned = text[1:] if text.startswith("\ufeff") else text
        self.text = cleaned.replace("\r\n", "\n")
        self.n = len(self.text)
        self.pos = 0

    def parse(self) -> dict[str, Any]:
        root: dict[str, Any] = {}
        current: dict[str, Any] = root
        header: tuple[str, ...] = ()
        flags = _TomlFlags()
        while True:
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos >= self.n:
                break
            ch = self.text[self.pos]
            if ch == "[":
                flags.finalize_pending()
                if self.pos + 1 < self.n and self.text[self.pos + 1] == "[":
                    self.pos += 2
                    keys = self._parse_key_path()
                    self._skip_ws_inline()
                    if not self.text.startswith("]]", self.pos):
                        raise ValueError("Expected ']]'")
                    self.pos += 2
                    header = tuple(keys)
                    current = self._ensure_array_table(root, keys, flags)
                else:
                    self.pos += 1
                    keys = self._parse_key_path()
                    self._skip_ws_inline()
                    if self.pos >= self.n or self.text[self.pos] != "]":
                        raise ValueError("Expected ']'")
                    self.pos += 1
                    header = tuple(keys)
                    current = self._ensure_table(root, keys, flags)
                self._skip_to_eol()
            else:
                keys = self._parse_key_path()
                self._skip_ws_inline()
                if self.pos >= self.n or self.text[self.pos] != "=":
                    raise ValueError(f"Expected '=' at pos {self.pos}")
                self.pos += 1
                self._skip_ws_inline()
                val = self._parse_value()
                self._assign_path(current, keys, val, header=header, flags=flags)
                self._skip_to_eol()
        return root

    def _skip_ws_inline(self) -> None:
        while self.pos < self.n and self.text[self.pos] in {" ", "\t"}:
            self.pos += 1

    def _skip_ws_and_comments(self, *, allow_newlines: bool) -> None:
        ws = {" ", "\t", "\r", "\n"} if allow_newlines else {" ", "\t"}
        while self.pos < self.n:
            ch = self.text[self.pos]
            if ch in ws:
                self.pos += 1
            elif ch == "#":
                while self.pos < self.n and self.text[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def _skip_to_eol(self) -> None:
        self._skip_ws_inline()
        if self.pos < self.n and self.text[self.pos] == "#":
            while self.pos < self.n and self.text[self.pos] != "\n":
                self.pos += 1
        if self.pos < self.n and self.text[self.pos] not in {"\r", "\n"}:
            raise ValueError(f"Unexpected trailing content in TOML at pos {self.pos}")
        if self.pos < self.n and self.text[self.pos] == "\r":
            self.pos += 1
        if self.pos < self.n and self.text[self.pos] == "\n":
            self.pos += 1

    def _parse_key_segment(self) -> str:
        self._skip_ws_inline()
        if self.pos >= self.n:
            raise ValueError("Unexpected EOF while parsing TOML key")
        ch = self.text[self.pos]
        if ch == '"':
            return self._parse_basic_string(multiline=False)
        if ch == "'":
            return self._parse_literal_string(multiline=False)
        start = self.pos
        while self.pos < self.n and (self.text[self.pos].isalnum() or self.text[self.pos] in {"_", "-"}):
            self.pos += 1
        if self.pos == start:
            raise ValueError(f"Invalid TOML bare key at pos {self.pos}")
        return self.text[start : self.pos]

    def _parse_key_path(self) -> list[str]:
        parts = [self._parse_key_segment()]
        while True:
            self._skip_ws_inline()
            if self.pos < self.n and self.text[self.pos] == ".":
                self.pos += 1
                parts.append(self._parse_key_segment())
            else:
                break
        return parts

    def _parse_value(self) -> Any:
        self._skip_ws_inline()
        if self.pos >= self.n:
            raise ValueError("Unexpected EOF while parsing TOML value")
        if self.text.startswith('"""', self.pos):
            return self._parse_basic_string(multiline=True)
        if self.text.startswith("'''", self.pos):
            return self._parse_literal_string(multiline=True)
        ch = self.text[self.pos]
        if ch == '"':
            return self._parse_basic_string(multiline=False)
        if ch == "'":
            return self._parse_literal_string(multiline=False)
        if ch == "[":
            return self._parse_array()
        if ch == "{":
            return self._parse_inline_table()
        return self._parse_scalar()

    def _parse_basic_string(self, *, multiline: bool) -> str:
        delim = '"""' if multiline else '"'
        self.pos += len(delim)
        if multiline:
            if self.text.startswith("\r\n", self.pos):
                self.pos += 2
            elif self.text.startswith("\n", self.pos):
                self.pos += 1
        out: list[str] = []
        while self.pos < self.n:
            if multiline and self.text.startswith('"""', self.pos):
                # Allow 1 or 2 trailing quotes immediately before closing delimiter.
                run = 0
                while self.pos + run < self.n and self.text[self.pos + run] == '"':
                    run += 1
                if run > 3:
                    out.append('"' * (run - 3))
                    self.pos += run
                    return "".join(out)
                self.pos += 3
                return "".join(out)
            ch = self.text[self.pos]
            if not multiline and ch == '"':
                self.pos += 1
                return "".join(out)
            if ch == "\\":
                self.pos += 1
                if self.pos >= self.n:
                    raise ValueError("Unterminated escape")
                esc = self.text[self.pos]
                if multiline and esc in {" ", "\t", "\r", "\n"}:
                    while self.pos < self.n and self.text[self.pos] in {" ", "\t", "\r", "\n"}:
                        self.pos += 1
                    continue
                if esc in self._ESCAPES:
                    out.append(self._ESCAPES[esc])
                    self.pos += 1
                elif esc == "u":
                    hex_part = self.text[self.pos + 1 : self.pos + 5]
                    if len(hex_part) != 4:
                        raise ValueError("Invalid \\u escape in TOML string")
                    out.append(chr(int(hex_part, 16)))
                    self.pos += 5
                elif esc == "U":
                    hex_part = self.text[self.pos + 1 : self.pos + 9]
                    if len(hex_part) != 8:
                        raise ValueError("Invalid \\U escape in TOML string")
                    out.append(chr(int(hex_part, 16)))
                    self.pos += 9
                else:
                    raise ValueError(f"Invalid TOML escape sequence: \\{esc}")
            else:
                out.append(ch)
                self.pos += 1
        raise ValueError("Unterminated TOML basic string")

    def _parse_literal_string(self, *, multiline: bool) -> str:
        delim = "'''" if multiline else "'"
        self.pos += len(delim)
        if multiline:
            if self.text.startswith("\r\n", self.pos):
                self.pos += 2
            elif self.text.startswith("\n", self.pos):
                self.pos += 1
        start = self.pos
        if multiline:
            end = self.text.find("'''", self.pos)
            if end == -1:
                raise ValueError("Unterminated TOML multiline literal string")
            run = 0
            while end + run < self.n and self.text[end + run] == "'":
                run += 1
            extra = run - 3
            val = self.text[start : end + extra]
            self.pos = end + run
            return val
        end = self.text.find("'", self.pos)
        if end == -1:
            raise ValueError("Unterminated TOML literal string")
        val = self.text[start:end]
        self.pos = end + 1
        return val

    def _parse_array(self) -> list[Any]:
        self.pos += 1  # '['
        items: list[Any] = []
        while True:
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos >= self.n:
                raise ValueError("Unterminated TOML array")
            if self.text[self.pos] == "]":
                self.pos += 1
                return items
            items.append(self._parse_value())
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos < self.n and self.text[self.pos] == ",":
                self.pos += 1
            elif self.pos < self.n and self.text[self.pos] == "]":
                self.pos += 1
                return items
            else:
                raise ValueError(f"Expected ',' or ']' in TOML array at pos {self.pos}")

    def _parse_inline_table(self) -> dict[str, Any]:
        self.pos += 1  # '{'
        table: dict[str, Any] = {}
        inline_flags = _TomlFlags()
        while True:
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos >= self.n:
                raise ValueError("Unterminated TOML inline table")
            if self.text[self.pos] == "}":
                self.pos += 1
                return table
            keys = self._parse_key_path()
            self._skip_ws_inline()
            if self.pos >= self.n or self.text[self.pos] != "=":
                raise ValueError(f"Expected '=' in TOML inline table at pos {self.pos}")
            self.pos += 1
            self._skip_ws_inline()
            val = self._parse_value()
            self._assign_path(table, keys, val, header=(), flags=inline_flags, access_lists=False)
            self._skip_ws_and_comments(allow_newlines=True)
            if self.pos < self.n and self.text[self.pos] == ",":
                self.pos += 1
            elif self.pos < self.n and self.text[self.pos] == "}":
                self.pos += 1
                return table
            else:
                raise ValueError(f"Expected ',' or '}}' in TOML inline table at pos {self.pos}")

    def _parse_scalar(self) -> Any:
        start = self.pos
        while self.pos < self.n and self.text[self.pos] not in {",", "]", "}", "#", "\r", "\n"}:
            self.pos += 1
        raw = self.text[start : self.pos].strip()
        if not raw:
            raise ValueError(f"Missing TOML value at pos {start}")
        if raw == "true":
            return True
        if raw == "false":
            return False
        cleaned = raw.replace("_", "")
        try:
            return int(cleaned, 0)
        except ValueError:
            pass
        try:
            return float(cleaned)
        except ValueError:
            pass
        if re.match(r"^\d{4}-\d{2}-\d{2}(?:[Tt ]\d{2}:\d{2}|$)", raw) or re.match(r"^\d{2}:\d{2}:\d{2}", raw):
            return raw
        raise ValueError(f"Invalid TOML scalar value: {raw!r}")

    @staticmethod
    def _get_or_create_nest(
        root: dict[str, Any],
        keys: list[str],
        *,
        access_lists: bool = True,
    ) -> dict[str, Any]:
        cur: Any = root
        for k in keys:
            if k not in cur:
                cur[k] = {}
            cur = cur[k]
            if access_lists and isinstance(cur, list):
                cur = cur[-1]
            if not isinstance(cur, dict):
                raise ValueError(f"Key path {keys!r} does not resolve to a table")
        return cur

    @staticmethod
    def _ensure_table(
        root: dict[str, Any],
        keys: list[str],
        flags: _TomlFlags | None = None,
    ) -> dict[str, Any]:
        key_tuple = tuple(keys)
        if flags is not None:
            if flags.is_(key_tuple, _TomlFlags.EXPLICIT_NEST) or flags.is_(
                key_tuple, _TomlFlags.FROZEN
            ):
                raise ValueError(f"Cannot declare {key_tuple!r} twice")
            flags.set(key_tuple, _TomlFlags.EXPLICIT_NEST, recursive=False)
        return _TomlFallbackParser._get_or_create_nest(root, keys, access_lists=True)

    @staticmethod
    def _ensure_array_table(
        root: dict[str, Any],
        keys: list[str],
        flags: _TomlFlags | None = None,
    ) -> dict[str, Any]:
        key_tuple = tuple(keys)
        if flags is not None:
            if flags.is_(key_tuple, _TomlFlags.FROZEN):
                raise ValueError(f"Cannot mutate immutable namespace {key_tuple!r}")
            flags.unset_all(key_tuple)
            flags.set(key_tuple, _TomlFlags.EXPLICIT_NEST, recursive=False)
        parent = (
            _TomlFallbackParser._get_or_create_nest(root, keys[:-1], access_lists=True)
            if len(keys) > 1
            else root
        )
        last = keys[-1]
        if last not in parent:
            parent[last] = []
        if not isinstance(parent[last], list):
            raise ValueError(f"Key path {keys!r} is not an array of tables")
        entry: dict[str, Any] = {}
        parent[last].append(entry)
        return entry

    @staticmethod
    def _assign_path(
        table: dict[str, Any],
        keys: list[str],
        value: Any,
        *,
        header: tuple[str, ...] = (),
        flags: _TomlFlags | None = None,
        access_lists: bool = True,
    ) -> None:
        key_parent = keys[:-1]
        key_stem = keys[-1]
        abs_parent = header + tuple(key_parent)
        if flags is not None:
            for i in range(1, len(keys)):
                cont_key = header + tuple(keys[:i])
                if flags.is_(cont_key, _TomlFlags.EXPLICIT_NEST):
                    raise ValueError(f"Cannot redefine namespace {cont_key!r}")
                flags.add_pending(cont_key, _TomlFlags.EXPLICIT_NEST)
            if flags.is_(abs_parent, _TomlFlags.FROZEN):
                raise ValueError(f"Cannot mutate immutable namespace {abs_parent!r}")
            if not access_lists and flags.is_(header + tuple(keys), _TomlFlags.FROZEN):
                raise ValueError(f"Cannot mutate immutable namespace {header + tuple(keys)!r}")

        cur = _TomlFallbackParser._get_or_create_nest(table, key_parent, access_lists=access_lists)
        if key_stem in cur:
            raise ValueError(f"Duplicate TOML key {key_stem!r}")
        if flags is not None and isinstance(value, (dict, list)):
            flags.set(header + tuple(keys), _TomlFlags.FROZEN, recursive=True)
        cur[key_stem] = value


def loads_toml_fallback(text: str) -> dict[str, Any]:
    """Parse TOML text into Python dicts/lists without tomllib (Python 3.10 fallback)."""
    return _TomlFallbackParser(text).parse()
