from __future__ import annotations

import re
from typing import Any

DEFAULT_FORBIDDEN_AI_WORDS = [
    "总而言之",
    "综上所述",
    "首先",
    "其次",
    "最后",
    "值得注意的是",
    "不得不说",
    "毋庸置疑",
    "令人印象深刻",
    "值得一提",
]

DEFAULT_FORBIDDEN_OPENINGS = [
    r"^关于.{1,20}，说一个",
    r"^今天我们来聊",
    r"^近期.{1,20}成为了热点",
]

CONTROVERSY_HINTS = [
    "但是",
    "只是",
    "其实",
    "问题",
    "真相",
    "误区",
    "不是",
    "低估",
    "高估",
]

FIRST_PERSON_VERB_HINTS = ["刚", "刚刚", "发现", "亲历", "试了", "看到", "观察到"]
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:%|倍|万|亿|k|K|w|W)?")


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text.strip()
    return parts[2].strip()


def detect_ai_words(text: str, forbidden_ai_words: list[str] | None = None) -> list[str]:
    words = forbidden_ai_words or DEFAULT_FORBIDDEN_AI_WORDS
    hits: list[str] = []
    for word in words:
        if word in text:
            hits.append(word)
    return hits


def detect_structure(text: str) -> dict[str, Any]:
    normalized = text.replace("\r\n", "\n")
    numbered_lines = re.findall(r"(?m)^\s*\d+\.\s+", normalized)
    has_numbered_list = len(numbered_lines) >= 2
    has_first_second_last = all(token in normalized for token in ("首先", "其次", "最后"))
    has_total_summary = any(token in normalized for token in ("总而言之", "综上所述", "总的来说"))
    return {
        "has_numbered_list": has_numbered_list,
        "numbered_line_count": len(numbered_lines),
        "has_first_second_last": has_first_second_last,
        "has_total_summary": has_total_summary,
    }


def split_sentences(text: str) -> list[str]:
    content = strip_frontmatter(text)
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", content)
    content = re.sub(r"^>.*$", " ", content, flags=re.MULTILINE)
    parts = re.split(r"[。！？!?\n]+", content)
    sentences = [part.strip(" \t\r\n>”“\"'") for part in parts]
    return [sentence for sentence in sentences if sentence]


def count_numbers(text: str) -> float:
    content = strip_frontmatter(text)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        return 0.0
    with_numbers = sum(1 for paragraph in paragraphs if NUMBER_PATTERN.search(paragraph))
    return with_numbers / len(paragraphs)


def analyze_opening(text: str, limit: int = 80) -> dict[str, Any]:
    content = strip_frontmatter(text)
    opening = re.sub(r"\s+", "", content)[:limit]
    has_number = bool(NUMBER_PATTERN.search(opening))
    has_controversy = any(token in opening for token in CONTROVERSY_HINTS)
    has_first_person_signal = any(token in opening for token in FIRST_PERSON_VERB_HINTS) or bool(
        re.search(r"(?<![们他她])我(?!们)", opening)
    )
    return {
        "opening": opening,
        "has_number": has_number,
        "has_controversy": has_controversy,
        "has_first_person_signal": has_first_person_signal,
    }


def match_forbidden_opening(text: str, forbidden_openings: list[str] | None = None) -> str | None:
    content = strip_frontmatter(text)
    opening = re.sub(r"\s+", "", content)[:80]
    for pattern in (forbidden_openings or DEFAULT_FORBIDDEN_OPENINGS):
        if re.search(pattern, opening):
            return pattern
    return None
