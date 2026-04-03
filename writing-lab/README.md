# Writing Lab

`writing-lab/` 是一个受控的写作进化实验室：固定题目、固定评分标准、独立 writer/evaluator/mutator 调用，并在草稿阶段通过 `baoyu_scorer` 做 reject sampling 风格门控，只有分数真正变好时才微调 `strategy.md`。

## Files

- `program.md`：实验循环说明
- `strategy.md`：当前写作策略，允许演化
- `evaluate.md`：评分锚点，只读
- `benchmark_topics.md`：固定 benchmark 题目，只读
- `results.tsv`：实验日志
- `run_experiment.py`：主循环
- `scorer/`：离线宝玉风格评分器与统计基线
- `strategy_history/`：每次策略变更前的备份
- `runs/`：每轮生成的文章与评分产物

## Requirements

Python 3.10+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r writing-lab/requirements.txt
```

## Authentication

脚本会优先读取以下环境变量：

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

可选模型覆盖：

- `WRITING_LAB_OPENAI_MODEL`
- `WRITING_LAB_ANTHROPIC_MODEL`

也可以通过 CLI 显式传：

```bash
python3 writing-lab/run_experiment.py --provider openai --model gpt-4.1-mini
python3 writing-lab/run_experiment.py --provider anthropic --model claude-3-5-sonnet-latest
```

## Usage

单轮实验：

```bash
python3 writing-lab/run_experiment.py
```

连续 5 轮：

```bash
python3 writing-lab/run_experiment.py --rounds 5
```

只生成文章和评分，不改策略：

```bash
python3 writing-lab/run_experiment.py --dry-run
```

指定 benchmark 题目：

```bash
python3 writing-lab/run_experiment.py --topic-id 2
```

调整 reject sampling 门槛：

```bash
python3 writing-lab/run_experiment.py --style-threshold 60 --max-draft-attempts 4
```

## Output

每轮会：

1. 先生成草稿，并在 `runs/<experiment_id>/style-attempts/` 下保存每次草稿与对应的风格评分
2. 将 `baoyu_scorer` 总分高于阈值的草稿丢弃并重写，直到通过阈值或达到最大尝试次数
3. 在 `runs/<experiment_id>/` 下写出最终 `article.md`、`style_score.json`、`evaluation.json`，以及有需要时的 `mutation.json`
4. 在 `results.tsv` 里追加一行
5. 只有风格门控通过且跑赢该题历史最佳分数，才会先备份旧策略，再只改 `strategy.md` 的一个字段

## Notes

- `evaluate.md` 和 `benchmark_topics.md` 被视为只读锚点，脚本不会修改它们。
- `strategy.md` 每次最多只改一个顶层字段，防止策略漂移过快。
- writer、evaluator、mutator 永远是独立模型调用，不共享会话上下文。
- `baoyu_scorer` 总分越低越接近宝玉风格；默认阈值是 `60`，高于阈值会触发重写。
