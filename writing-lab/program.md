# Writing AutoResearch Program

This lab treats writing quality like an optimization target.

## Loop

1. Load the current strategy from `strategy.md`.
2. Pick one benchmark topic from `benchmark_topics.md`.
3. Ask a writing agent to draft one article for that topic.
4. Run `baoyu_scorer` on the draft and use reject sampling to rewrite when style score is above threshold.
5. Ask a separate evaluation agent to score the accepted article with `evaluate.md`.
6. Compare the score against the historical best result for the same topic.
7. If the run improves the topic best score and passes the style gate, ask a separate mutation agent to change exactly one strategy field.
8. Back up the old strategy before writing the new one.
9. Append the run result to `results.tsv`.

## Hard Rules

- `evaluate.md` is a read-only rubric anchor.
- `benchmark_topics.md` is a read-only benchmark anchor.
- `strategy.md` may change by at most one top-level field per improving run.
- Writer, evaluator, and mutator must run as separate model calls.
- Drafts with `baoyu_scorer` total score above threshold must be rewritten or rejected.
- Lower score is better.
- `--dry-run` may write artifacts, but must not mutate `strategy.md`.

## Suggested Artifact Layout

- `runs/<experiment_id>/article.md`
- `runs/<experiment_id>/evaluation.json`
- `runs/<experiment_id>/mutation.json`
- `strategy_history/<timestamp>-<experiment_id>.md`
