#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import jieba  # type: ignore
except ImportError:  # pragma: no cover
    jieba = None

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scorer.rules import (  # type: ignore
        analyze_opening,
        count_numbers,
        detect_ai_words,
        detect_structure,
        match_forbidden_opening,
        split_sentences,
        strip_frontmatter,
    )
else:
    from .rules import (
        analyze_opening,
        count_numbers,
        detect_ai_words,
        detect_structure,
        match_forbidden_opening,
        split_sentences,
        strip_frontmatter,
    )

RESULT_HEADERS = [
    "timestamp",
    "text_preview",
    "ai_smell",
    "data_density",
    "rhythm",
    "transition",
    "hook",
    "total_score",
    "notes",
]
DEFAULT_BASELINE = Path(__file__).resolve().with_name("stats_baseline.json")
DEFAULT_RESULTS = Path(__file__).resolve().parents[1] / "results.tsv"


class BaoyuScorer:
    def __init__(self, baseline: dict[str, Any] | None = None, baseline_path: str | Path | None = None):
        if baseline is not None:
            self.baseline = baseline
        else:
            baseline_file = Path(baseline_path or DEFAULT_BASELINE).expanduser().resolve()
            self.baseline = json.loads(baseline_file.read_text(encoding="utf-8"))

    def score(self, text: str) -> dict[str, Any]:
        content = strip_frontmatter(text)
        ai_smell, ai_notes = self._score_ai_smell(content)
        data_density, density_notes = self._score_data_density(content)
        rhythm, rhythm_notes = self._score_rhythm(content)
        transition, transition_notes = self._score_transition(content)
        hook, hook_notes = self._score_hook(content)
        total = ai_smell + data_density + rhythm + transition + hook
        notes = {
            "ai_smell": ai_notes,
            "data_density": density_notes,
            "rhythm": rhythm_notes,
            "transition": transition_notes,
            "hook": hook_notes,
        }
        return {
            "ai_smell": ai_smell,
            "data_density": data_density,
            "rhythm": rhythm,
            "transition": transition,
            "hook": hook,
            "total_score": total,
            "total": total,
            "notes": notes,
        }

    def append_result(self, path: str | Path, text: str, score: dict[str, Any]) -> None:
        results_path = Path(path)
        if not results_path.exists():
            results_path.parent.mkdir(parents=True, exist_ok=True)
            with results_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=RESULT_HEADERS, delimiter="\t")
                writer.writeheader()
        preview = re.sub(r"\s+", " ", strip_frontmatter(text)).strip()[:30]
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "text_preview": preview,
            "ai_smell": score["ai_smell"],
            "data_density": score["data_density"],
            "rhythm": score["rhythm"],
            "transition": score["transition"],
            "hook": score["hook"],
            "total_score": score["total_score"],
            "notes": json.dumps(score["notes"], ensure_ascii=False),
        }
        with results_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RESULT_HEADERS, delimiter="\t")
            writer.writerow(row)

    def _score_ai_smell(self, text: str) -> tuple[int, dict[str, Any]]:
        hits = detect_ai_words(text, self.baseline.get("forbidden_ai_words"))
        forbidden_opening = match_forbidden_opening(text)
        structure = detect_structure(text)
        score = min(len(hits) * 3, 20)
        if forbidden_opening:
            score += 5
        if structure["has_numbered_list"] or structure["has_first_second_last"]:
            score += 5
        score = min(score, 20)
        return score, {
            "forbidden_ai_words": hits,
            "forbidden_opening": forbidden_opening,
            "structure": structure,
        }

    def _score_data_density(self, text: str) -> tuple[int, dict[str, Any]]:
        ratio = count_numbers(text)
        baseline_ratio = float(self.baseline.get("number_ratio", 0.5537))
        distance = abs(ratio - baseline_ratio)
        score = min(20, round(distance * 20))
        if ratio == 0:
            score = min(20, score + 8)
        return score, {
            "paragraph_number_ratio": round(ratio, 4),
            "baseline_number_ratio": baseline_ratio,
            "absolute_distance": round(distance, 4),
        }

    def _score_rhythm(self, text: str) -> tuple[int, dict[str, Any]]:
        sentences = split_sentences(text)
        if not sentences:
            return 20, {"reason": "no_sentences"}
        lengths = [len(re.sub(r"\s+", "", sentence)) for sentence in sentences]
        long_ratio = sum(1 for length in lengths if length >= 30) / len(lengths)
        mid_ratio = sum(1 for length in lengths if 15 <= length < 30) / len(lengths)
        short_ratio = sum(1 for length in lengths if length < 15) / len(lengths)
        distance = math.sqrt(
            (long_ratio - float(self.baseline.get("long_sentence_ratio", 0.42))) ** 2
            + (mid_ratio - float(self.baseline.get("mid_sentence_ratio", 0.28))) ** 2
            + (short_ratio - float(self.baseline.get("short_sentence_ratio", 0.30))) ** 2
        )
        score = min(20, round(distance * 20))
        return score, {
            "sentence_count": len(sentences),
            "avg_sentence_length": round(sum(lengths) / len(lengths), 2),
            "long_ratio": round(long_ratio, 4),
            "mid_ratio": round(mid_ratio, 4),
            "short_ratio": round(short_ratio, 4),
            "distance": round(distance, 4),
        }

    def _score_transition(self, text: str) -> tuple[int, dict[str, Any]]:
        transition_words = self.baseline.get("transition_words", {})
        hits = {word: text.count(word) for word in transition_words}
        total_hits = sum(hits.values())
        score = 0
        if total_hits == 0:
            score += 10
        elif total_hits == 1:
            score += 4
        elif total_hits == 2:
            score += 1
        if "然而" in text:
            score += 5
        if hits.get("但是", 0) > 0 and hits.get("只是", 0) == 0:
            score += 3
        score = min(score, 20)
        return score, {
            "hits": hits,
            "total_hits": total_hits,
            "has_ranhou": "然而" in text,
            "uses_danshi_without_zhishi": hits.get("但是", 0) > 0 and hits.get("只是", 0) == 0,
        }

    def _score_hook(self, text: str) -> tuple[int, dict[str, Any]]:
        opening = analyze_opening(text)
        score = 0
        if not opening["has_number"]:
            score += 5
        if not opening["has_controversy"]:
            score += 5
        if not opening["has_first_person_signal"]:
            score += 5
        return min(score, 20), opening


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Baoyu writing style scorer.")
    parser.add_argument("--text", help="Text to score.")
    parser.add_argument("--file", help="Markdown file to score.")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="Path to stats_baseline.json")
    parser.add_argument("--save", action="store_true", help="Append result to writing-lab/results.tsv")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="TSV path for --save")
    return parser.parse_args()


def read_input(args: argparse.Namespace) -> str:
    if bool(args.text) == bool(args.file):
        raise ValueError("Provide exactly one of --text or --file.")
    if args.text:
        return args.text
    return Path(args.file).expanduser().read_text(encoding="utf-8")


def main() -> int:
    args = parse_args()
    text = read_input(args)
    scorer = BaoyuScorer(baseline_path=args.baseline)
    result = scorer.score(text)
    if args.save:
        scorer.append_result(args.results, text, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
