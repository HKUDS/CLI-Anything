#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

LAB_ROOT = Path(__file__).resolve().parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from scorer.baoyu_scorer import BaoyuScorer


RESULT_HEADERS = [
    "experiment_id",
    "timestamp",
    "topic_id",
    "strategy_hash",
    "style_score",
    "style_gate_passed",
    "style_attempts",
    "ai_smell",
    "hook",
    "density",
    "perspective",
    "total_score",
    "strategy_change",
]

STRATEGY_KEYS = [
    "hook_style",
    "structure",
    "tone",
    "forbidden_words",
    "signature_move",
    "max_ai_smell_score",
]

SCORE_LIMITS = {
    "ai_smell": 4,
    "hook": 2,
    "density": 2,
    "perspective": 2,
}

OPENAI_DEFAULT_MODEL = os.getenv("WRITING_LAB_OPENAI_MODEL", "gpt-4.1-mini")
ANTHROPIC_DEFAULT_MODEL = os.getenv(
    "WRITING_LAB_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"
)
DEFAULT_STYLE_THRESHOLD = int(os.getenv("WRITING_LAB_STYLE_THRESHOLD", "60"))
DEFAULT_MAX_DRAFT_ATTEMPTS = int(os.getenv("WRITING_LAB_MAX_DRAFT_ATTEMPTS", "3"))
STYLE_COMPONENT_KEYS = ["ai_smell", "data_density", "rhythm", "transition", "hook"]


@dataclass(frozen=True)
class Topic:
    id: str
    title: str


@dataclass(frozen=True)
class EvaluationResult:
    ai_smell: int
    hook: int
    density: int
    perspective: int
    total_score: int
    summary: str
    improvement_hypothesis: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class MutationProposal:
    field: str
    new_value: Any
    reason: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class StyleGateResult:
    article: str
    style_score: int
    style_payload: dict[str, Any]
    style_gate_passed: bool
    attempt_count: int
    selected_attempt: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the writing auto-research experiment loop."
    )
    parser.add_argument("--rounds", type=int, default=1, help="Number of rounds to run.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and score articles without mutating strategy.md.",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "openai", "anthropic"],
        default="auto",
        help="Model provider to use for all agent calls.",
    )
    parser.add_argument("--model", help="Model name to use for all roles.")
    parser.add_argument("--writer-model", help="Optional writer model override.")
    parser.add_argument("--evaluator-model", help="Optional evaluator model override.")
    parser.add_argument("--mutator-model", help="Optional mutator model override.")
    parser.add_argument(
        "--style-threshold",
        type=int,
        default=DEFAULT_STYLE_THRESHOLD,
        help="Maximum acceptable Baoyu style score before rewrite/reject sampling.",
    )
    parser.add_argument(
        "--max-draft-attempts",
        type=int,
        default=DEFAULT_MAX_DRAFT_ATTEMPTS,
        help="Maximum number of draft attempts before keeping the lowest style score draft.",
    )
    parser.add_argument(
        "--topic-id",
        help="Optional benchmark topic id. If omitted, each round picks randomly.",
    )
    parser.add_argument(
        "--seed", type=int, help="Optional random seed for reproducible topic sampling."
    )
    parser.add_argument(
        "--lab-dir",
        default=str(Path(__file__).resolve().parent),
        help="Path to the writing-lab directory.",
    )
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_timestamp(value: datetime | None = None) -> str:
    resolved = value or utc_now()
    return resolved.isoformat(timespec="seconds").replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_strategy(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"Strategy file must contain a YAML object: {path}")
    missing = [key for key in STRATEGY_KEYS if key not in payload]
    if missing:
        raise ValueError(f"Strategy file is missing keys: {', '.join(missing)}")
    return payload


def save_strategy(path: Path, strategy: dict[str, Any]) -> None:
    write_text(path, yaml.safe_dump(strategy, sort_keys=False, allow_unicode=True))


