from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class RunRoundTest(unittest.TestCase):
    def _create_lab_dir(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        lab_dir = Path(temp_dir.name)
        (lab_dir / 'program.md').write_text('program', encoding='utf-8')
        (lab_dir / 'evaluate.md').write_text('evaluate rubric', encoding='utf-8')
        (lab_dir / 'benchmark_topics.md').write_text('1. "Test topic"\n', encoding='utf-8')
        (lab_dir / 'strategy.md').write_text(
            '\n'.join(
                [
                    'hook_style: direct',
                    'structure: narrative',
                    'tone: sharp',
                    'forbidden_words:',
                    '  - synergy',
                    'signature_move: concrete detail',
                    'max_ai_smell_score: 3',
                    '',
                ]
            ),
            encoding='utf-8',
        )
        (lab_dir / 'results.tsv').write_text(
            '\t'.join(MODULE.RESULT_HEADERS) + '\n',
            encoding='utf-8',
        )
        scorer_dir = lab_dir / 'scorer'
        scorer_dir.mkdir(parents=True)
        (scorer_dir / 'baoyu_scorer.py').write_text('# stub\n', encoding='utf-8')
        (scorer_dir / 'stats_baseline.json').write_text('{}\n', encoding='utf-8')
        return lab_dir

    def test_run_round_dry_run_keeps_strategy_unchanged_and_logs_result(self) -> None:
        lab_dir = self._create_lab_dir()
        original_strategy = (lab_dir / 'strategy.md').read_text(encoding='utf-8')
        topics = MODULE.load_topics(lab_dir / 'benchmark_topics.md')
        style_gate = MODULE.StyleGateResult(
            article='draft body',
            style_score=28,
            style_payload={'total_score': 28},
            style_gate_passed=True,
            attempt_count=1,
            selected_attempt=1,
        )
        evaluation_json = json.dumps(
            {
                'ai_smell': 0,
                'hook': 1,
                'density': 1,
                'perspective': 0,
                'total_score': 2,
                'summary': 'solid draft',
                'improvement_hypothesis': 'tighten the hook',
            },
            ensure_ascii=False,
        )

        with mock.patch.object(MODULE, 'generate_article_with_style_gate', return_value=style_gate), mock.patch.object(
            MODULE, 'call_model', return_value=evaluation_json
        ):
            result = MODULE.run_round(
                lab_dir=lab_dir,
                provider='openai',
                models={'writer': 'w', 'evaluator': 'e', 'mutator': 'm'},
                topics=topics,
                requested_topic_id='1',
                rng=MODULE.random.Random(7),
                dry_run=True,
                style_threshold=60,
                max_draft_attempts=3,
            )

        self.assertEqual(result['strategy_change'], 'dry-run')
        self.assertTrue(result['improved'])
        self.assertEqual((lab_dir / 'strategy.md').read_text(encoding='utf-8'), original_strategy)
        self.assertTrue(result['article_path'].exists())
        self.assertTrue(result['evaluation_path'].exists())
        rows = (lab_dir / 'results.tsv').read_text(encoding='utf-8').strip().splitlines()
        self.assertEqual(len(rows), 2)
        self.assertIn('dry-run', rows[1])

    def test_run_round_mutates_one_field_and_writes_backup_when_improved(self) -> None:
        lab_dir = self._create_lab_dir()
        topics = MODULE.load_topics(lab_dir / 'benchmark_topics.md')
        style_gate = MODULE.StyleGateResult(
            article='draft body',
            style_score=24,
            style_payload={'total_score': 24},
            style_gate_passed=True,
            attempt_count=1,
            selected_attempt=1,
        )
        evaluation_json = json.dumps(
            {
                'ai_smell': 0,
                'hook': 0,
                'density': 1,
                'perspective': 0,
                'total_score': 1,
                'summary': 'better draft',
                'improvement_hypothesis': 'sharpen tone',
            },
            ensure_ascii=False,
        )
        mutation_json = json.dumps(
            {
                'field': 'tone',
                'new_value': 'colder',
                'reason': 'Lower score came from a more opinionated tone.',
            },
            ensure_ascii=False,
        )

        with mock.patch.object(MODULE, 'generate_article_with_style_gate', return_value=style_gate), mock.patch.object(
            MODULE, 'call_model', side_effect=[evaluation_json, mutation_json]
        ):
            result = MODULE.run_round(
                lab_dir=lab_dir,
                provider='openai',
                models={'writer': 'w', 'evaluator': 'e', 'mutator': 'm'},
                topics=topics,
                requested_topic_id='1',
                rng=MODULE.random.Random(9),
                dry_run=False,
                style_threshold=60,
                max_draft_attempts=3,
            )

        mutated_strategy = (lab_dir / 'strategy.md').read_text(encoding='utf-8')
        self.assertIn('tone: colder', mutated_strategy)
        self.assertNotIn('tone: sharp', mutated_strategy)
        self.assertIsNotNone(result['backup_path'])
        assert result['backup_path'] is not None
        self.assertTrue(result['backup_path'].exists())
        self.assertTrue((result['mutation_path']).exists())
        mutation_payload = json.loads((result['mutation_path']).read_text(encoding='utf-8'))
        self.assertEqual(mutation_payload['field'], 'tone')
        self.assertEqual(mutation_payload['new_value'], 'colder')
        self.assertEqual(result['strategy_change'], 'tone: "sharp" -> "colder"')


if __name__ == '__main__':
    unittest.main()
