from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scorer.rules import analyze_opening, count_numbers, detect_ai_words, detect_structure, split_sentences
from scorer.baoyu_scorer import BaoyuScorer


TEXT_A = """
刚发现一个很有意思的事情。OpenAI在最新的报告里披露，
他们的o3模型在数学竞赛题上的通过率已经达到了92%，
只是这个数字背后藏着一个细节——测试集只有500道题，
而且全是美国高中竞赛题的分布。
说白了，这不是在测智力，而是在测记忆力。
""".strip()

TEXT_B = """
首先，我们需要了解人工智能的发展现状。
随着技术的不断进步，AI在各个领域都取得了显著成就。
值得注意的是，这些进步不仅体现在技术层面，
更重要的是，它们正在深刻改变我们的生活方式。
综上所述，AI的未来发展前景十分广阔。
""".strip()


class RulesTest(unittest.TestCase):
    def test_detect_ai_words(self) -> None:
        hits = detect_ai_words(TEXT_B)
        self.assertIn("首先", hits)
        self.assertIn("值得注意的是", hits)
        self.assertIn("综上所述", hits)

    def test_detect_structure(self) -> None:
        result = detect_structure("首先，要看方向。其次，要看执行。最后，要看结果。")
        self.assertTrue(result["has_first_second_last"])
        self.assertFalse(result["has_numbered_list"])

    def test_split_sentences(self) -> None:
        parts = split_sentences("第一句。第二句！第三句？")
        self.assertEqual(parts, ["第一句", "第二句", "第三句"])

    def test_count_numbers_uses_paragraph_ratio(self) -> None:
        ratio = count_numbers("第一段没有数字。\n\n第二段有 42%。\n\n第三段有 3 倍。")
        self.assertAlmostEqual(ratio, 2 / 3, places=3)

    def test_analyze_opening(self) -> None:
        result = analyze_opening(TEXT_A)
        self.assertTrue(result["has_number"])
        self.assertTrue(result["has_first_person_signal"])
        self.assertTrue(result["has_controversy"])

    def test_analyze_opening_does_not_count_generic_women(self) -> None:
        result = analyze_opening(TEXT_B)
        self.assertFalse(result["has_first_person_signal"])


class ScorerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = BaoyuScorer(
            baseline={
                "avg_sentence_length": 29.73,
                "long_sentence_ratio": 0.42,
                "mid_sentence_ratio": 0.28,
                "short_sentence_ratio": 0.30,
                "number_ratio": 0.5537,
                "transition_words": {
                    "只是": 253,
                    "其实": 173,
                    "但是": 170,
                    "实际上": 89,
                    "不过": 67,
                },
                "example_words": {"像": 424, "比如": 296, "例如": 46},
                "forbidden_ai_words": [
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
                ],
                "forbidden_openings": [
                    "关于XXX，说一个",
                    "今天我们来聊",
                    "近期XXX成为了热点",
                ],
            }
        )

    def test_score_prefers_baoyu_style_text(self) -> None:
        score_a = self.scorer.score(TEXT_A)
        score_b = self.scorer.score(TEXT_B)
        self.assertLess(score_a["total_score"], 30)
        self.assertGreater(score_b["total_score"], 60)
        self.assertLess(score_a["total_score"], score_b["total_score"])

    def test_save_result_appends_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            results_path = Path(temp_dir) / "results.tsv"
            score = self.scorer.score(TEXT_A)
            self.scorer.append_result(results_path, TEXT_A, score)
            content = results_path.read_text(encoding="utf-8")
            self.assertIn("timestamp\ttext_preview", content)
            self.assertIn(str(score["total_score"]), content)


class BaselineBuilderTest(unittest.TestCase):
    def test_build_baseline_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            corpus = root / "corpus"
            corpus.mkdir()
            (corpus / "a.md").write_text("第一段有 42%。\n\n只是这件事没那么简单。", encoding="utf-8")
            (corpus / "b.md").write_text("比如说，这里没有数字。\n\n但是第二段有 3 倍。", encoding="utf-8")
            output = root / "stats_baseline.json"
            command = [
                sys.executable,
                str(ROOT / "scripts" / "build_baseline.py"),
                "--input-dir",
                str(corpus),
                "--output",
                str(output),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertTrue(output.exists(), completed.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("avg_sentence_length", data)
            self.assertIn("transition_words", data)
            self.assertGreater(data["number_ratio"], 0)


if __name__ == "__main__":
    unittest.main()