def strategy_hash(strategy: dict[str, Any]) -> str:
    stable_yaml = yaml.safe_dump(strategy, sort_keys=True, allow_unicode=True)
    return hashlib.sha256(stable_yaml.encode("utf-8")).hexdigest()[:12]


def backup_strategy(strategy_path: Path, history_dir: Path, experiment_id: str) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    backup_path = history_dir / f"{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{experiment_id}.md"
    shutil.copy2(strategy_path, backup_path)
    return backup_path


def load_topics(path: Path) -> list[Topic]:
    topics: list[Topic] = []
    pattern = re.compile(r'^\s*(\d+)\.\s+"(.+)"\s*$')
    for line in read_text(path).splitlines():
        match = pattern.match(line)
        if match:
            topics.append(Topic(id=match.group(1), title=match.group(2)))
    if not topics:
        raise ValueError(f"No benchmark topics found in {path}")
    return topics


def ensure_results_file(path: Path) -> None:
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            existing_headers = next(reader, None)
        if existing_headers == RESULT_HEADERS:
            return
        rows: list[dict[str, str]] = []
        if existing_headers:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                rows = list(reader)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RESULT_HEADERS, delimiter="\t")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in RESULT_HEADERS})
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_HEADERS, delimiter="\t")
        writer.writeheader()


def load_topic_best_scores(path: Path) -> dict[str, int]:
    ensure_results_file(path)
    best_scores: dict[str, int] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            try:
                total_score = int(row["total_score"])
            except (KeyError, TypeError, ValueError):
                continue
            topic_id = row.get("topic_id")
            if not topic_id:
                continue
            current_best = best_scores.get(topic_id)
            if current_best is None or total_score < current_best:
                best_scores[topic_id] = total_score
    return best_scores


def append_result(path: Path, row: dict[str, Any]) -> None:
    ensure_results_file(path)
    serialized = {key: row.get(key, "") for key in RESULT_HEADERS}
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_HEADERS, delimiter="\t")
        writer.writerow(serialized)


def choose_topic(topics: list[Topic], requested_topic_id: str | None, rng: random.Random) -> Topic:
    if requested_topic_id:
        for topic in topics:
            if topic.id == requested_topic_id:
                return topic
        valid = ", ".join(topic.id for topic in topics)
        raise ValueError(f"Unknown topic id {requested_topic_id}. Valid ids: {valid}")
    return rng.choice(topics)


def infer_provider(provider_flag: str) -> str:
    if provider_flag != "auto":
        return provider_flag
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError(
        "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
        "or pass --provider explicitly with valid credentials."
    )


def resolve_models(provider: str, args: argparse.Namespace) -> dict[str, str]:
    default_model = (
        OPENAI_DEFAULT_MODEL if provider == "openai" else ANTHROPIC_DEFAULT_MODEL
    )
    shared = args.model or default_model
    return {
        "writer": args.writer_model or shared,
        "evaluator": args.evaluator_model or shared,
        "mutator": args.mutator_model or shared,
    }


def extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    collected: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str) and text.strip():
                collected.append(text.strip())
    joined = "\n".join(collected).strip()
    if joined:
        return joined
    raise RuntimeError("Model response did not contain text output.")


def extract_anthropic_text(response: Any) -> str:
    collected: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            collected.append(text.strip())
    joined = "\n".join(collected).strip()
    if joined:
        return joined
    raise RuntimeError("Anthropic response did not contain text output.")


def call_model(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float,
    max_output_tokens: int,
) -> str:
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        )
        return extract_response_text(response)

    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model,
            system=system_prompt,
            temperature=temperature,
            max_tokens=max_output_tokens,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return extract_anthropic_text(response)

    raise ValueError(f"Unsupported provider: {provider}")


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    return cleaned.strip()


def parse_json_object(text: str) -> dict[str, Any]:
    candidate = strip_code_fences(text)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.S)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object.")
    return payload


