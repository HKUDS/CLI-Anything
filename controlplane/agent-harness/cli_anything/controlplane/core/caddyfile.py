"""Static parser for Caddyfiles.

It does not execute Caddy. It answers the questions an agent actually asks
about a reverse proxy: *which site block serves this domain*, *what upstream
does it point at*, and *is the file structurally sane*.

Only the directives that carry routing meaning are modelled (`reverse_proxy`,
`redir`, `file_server`, `root`, `respond`, `handle`/`route` containers). Every
other directive is kept verbatim under ``handlers`` so nothing is lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import re

_PLACEHOLDER_RE = re.compile(r"\{[A-Za-z0-9_.\-]+\}")
_QUOTED_RE = re.compile(r'"[^"]*"')


@dataclass
class Handler:
    """One directive inside a site block."""

    type: str
    args: list[str] = field(default_factory=list)
    children: list["Handler"] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "args": self.args}
        if self.children:
            out["children"] = [c.as_dict() for c in self.children]
        return out

    def iter_handlers(self):
        yield self
        for child in self.children:
            yield from child.iter_handlers()


@dataclass
class Site:
    addresses: list[str]
    handlers: list[Handler] = field(default_factory=list)
    line: int = 0

    @property
    def primary(self) -> str:
        return self.addresses[0] if self.addresses else ""

    def upstreams(self) -> list[str]:
        result: list[str] = []
        for handler in self.handlers:
            for node in handler.iter_handlers():
                if node.type != "reverse_proxy":
                    continue
                for arg in node.args:
                    if arg.startswith("-"):
                        continue
                    result.append(_strip_scheme(arg))
                for child in node.children:
                    if child.type == "to":
                        for arg in child.args:
                            result.append(_strip_scheme(arg))
        return result

    def kind(self) -> str:
        types = {h.type for h in self.handlers}
        if self.upstreams():
            return "reverse_proxy"
        if "redir" in types:
            return "redirect"
        if "file_server" in types:
            return "static"
        if "respond" in types:
            return "respond"
        return "other"

    def as_dict(self) -> dict[str, Any]:
        return {
            "addresses": self.addresses,
            "kind": self.kind(),
            "upstreams": self.upstreams(),
            "line": self.line,
            "handlers": [h.as_dict() for h in self.handlers],
        }


@dataclass
class Caddyfile:
    sites: list[Site] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    has_global_options: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "sites": [s.as_dict() for s in self.sites],
            "snippets": self.snippets,
            "has_global_options": self.has_global_options,
        }

    def find(self, domain: str) -> list[Site]:
        """Sites matching an exact address or a wildcard/subdomain pattern."""
        domain = domain.lower().strip().rstrip(".")
        matches: list[Site] = []
        for site in self.sites:
            for address in site.addresses:
                if _address_matches(address.lower(), domain):
                    matches.append(site)
                    break
        return matches


def _address_matches(address: str, domain: str) -> bool:
    address = address.split(" ")[0]
    if address == domain:
        return True
    if address.startswith("*."):
        suffix = address[1:]  # ".example.com"
        return domain.endswith(suffix) or domain.lstrip("*.") == suffix.lstrip(".")
    if address.startswith(":") or address.startswith("http://") or address.startswith("https://"):
        return False
    return False


def _strip_scheme(upstream: str) -> str:
    for prefix in ("https://", "http://", "h2c://", "unix/"):
        if upstream.startswith(prefix):
            return upstream[len(prefix):] if prefix != "unix/" else upstream
    return upstream


def _strip_comment(line: str) -> str:
    out = []
    in_quote = False
    for char in line:
        if char == '"':
            in_quote = not in_quote
        if char == "#" and not in_quote:
            break
        out.append(char)
    return "".join(out).rstrip()


def _tokenize(text: str) -> list[tuple[int, str, int]]:
    """Return (line_number, content, depth) tokens.

    Closing braces are emitted as their own ``"}"`` token carrying the depth of
    the block they close, so callers can see where a block ends. Caddy
    placeholders such as ``{host}`` or ``{http.request.host}`` are removed
    before brace counting so they are never mistaken for blocks.
    """
    tokens: list[tuple[int, str, int]] = []
    depth = 0

    for number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).strip()
        if not line:
            continue

        skeleton = _QUOTED_RE.sub('""', line)
        skeleton = _PLACEHOLDER_RE.sub("", skeleton)

        while skeleton.startswith("}"):
            depth = max(0, depth - 1)
            tokens.append((number, "}", depth))
            line = line[1:].strip()
            skeleton = skeleton[1:].strip()

        if not line:
            continue

        trailing = 0
        while skeleton.endswith("}"):
            trailing += 1
            skeleton = skeleton[:-1].rstrip()
            line = line[:-1].rstrip()

        tokens.append((number, line, depth))
        depth += skeleton.count("{") - trailing
        for _ in range(trailing):
            depth = max(0, depth - 1)
            tokens.append((number, "}", depth))

        depth = max(0, depth)

    return tokens


def _split_args(line: str) -> list[str]:
    """Split a directive line on whitespace, keeping quoted strings intact."""
    args: list[str] = []
    current: list[str] = []
    in_quote = False
    for char in line:
        if char == '"':
            in_quote = not in_quote
            continue
        if char.isspace() and not in_quote:
            if current:
                args.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        args.append("".join(current))
    return args


def parse(text: str) -> Caddyfile:
    """Parse Caddyfile text into sites, snippets and handlers."""
    caddyfile = Caddyfile()
    tokens = _tokenize(text)
    index = 0

    while index < len(tokens):
        number, line, depth = tokens[index]
        if depth != 0 or line == "}":
            index += 1
            continue

        header = line.rstrip("{").strip()
        opens_block = line.endswith("{")

        # Collect the body of this block: everything until the matching "}" at depth 0.
        body: list[tuple[int, str, int]] = []
        next_index = index + 1
        if opens_block:
            while next_index < len(tokens):
                n2, l2, d2 = tokens[next_index]
                if d2 == 0 and l2 == "}":
                    break
                body.append((n2, l2, d2))
                next_index += 1
            next_index += 1  # consume closing brace

        if not header:
            caddyfile.has_global_options = True
            index = next_index
            continue

        if header.startswith("(") and header.endswith(")"):
            caddyfile.snippets.append(header[1:-1])
            index = next_index
            continue

        addresses = [a for a in (part.strip() for part in header.split(",")) if a]
        handlers = _parse_body(body)
        caddyfile.sites.append(Site(addresses=addresses, handlers=handlers, line=number))
        index = next_index

    return caddyfile


def _parse_body(body: list[tuple[int, str, int]]) -> list[Handler]:
    """Turn body tokens into a handler tree using brace depth."""
    handlers: list[Handler] = []
    stack: list[Handler] = []

    for _, line, absolute_depth in body:
        depth = max(0, absolute_depth - 1)
        if line == "}":
            continue

        opens = line.endswith("{")
        text = line.rstrip("{").strip() if opens else line
        parts = _split_args(text)
        if not parts:
            continue

        handler = Handler(type=parts[0], args=parts[1:])

        if depth == 0:
            handlers.append(handler)
        elif depth - 1 < len(stack):
            stack[depth - 1].children.append(handler)
        else:
            # Malformed nesting: attach at the top rather than losing the directive.
            handlers.append(handler)

        del stack[depth:]
        if opens:
            stack.append(handler)

    return handlers


def load(path: Path) -> Caddyfile:
    return parse(path.read_text(encoding="utf-8-sig"))


def validate(caddyfile: Caddyfile) -> list[dict[str, str]]:
    """Structural checks that do not need the Caddy binary."""
    issues: list[dict[str, str]] = []

    if not caddyfile.sites:
        issues.append({"level": "error", "message": "no site blocks found"})

    seen: dict[str, int] = {}
    for site in caddyfile.sites:
        if not site.addresses:
            issues.append({
                "level": "error",
                "message": f"line {site.line}: site block without an address",
            })
        for address in site.addresses:
            if address in seen:
                issues.append({
                    "level": "warn",
                    "message": (
                        f"line {site.line}: address '{address}' already declared on "
                        f"line {seen[address]}"
                    ),
                })
            else:
                seen[address] = site.line
        if site.kind() == "reverse_proxy" and not site.upstreams():
            issues.append({
                "level": "error",
                "message": f"line {site.line}: reverse_proxy without an upstream",
            })
        has_proxy = any(
            node.type == "reverse_proxy"
            for handler in site.handlers
            for node in handler.iter_handlers()
        )
        if has_proxy and not site.upstreams():
            issues.append({
                "level": "error",
                "message": f"line {site.line}: reverse_proxy without an upstream",
            })
        for upstream in site.upstreams():
            if ":" not in upstream and not upstream.startswith("/"):
                issues.append({
                    "level": "warn",
                    "message": (
                        f"line {site.line}: upstream '{upstream}' has no port "
                        "(assumes 443/80)"
                    ),
                })

    return issues
