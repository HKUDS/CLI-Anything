#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scorer.rules import count_numbers, split_sentences, strip_frontmatter

DEFAULT_INPUT_DIR = Path.home() / "Claude-Code/BAOYU_KNOWLEDGE/tweets/dotey/03-工具开发/baoyu-rag/pure_tweets"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "scorer" / "stats_baseline.json"
TRANSITION_WORDS = ["只是", "其实", "但是", "实际上", "不过"]
EXAMPLE_WORDS = ["像", "比如", "例如"]
FORBIDDEN_AI_WORDS = [
    "总而言之", "综上所述", "首先", "其次", "最后",
    "值得注意的是", "不得不说", "毋庸置疑", "令人印象深刻", "值得一提",
]
FORBIDDEN_OPENINGS = [
    "关于XXX，说一个", "今天我们来聊", "近期XXX成为了热点",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Baoyu style baseline stats from markdown corpus.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Corpus directory of markdown tweets.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Where to write stats_baseline.json.")
    return parser.parse_args()


def classify_sentence(length: int) -> str:
    if length >= 30:
        return "long"
    if length >= 15:
        return "mid"
    return "short"


def build_baseline(input_dir: Path) -> dict[str, object]:
    files = sorted(input_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No markdown files found in {input_dir}")

    sentence_lengths: list[int] = []
    sentence_buckets = Counter()
    number_ratios: list[float] = []
    transition_counts = Counter()
    example_counts = Counter()

    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        content = strip_frontmatter(text)
        for sentence in split_sentences(content):
            normalized = re.sub(r"\s+", "", sentence)
            if not normalized:
                continue
            length = len(normalized)
            sentence_lengths.append(length)
            sentence_buckets[classify_sentence(length)] += 1
        number_ratios.append(count_numbers(content))
        for word in TRANSITION_WORDS:
            transition_counts[word] += content.count(word)
        for word in EXAMPLE_WORDS:
            example_counts[word] += content.count(word)

    total_sentences = max(sum(sentence_buckets.values()), 1)
    avg_sentence_length = round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 2)
    baseline = {
        "avg_sentence_length": avg_sentence_length,
        "long_sentence_ratio": round(sentence_buckets["long"] / total_sentences, 4),
        "mid_sentence_ratio": round(sentence_buckets["mid"] / total_sentences, 4),
        "short_sentence_ratio": round(sentence_buckets["short"] / total_sentences, 4),
        "number_ratio": round(sum(number_ratios) / max(len(number_ratios), 1), 4),
        "transition_words": dict(transition_counts),
        "example_words": dict(example_counts),
        "forbidden_ai_words": FORBIDDEN_AI_WORDS,
        "forbidden_openings": FORBIDDEN_OPENINGS,
    }
    return baseline


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    baseline = build_baseline(input_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote baseline for {input_dir} -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
