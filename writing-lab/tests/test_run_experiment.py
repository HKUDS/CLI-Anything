from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'run_experiment.py'
SPEC = importlib.util.spec_from_file_location('writing_lab_run_experiment', MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeScorer:
    def __init__(self, score_map: dict[str, dict[str, object]]) -> None:
        self.score_map = score_map

    def score(self, text: str) -> dict[str, object]:
        return self.score_map[text]


class StyleGateTest(unittest.TestCase):
    def test_accepts_first_draft_when_style_score_passes(self) -> None:
        prompts: list[tuple[str, str]] = []

        def fake_model_caller(provider, model, system_prompt, user_prompt, **kwargs):
            prompts.append((system_prompt, user_prompt))
            return 'good draft'

        scorer = FakeScorer(
            {
                'good draft': {
                    'total_score': 28,
                    'ai_smell': 2,
                    'data_density': 6,
                    'rhythm': 8,
                    'transition': 7,
                    'hook': 5,
                    'notes': {},
                }
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = MODULE.generate_article_with_style_gate(
                provider='openai',
                model='fake-model',
                base_system_prompt='system',
                base_user_prompt='user',
                style_scorer=scorer,
                style_threshold=60,
                max_attempts=3,
                model_caller=fake_model_caller,
                run_dir=Path(temp_dir),
            )

        self.assertEqual(result.article, 'good draft')
        self.assertTrue(result.style_gate_passed)
        self.assertEqual(result.attempt_count, 1)
        self.assertEqual(len(prompts), 1)

    def test_rewrites_when_style_score_exceeds_threshold(self) -> None:
        prompts: list[tuple[str, str]] = []
        drafts = iter(['bad draft', 'good rewrite'])

        def fake_model_caller(provider, model, system_prompt, user_prompt, **kwargs):
            prompts.append((system_prompt, user_prompt))
            return next(drafts)

        scorer = FakeScorer(
            {
                'bad draft': {
                    'total_score': 72,
                    'ai_smell': 18,
                    'data_density': 16,
                    'rhythm': 15,
                    'transition': 12,
                    'hook': 11,
                    'notes': {'ai_smell': {'forbidden_ai_words': ['综上所述']}},
                },
                'good rewrite': {
                    'total_score': 36,
                    'ai_smell': 6,
                    'data_density': 9,
                    'rhythm': 8,
                    'transition': 7,
                    'hook': 6,
                    'notes': {'ai_smell': {'forbidden_ai_words': []}},
                },
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = MODULE.generate_article_with_style_gate(
                provider='openai',
                model='fake-model',
                base_system_prompt='system',
                base_user_prompt='user',
                style_scorer=scorer,
                style_threshold=60,
                max_attempts=3,
                model_caller=fake_model_caller,
                run_dir=Path(temp_dir),
            )

        self.assertEqual(result.article, 'good rewrite')
        self.assertTrue(result.style_gate_passed)
        self.assertEqual(result.selected_attempt, 2)
        self.assertEqual(len(prompts), 2)
        self.assertIn('上一稿宝玉风格总分 72', prompts[1][1])
        self.assertIn('综上所述', prompts[1][1])

    def test_keeps_lowest_score_attempt_when_all_rewrites_fail(self) -> None:
        drafts = iter(['draft one', 'draft two', 'draft three'])

        def fake_model_caller(provider, model, system_prompt, user_prompt, **kwargs):
            return next(drafts)

        scorer = FakeScorer(
            {
                'draft one': {
                    'total_score': 88,
                    'ai_smell': 18,
                    'data_density': 18,
                    'rhythm': 18,
                    'transition': 17,
                    'hook': 17,
                    'notes': {},
                },
                'draft two': {
                    'total_score': 64,
                    'ai_smell': 14,
                    'data_density': 13,
                    'rhythm': 13,
                    'transition': 12,
                    'hook': 12,
                    'notes': {},
                },
                'draft three': {
                    'total_score': 70,
                    'ai_smell': 15,
                    'data_density': 14,
                    'rhythm': 14,
                    'transition': 14,
                    'hook': 13,
                    'notes': {},
                },
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = MODULE.generate_article_with_style_gate(
                provider='openai',
                model='fake-model',
                base_system_prompt='system',
                base_user_prompt='user',
                style_scorer=scorer,
                style_threshold=60,
                max_attempts=3,
                model_caller=fake_model_caller,
                run_dir=Path(temp_dir),
            )

        self.assertFalse(result.style_gate_passed)
        self.assertEqual(result.article, 'draft two')
        self.assertEqual(result.style_score, 64)
        self.assertEqual(result.attempt_count, 3)
        self.assertEqual(result.selected_attempt, 2)


if __name__ == '__main__':
    unittest.main()
