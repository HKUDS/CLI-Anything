"""SlideSpec / DeckSpec — 平台中立的可消费 PPT 数据结构。

颜色用语义名 ("primary"/"secondary"/...) 而非 RGB,渲染时按 preset 解析。
坐标用 960x540 标准 16:9 画布 (像素),供 lark-slides / pptx 自行转换。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SlideElement:
    type: str
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    text: str = ""
    color: str = "dark"
    role: str = "body"
    fs: int = 18
    bold: bool = False
    align: int = 0
    bg: str | None = None
    cols: int = 0
    rows: int = 0
    gap_x: int = 0
    gap_y: int = 0
    item_w: int = 0
    item_h: int = 0
    count: int = 0
    start_y: int = 0
    gap: int = 0
    fields: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    decorations: list = field(default_factory=list)
    header: list = field(default_factory=list)
    data: Any = None
    col_w: list = field(default_factory=list)
    row_h: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in (None, "", 0, [], {})}


@dataclass
class SlideSpec:
    layout: str
    index: int = 0
    title: str = ""
    elements: list[SlideElement] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "index": self.index, "layout": self.layout, "title": self.title,
            "data": self.data, "elements": [e.to_dict() for e in self.elements],
        }


@dataclass
class DeckSpec:
    name: str
    preset: str
    talk_type: str
    slides: list[SlideSpec] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def slide_count(self) -> int:
        return len(self.slides)

    def layout_sequence(self) -> list[str]:
        return [s.layout for s in self.slides]

    def to_dict(self) -> dict:
        return {
            "name": self.name, "preset": self.preset, "talk_type": self.talk_type,
            "slide_count": self.slide_count(), "metadata": self.metadata,
            "slides": [s.to_dict() for s in self.slides],
        }

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    def write(self, path: str) -> None:
        from pathlib import Path
        Path(path).write_text(self.to_json(), encoding="utf-8")