def build_writer_prompts(
    program_text: str,
    strategy: dict[str, Any],
    evaluate_text: str,
    topic: Topic,
) -> tuple[str, str]:
    system_prompt = (
        "You are the Writing Agent inside a writing optimization lab. "
        "Write one Chinese article that follows the current strategy as closely as possible."
    )
    strategy_yaml = yaml.safe_dump(strategy, sort_keys=False, allow_unicode=True)
    user_prompt = f"""实验说明：
{program_text}

当前策略（YAML）：
```yaml
{strategy_yaml.strip()}
```

评分锚点（供你参考，但不要在文章中提到它）：
{evaluate_text}

本轮 benchmark 题目：
[{topic.id}] {topic.title}

输出要求：
- 写一篇中文文章，约 800-1200 字
- 用 Markdown 输出，第一行是标题
- 以自然段为主，不要写成提纲
- 必须遵守 forbidden_words 和 signature_move
- 不要解释策略，不要输出评分，不要输出额外前后缀

只返回文章正文。"""
    return system_prompt, user_prompt


def build_evaluator_prompts(evaluate_text: str, topic: Topic, article: str) -> tuple[str, str]:
    system_prompt = (
        "You are the Evaluation Agent in a writing lab. "
        "Score the article strictly against the rubric and return JSON only."
    )
    user_prompt = f"""评分标准（只读锚点）：
{evaluate_text}

本轮题目：
[{topic.id}] {topic.title}

待评分文章：
<<<ARTICLE
{article}
ARTICLE

请只返回 JSON，结构如下：
{{
  "ai_smell": 0,
  "hook": 0,
  "density": 0,
  "perspective": 0,
  "total_score": 0,
  "summary": "一句话总结",
  "improvement_hypothesis": "下一轮最值得尝试的微调方向",
  "notes": {{
    "ai_smell": "说明",
    "hook": "说明",
    "density": "说明",
    "perspective": "说明"
  }}
}}

规则：
- 分数必须是整数
- ai_smell 范围 0-4，其余三项范围 0-2
- total_score 必须等于四项之和
- 分数越低越好
- 不要输出 Markdown 或额外解释"""
    return system_prompt, user_prompt


def build_mutator_prompts(
    strategy: dict[str, Any],
    topic: Topic,
    article: str,
    evaluation: EvaluationResult,
    previous_best: int | None,
) -> tuple[str, str]:
    system_prompt = (
        "You are the Strategy Mutation Agent in a writing lab. "
        "Propose exactly one valid strategy field change and return JSON only."
    )
    strategy_yaml = yaml.safe_dump(strategy, sort_keys=False, allow_unicode=True)
    evaluation_json = json.dumps(evaluation.raw_payload, ensure_ascii=False, indent=2)
    best_label = "none" if previous_best is None else str(previous_best)
    user_prompt = f"""当前策略：
```yaml
{strategy_yaml.strip()}
```

本轮题目：
[{topic.id}] {topic.title}

本轮文章：
<<<ARTICLE
{article}
ARTICLE

本轮评分：
{evaluation_json}

该题历史最佳总分（本轮之前）：
{best_label}

请基于“为什么这次更好”提出一个最小有效改动。

硬规则：
- 只能改一个顶层字段
- 允许字段：{", ".join(STRATEGY_KEYS)}
- 新值必须保持同类型
- 不要修改 evaluate.md 或 benchmark_topics.md
- 不要一次改多个字段

只返回 JSON：
{{
  "field": "hook_style",
  "new_value": "新的值",
  "reason": "一句话解释"
}}"""
    return system_prompt, user_prompt


def extract_style_total(style_payload: dict[str, Any]) -> int:
    raw_total = style_payload.get("total_score", style_payload.get("total"))
    if not isinstance(raw_total, int):
        raise ValueError("Style scorer payload must include integer total_score.")
    return raw_total


