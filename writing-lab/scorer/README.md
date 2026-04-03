# Baoyu Style Scorer

这是一个离线的宝玉风格评估器，用真实推文语料构建统计基线，再对输入文本做 5 维度评分。

## Build baseline

```bash
cd ~/Claude-Code/writing-lab
python3 scripts/build_baseline.py
```

可选参数：

```bash
python3 scripts/build_baseline.py \
  --input-dir ~/Claude-Code/BAOYU_KNOWLEDGE/tweets/dotey/03-工具开发/baoyu-rag/pure_tweets \
  --output scorer/stats_baseline.json
```

## CLI

```bash
cd ~/Claude-Code/writing-lab
python3 scorer/baoyu_scorer.py --text "刚发现一个很有意思的事情..."
python3 scorer/baoyu_scorer.py --file article.md
python3 scorer/baoyu_scorer.py --file article.md --save
```

## Python API

```python
from scorer.baoyu_scorer import BaoyuScorer

scorer = BaoyuScorer()
result = scorer.score(text)
print(result["total_score"])
```

## Output

评分维度：

- `ai_smell`
- `data_density`
- `rhythm`
- `transition`
- `hook`
- `total_score`

分数越低越接近宝玉风格。
