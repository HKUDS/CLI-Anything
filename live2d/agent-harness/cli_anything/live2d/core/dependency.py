"""Build dependency graph between motions, expressions, and parameters."""

from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

from .parser import ModelInfo
from .motion_parser import load_motion, MotionInfo
from .expression_parser import load_expression, ExpressionInfo


@dataclass
class ParamUsage:
    """Track which motions/expressions use a parameter."""
    param_id: str
    motions: list[str] = field(default_factory=list)
    expressions: list[str] = field(default_factory=list)

    @property
    def total_references(self) -> int:
        return len(self.motions) + len(self.expressions)


@dataclass
class DependencyGraph:
    model_path: Path
    params: dict[str, ParamUsage] = field(default_factory=dict)
    parse_errors: list[dict] = field(default_factory=list)

    @property
    def param_count(self) -> int:
        return len(self.params)

    def to_dict(self) -> dict:
        return {
            "model": str(self.model_path),
            "param_count": self.param_count,
            "parse_errors": len(self.parse_errors),
            "params": {
                pid: {
                    "motions": u.motions,
                    "expressions": u.expressions,
                    "total_references": u.total_references,
                }
                for pid, u in sorted(self.params.items(), key=lambda x: -x[1].total_references)
            },
        }


def build_dependency_graph(info: ModelInfo) -> DependencyGraph:
    """Build a dependency graph from a model."""
    graph = DependencyGraph(model_path=info.path)
    model_dir = info.path.parent

    # Process motions
    for group, motions in info.motions.items():
        for m in motions:
            motion_path = model_dir / m.file
            try:
                motion = load_motion(motion_path)
                for pid in motion.parameter_ids:
                    if pid not in graph.params:
                        graph.params[pid] = ParamUsage(param_id=pid)
                    graph.params[pid].motions.append(f"[{group}] {m.file}")
            except Exception as e:
                graph.parse_errors.append({"file": m.file, "error": str(e)})

    # Process expressions
    for expr in info.expressions:
        expr_path = model_dir / expr.file
        try:
            expression = load_expression(expr_path)
            for pid in expression.param_ids:
                if pid not in graph.params:
                    graph.params[pid] = ParamUsage(param_id=pid)
                graph.params[pid].expressions.append(expr.name)
        except Exception as e:
            graph.parse_errors.append({"file": expr.file, "error": str(e)})

    return graph