def build_style_retry_prompt(
    base_user_prompt: str,
    style_payload: dict[str, Any],
    *,
    style_threshold: int,
) -> str:
    style_total = extract_style_total(style_payload)
    ranked_components = sorted(
        (
            (key, int(style_payload.get(key, 0)))
            for key in STYLE_COMPONENT_KEYS
            if isinstance(style_payload.get(key), int)
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    top_penalties = [f"{key}={value}" for key, value in ranked_components[:3]]
    ai_notes = style_payload.get("notes", {}).get("ai_smell", {})
    forbidden_ai_words = ai_notes.get("forbidden_ai_words", [])
    forbidden_line = (
        f"\n- 命中的 AI 味词：{', '.join(forbidden_ai_words)}"
        if forbidden_ai_words
        else ""
    )
    return (
        f"{base_user_prompt}\n\n"
        f"上一稿宝玉风格总分 {style_total}，未达到阈值 <= {style_threshold}。\n"
        "请完全重写，不要局部修补，目标是把宝玉风格总分压到阈值以内。\n"
        f"- 重点惩罚项：{', '.join(top_penalties) if top_penalties else '无'}"
        f"{forbidden_line}\n"
        "- 优先减少 AI 味套话、增强数字细节、增加真实判断和转折。\n"
        "- 保留原题目与核心观点，但用更像宝玉的表达重写。\n"
        "- 只返回新的完整文章正文。"
    )


def write_style_attempt(
    style_attempts_dir: Path,
    attempt_number: int,
    article: str,
    style_payload: dict[str, Any],
) -> None:
    style_attempts_dir.mkdir(parents=True, exist_ok=True)
    attempt_stub = style_attempts_dir / f"attempt-{attempt_number:02d}"
    write_text(
        attempt_stub.with_suffix(".md"),
        article + ("\n" if not article.endswith("\n") else ""),
    )
    write_json(attempt_stub.with_suffix(".json"), style_payload)


def generate_article_with_style_gate(
    *,
    provider: str,
    model: str,
    base_system_prompt: str,
    base_user_prompt: str,
    style_scorer: Any,
    style_threshold: int,
    max_attempts: int,
    model_caller: Any = call_model,
    run_dir: Path | None = None,
) -> StyleGateResult:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    best_attempt: dict[str, Any] | None = None
    user_prompt = base_user_prompt
    style_attempts_dir = run_dir / "style-attempts" if run_dir else None

    for attempt_number in range(1, max_attempts + 1):
        article = model_caller(
            provider,
            model,
            base_system_prompt,
            user_prompt,
            temperature=0.7,
            max_output_tokens=3200,
        ).strip()
        style_payload = style_scorer.score(article)
        style_total = extract_style_total(style_payload)

        if style_attempts_dir:
            write_style_attempt(style_attempts_dir, attempt_number, article, style_payload)

        attempt_record = {
            "article": article,
            "style_score": style_total,
            "style_payload": style_payload,
            "attempt_number": attempt_number,
        }
        if best_attempt is None or style_total < int(best_attempt["style_score"]):
            best_attempt = attempt_record

        if style_total <= style_threshold:
            return StyleGateResult(
                article=article,
                style_score=style_total,
                style_payload=style_payload,
                style_gate_passed=True,
                attempt_count=attempt_number,
                selected_attempt=attempt_number,
            )

        user_prompt = build_style_retry_prompt(
            base_user_prompt,
            style_payload,
            style_threshold=style_threshold,
        )

    assert best_attempt is not None
    return StyleGateResult(
        article=str(best_attempt["article"]),
        style_score=int(best_attempt["style_score"]),
        style_payload=dict(best_attempt["style_payload"]),
        style_gate_passed=False,
        attempt_count=max_attempts,
        selected_attempt=int(best_attempt["attempt_number"]),
    )


def parse_evaluation(text: str) -> EvaluationResult:
    payload = parse_json_object(text)
    scores: dict[str, int] = {}
    for key, max_value in SCORE_LIMITS.items():
        raw_value = payload.get(key)
        if not isinstance(raw_value, int):
            raise ValueError(f"Evaluation field {key} must be an integer.")
        if raw_value < 0 or raw_value > max_value:
            raise ValueError(f"Evaluation field {key} must be between 0 and {max_value}.")
        scores[key] = raw_value
    expected_total = sum(scores.values())
    raw_total = payload.get("total_score")
    if not isinstance(raw_total, int) or raw_total != expected_total:
        raise ValueError(
            f"Evaluation total_score must equal sum of component scores ({expected_total})."
        )
    summary = payload.get("summary")
    hypothesis = payload.get("improvement_hypothesis")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Evaluation summary must be a non-empty string.")
    if not isinstance(hypothesis, str) or not hypothesis.strip():
        raise ValueError("Evaluation improvement_hypothesis must be a non-empty string.")
    return EvaluationResult(
        ai_smell=scores["ai_smell"],
        hook=scores["hook"],
        density=scores["density"],
        perspective=scores["perspective"],
        total_score=raw_total,
        summary=summary.strip(),
        improvement_hypothesis=hypothesis.strip(),
        raw_payload=payload,
    )


def coerce_mutation_value(field: str, proposed_value: Any, current_value: Any) -> Any:
    if isinstance(current_value, int) and not isinstance(current_value, bool):
        if isinstance(proposed_value, int):
            return proposed_value
        if isinstance(proposed_value, str) and proposed_value.strip().isdigit():
            return int(proposed_value.strip())
        raise ValueError(f"Mutation for {field} must stay an integer.")
    if isinstance(current_value, list):
        if not isinstance(proposed_value, list) or not all(
            isinstance(item, str) and item.strip() for item in proposed_value
        ):
            raise ValueError(f"Mutation for {field} must stay a non-empty string list.")
        return [item.strip() for item in proposed_value]
    if isinstance(current_value, str):
        if not isinstance(proposed_value, str) or not proposed_value.strip():
            raise ValueError(f"Mutation for {field} must stay a non-empty string.")
        return proposed_value.strip()
    raise ValueError(f"Unsupported strategy field type for {field}.")


def parse_mutation(text: str, strategy: dict[str, Any]) -> MutationProposal:
    payload = parse_json_object(text)
    field = payload.get("field")
    if field not in STRATEGY_KEYS:
        raise ValueError(f"Mutation field must be one of: {', '.join(STRATEGY_KEYS)}")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Mutation reason must be a non-empty string.")
    new_value = coerce_mutation_value(field, payload.get("new_value"), strategy[field])
    if new_value == strategy[field]:
        raise ValueError("Mutation must actually change the chosen field.")
    return MutationProposal(
        field=field,
        new_value=new_value,
        reason=reason.strip(),
        raw_payload=payload,
    )


def apply_mutation(
    strategy: dict[str, Any], proposal: MutationProposal
) -> tuple[dict[str, Any], str]:
    updated = dict(strategy)
    previous_value = updated[proposal.field]
    updated[proposal.field] = proposal.new_value
    changed_fields = [
        key for key in STRATEGY_KEYS if updated.get(key) != strategy.get(key)
    ]
    if changed_fields != [proposal.field]:
        raise ValueError(
            "Strategy mutation must change exactly one top-level field. "
            f"Changed: {', '.join(changed_fields) or 'none'}"
        )
    change_label = (
        f"{proposal.field}: {json.dumps(previous_value, ensure_ascii=False)} -> "
        f"{json.dumps(proposal.new_value, ensure_ascii=False)}"
    )
    return updated, change_label


def select_topic_best_label(previous_best: int | None) -> str:
    return "baseline" if previous_best is None else str(previous_best)


def run_round(
    *,
    lab_dir: Path,
    provider: str,
    models: dict[str, str],
    topics: list[Topic],
    requested_topic_id: str | None,
    rng: random.Random,
    dry_run: bool,
    style_threshold: int,
    max_draft_attempts: int,
) -> dict[str, Any]:
    strategy_path = lab_dir / "strategy.md"
    evaluate_path = lab_dir / "evaluate.md"
    program_path = lab_dir / "program.md"
    results_path = lab_dir / "results.tsv"
    history_dir = lab_dir / "strategy_history"
    runs_dir = lab_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    strategy = load_strategy(strategy_path)
    strategy_digest = strategy_hash(strategy)
    program_text = read_text(program_path)
    evaluate_text = read_text(evaluate_path)
    topic = choose_topic(topics, requested_topic_id, rng)
    historical_best = load_topic_best_scores(results_path)
    previous_best = historical_best.get(topic.id)

    experiment_id = f"{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    run_dir = runs_dir / experiment_id
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "metadata.json",
        {
            "experiment_id": experiment_id,
            "timestamp": iso_timestamp(),
            "provider": provider,
            "models": models,
            "topic": {"id": topic.id, "title": topic.title},
            "strategy_hash": strategy_digest,
            "previous_best_total_score": previous_best,
            "dry_run": dry_run,
            "style_threshold": style_threshold,
            "max_draft_attempts": max_draft_attempts,
        },
    )
    save_strategy(run_dir / "strategy_snapshot.yaml", strategy)

    writer_system, writer_user = build_writer_prompts(
        program_text, strategy, evaluate_text, topic
    )
    style_scorer = BaoyuScorer(baseline_path=lab_dir / "scorer" / "stats_baseline.json")
    style_gate = generate_article_with_style_gate(
        provider=provider,
        model=models["writer"],
        base_system_prompt=writer_system,
        base_user_prompt=writer_user,
        style_scorer=style_scorer,
        style_threshold=style_threshold,
        max_attempts=max_draft_attempts,
        run_dir=run_dir,
    )
    article = style_gate.article
    write_text(run_dir / "article.md", article + ("\n" if not article.endswith("\n") else ""))
    write_json(
        run_dir / "style_score.json",
        {
            "style_threshold": style_threshold,
            "style_gate_passed": style_gate.style_gate_passed,
            "style_score": style_gate.style_score,
            "attempt_count": style_gate.attempt_count,
            "selected_attempt": style_gate.selected_attempt,
            "score_payload": style_gate.style_payload,
        },
    )

    evaluator_system, evaluator_user = build_evaluator_prompts(
        evaluate_text, topic, article
    )
    evaluation_text = call_model(
        provider,
        models["evaluator"],
        evaluator_system,
        evaluator_user,
        temperature=0.0,
        max_output_tokens=1800,
    )
    evaluation = parse_evaluation(evaluation_text)
    write_json(run_dir / "evaluation.json", evaluation.raw_payload)

    improved = (
        style_gate.style_gate_passed
        and (previous_best is None or evaluation.total_score < previous_best)
    )
    strategy_change = "none"
    backup_path: Path | None = None

    if improved and not dry_run:
        mutator_system, mutator_user = build_mutator_prompts(
            strategy, topic, article, evaluation, previous_best
        )
        mutation_text = call_model(
            provider,
            models["mutator"],
            mutator_system,
            mutator_user,
            temperature=0.2,
            max_output_tokens=1200,
        )
        proposal = parse_mutation(mutation_text, strategy)
        updated_strategy, strategy_change = apply_mutation(strategy, proposal)
        backup_path = backup_strategy(strategy_path, history_dir, experiment_id)
        save_strategy(strategy_path, updated_strategy)
        write_json(
            run_dir / "mutation.json",
            {
                "field": proposal.field,
                "new_value": proposal.new_value,
                "reason": proposal.reason,
                "backup_path": str(backup_path),
            },
        )
    elif improved and dry_run:
        strategy_change = "dry-run"

    result_row = {
        "experiment_id": experiment_id,
        "timestamp": iso_timestamp(),
        "topic_id": topic.id,
        "strategy_hash": strategy_digest,
        "style_score": style_gate.style_score,
        "style_gate_passed": str(style_gate.style_gate_passed).lower(),
        "style_attempts": style_gate.attempt_count,
        "ai_smell": evaluation.ai_smell,
        "hook": evaluation.hook,
        "density": evaluation.density,
        "perspective": evaluation.perspective,
        "total_score": evaluation.total_score,
        "strategy_change": strategy_change,
    }
    append_result(results_path, result_row)

    return {
        "experiment_id": experiment_id,
        "topic": topic,
        "article_path": run_dir / "article.md",
        "evaluation_path": run_dir / "evaluation.json",
        "mutation_path": run_dir / "mutation.json",
        "backup_path": backup_path,
        "style_gate": style_gate,
        "evaluation": evaluation,
        "previous_best": previous_best,
        "improved": improved,
        "strategy_change": strategy_change,
    }


def print_round_summary(index: int, total_rounds: int, payload: dict[str, Any]) -> None:
    style_gate: StyleGateResult = payload["style_gate"]
    evaluation: EvaluationResult = payload["evaluation"]
    topic: Topic = payload["topic"]
    previous_best = payload["previous_best"]
    improved = payload["improved"]
    previous_label = select_topic_best_label(previous_best)
    print(
        f"[round {index}/{total_rounds}] "
        f"experiment={payload['experiment_id']} "
        f"topic={topic.id}:{topic.title}"
    )
    print(
        f"  total_score={evaluation.total_score} "
        f"(ai_smell={evaluation.ai_smell}, hook={evaluation.hook}, "
        f"density={evaluation.density}, perspective={evaluation.perspective})"
    )
    print(
        f"  previous_best={previous_label} improved={'yes' if improved else 'no'} "
        f"strategy_change={payload['strategy_change']}"
    )
    print(
        f"  style_score={style_gate.style_score} "
        f"passed={'yes' if style_gate.style_gate_passed else 'no'} "
        f"attempts={style_gate.attempt_count} selected_attempt={style_gate.selected_attempt}"
    )
    print(f"  summary={evaluation.summary}")
    print(f"  next_hypothesis={evaluation.improvement_hypothesis}")
    print(f"  article={payload['article_path']}")
    print(f"  style_eval={payload['article_path'].parent / 'style_score.json'}")
    print(f"  evaluation={payload['evaluation_path']}")
    if payload["backup_path"]:
        print(f"  strategy_backup={payload['backup_path']}")


def validate_lab_dir(lab_dir: Path) -> None:
    required = [
        lab_dir / "program.md",
        lab_dir / "strategy.md",
        lab_dir / "evaluate.md",
        lab_dir / "benchmark_topics.md",
        lab_dir / "results.tsv",
        lab_dir / "scorer" / "baoyu_scorer.py",
        lab_dir / "scorer" / "stats_baseline.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Lab directory is missing required files: " + ", ".join(missing)
        )


def main() -> int:
    args = parse_args()
    if args.rounds < 1:
        raise ValueError("--rounds must be >= 1")

    lab_dir = Path(args.lab_dir).resolve()
    validate_lab_dir(lab_dir)
    ensure_results_file(lab_dir / "results.tsv")

    provider = infer_provider(args.provider)
    models = resolve_models(provider, args)
    topics = load_topics(lab_dir / "benchmark_topics.md")
    rng = random.Random(args.seed)

    for index in range(1, args.rounds + 1):
        result = run_round(
            lab_dir=lab_dir,
            provider=provider,
            models=models,
            topics=topics,
            requested_topic_id=args.topic_id,
            rng=rng,
            dry_run=args.dry_run,
            style_threshold=args.style_threshold,
            max_draft_attempts=args.max_draft_attempts,
        )
        print_round_summary(index, args.rounds, result)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:  # noqa: BLE001
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
