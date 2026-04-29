"""
Tests for models manager module
"""

import pytest
from datetime import datetime, timedelta
from cli_anything.unimol_tools.core.models_manager import (
    calculate_model_score,
    rank_models,
    get_best_model,
    compare_models,
    get_model_history,
    suggest_deletable_models
)


@pytest.fixture
def sample_runs():
    """Sample runs with different metrics"""
    base_time = datetime.now()

    return [
        {
            "run_id": "run_001",
            "timestamp": (base_time - timedelta(days=5)).isoformat(),
            "metrics": {"auc": 0.75, "accuracy": 0.70},
            "duration_sec": 16.3
        },
        {
            "run_id": "run_002",
            "timestamp": (base_time - timedelta(days=3)).isoformat(),
            "metrics": {"auc": 0.85, "accuracy": 0.80},
            "duration_sec": 19.7
        },
        {
            "run_id": "run_003",
            "timestamp": (base_time - timedelta(days=1)).isoformat(),
            "metrics": {"auc": 0.92, "accuracy": 0.88},
            "duration_sec": 26.8
        },
        {
            "run_id": "run_004",
            "timestamp": base_time.isoformat(),
            "metrics": {"auc": 0.68, "accuracy": 0.65},
            "duration_sec": 15.2
        }
    ]


@pytest.fixture
def sample_project(sample_runs):
    """Sample project with runs"""
    return {
        "project_name": "test_project",
        "task_type": "classification",
        "runs": sample_runs
    }


class TestCalculateModelScore:
    """Test model scoring algorithm"""

    def test_auc_based_score(self):
        """Test 100% AUC-based scoring"""
        run = {
            "metrics": {"auc": 0.85},
            "duration_sec": 20,
            "timestamp": datetime.now().isoformat()
        }

        score = calculate_model_score(run)
        assert score == 8.5  # AUC * 10

    def test_perfect_score(self):
        """Test perfect AUC gives perfect score"""
        run = {
            "metrics": {"auc": 1.0},
            "duration_sec": 20,
            "timestamp": datetime.now().isoformat()
        }

        score = calculate_model_score(run)
        assert score == 10.0

    def test_poor_score(self):
        """Test poor AUC gives low score"""
        run = {
            "metrics": {"auc": 0.50},
            "duration_sec": 20,
            "timestamp": datetime.now().isoformat()
        }

        score = calculate_model_score(run)
        assert score == 5.0

    def test_missing_auc_uses_auroc(self):
        """Test fallback to auroc if auc missing"""
        run = {
            "metrics": {"auroc": 0.88},
            "duration_sec": 20,
            "timestamp": datetime.now().isoformat()
        }

        score = calculate_model_score(run)
        assert score == 8.8

    def test_missing_metrics(self):
        """Test handling of missing metrics"""
        run = {
            "duration_sec": 20,
            "timestamp": datetime.now().isoformat()
        }

        score = calculate_model_score(run)
        # Should default to 0.5 AUC
        assert score == 5.0

    def test_custom_weights(self):
        """Test custom weight configuration"""
        run = {
            "metrics": {"auc": 0.80},
            "duration_sec": 10,
            "timestamp": datetime.now().isoformat()
        }

        # With time weight
        score = calculate_model_score(
            run,
            weight_auc=0.7,
            weight_time=0.3,
            weight_recency=0.0
        )

        # Should incorporate time component
        assert score != 8.0
        assert 0 <= score <= 10


class TestRankModels:
    """Test model ranking"""

    def test_rank_by_auc(self, sample_project):
        """Test ranking by AUC"""
        ranked = rank_models(sample_project)

        assert len(ranked) == 4
        assert ranked[0]["run_id"] == "run_003"  # Best AUC
        assert ranked[1]["run_id"] == "run_002"
        assert ranked[2]["run_id"] == "run_001"
        assert ranked[3]["run_id"] == "run_004"  # Worst AUC

    def test_rank_includes_scores(self, sample_project):
        """Test that ranking includes scores"""
        ranked = rank_models(sample_project)

        for model in ranked:
            assert "score" in model
            assert "auc" in model
            assert "status" in model
            assert "rank" in model

    def test_rank_numbers_sequential(self, sample_project):
        """Test rank numbers are sequential"""
        ranked = rank_models(sample_project)

        for i, model in enumerate(ranked, 1):
            assert model["rank"] == i

    def test_status_labels(self, sample_project):
        """Test status label assignment"""
        ranked = rank_models(sample_project)

        # run_003 has AUC 0.92 and score 9.2
        assert ranked[0]["status"] == "Best"

        # run_002 has AUC 0.85 and score 8.5
        assert ranked[1]["status"] in ["Good", "Best"]

        # run_004 has AUC 0.68
        assert ranked[3]["status"] in ["Weak", "Poor"]

    def test_empty_runs(self):
        """Test ranking with no runs"""
        project = {"runs": []}
        ranked = rank_models(project)

        assert ranked == []

    def test_single_run(self):
        """Test ranking with single run"""
        project = {
            "runs": [{
                "run_id": "run_001",
                "metrics": {"auc": 0.80},
                "duration_sec": 20,
                "timestamp": datetime.now().isoformat()
            }]
        }

        ranked = rank_models(project)

        assert len(ranked) == 1
        assert ranked[0]["rank"] == 1


class TestGetBestModel:
    """Test getting best model"""

    def test_get_best_by_auc(self, sample_project):
        """Test getting best model by AUC"""
        best = get_best_model(sample_project, metric="auc")

        assert best is not None
        assert best["run_id"] == "run_003"
        assert best["metrics"]["auc"] == 0.92

    def test_get_best_by_accuracy(self, sample_project):
        """Test getting best model by accuracy"""
        best = get_best_model(sample_project, metric="accuracy")

        assert best is not None
        assert best["run_id"] == "run_003"
        assert best["metrics"]["accuracy"] == 0.88

    def test_no_runs(self):
        """Test with no runs"""
        project = {"runs": []}
        best = get_best_model(project)

        assert best is None

    def test_missing_metric(self):
        """Test with missing metric"""
        project = {
            "runs": [{
                "run_id": "run_001",
                "metrics": {},
                "duration_sec": 20
            }]
        }

        best = get_best_model(project, metric="auc")
        # Should still return the run even if metric missing
        assert best is not None


class TestCompareModels:
    """Test model comparison"""

    def test_compare_two_models(self, sample_project):
        """Test comparing two models"""
        result = compare_models(sample_project, ["run_002", "run_003"])

        assert "comparisons" in result
        assert "overall_winner" in result
        assert result["overall_winner"] in ["run_002", "run_003"]

    def test_compare_includes_metrics(self, sample_project):
        """Test comparison includes all metrics"""
        result = compare_models(sample_project, ["run_002", "run_003"])

        comparisons = result["comparisons"]

        # Should have AUC comparison
        assert "auc" in comparisons
        assert "values" in comparisons["auc"]
        assert "winner" in comparisons["auc"]

    def test_compare_insufficient_models(self, sample_project):
        """Test comparison with <2 models"""
        result = compare_models(sample_project, ["run_001"])

        assert "error" in result
        assert result["error"] == "Need at least 2 models to compare"

    def test_compare_nonexistent_models(self, sample_project):
        """Test comparison with nonexistent models"""
        result = compare_models(sample_project, ["run_999", "run_998"])

        assert "error" in result

    def test_overall_winner_calculation(self, sample_project):
        """Test overall winner is correctly calculated"""
        result = compare_models(sample_project, ["run_001", "run_002", "run_003"])

        # run_003 should win most metrics
        assert result["overall_winner"] == "run_003"

        # Check win counts
        assert "win_counts" in result
        assert result["win_counts"]["run_003"] > result["win_counts"]["run_001"]


class TestGetModelHistory:
    """Test model performance history"""

    def test_history_timeline(self, sample_project):
        """Test history timeline generation"""
        history = get_model_history(sample_project)

        assert "timeline" in history
        assert len(history["timeline"]) == 4

        # Should be sorted by timestamp
        timestamps = [item["timestamp"] for item in history["timeline"]]
        assert timestamps == sorted(timestamps)

    def test_trend_detection_improving(self):
        """Test detecting improving trend"""
        base_time = datetime.now()

        project = {
            "runs": [
                {
                    "run_id": "run_001",
                    "timestamp": (base_time - timedelta(days=2)).isoformat(),
                    "metrics": {"auc": 0.70}
                },
                {
                    "run_id": "run_002",
                    "timestamp": (base_time - timedelta(days=1)).isoformat(),
                    "metrics": {"auc": 0.80}
                },
                {
                    "run_id": "run_003",
                    "timestamp": base_time.isoformat(),
                    "metrics": {"auc": 0.90}
                }
            ]
        }

        history = get_model_history(project)

        assert history["trend"] == "improving"

    def test_trend_detection_declining(self):
        """Test detecting declining trend"""
        base_time = datetime.now()

        project = {
            "runs": [
                {
                    "run_id": "run_001",
                    "timestamp": (base_time - timedelta(days=2)).isoformat(),
                    "metrics": {"auc": 0.90}
                },
                {
                    "run_id": "run_002",
                    "timestamp": (base_time - timedelta(days=1)).isoformat(),
                    "metrics": {"auc": 0.80}
                },
                {
                    "run_id": "run_003",
                    "timestamp": base_time.isoformat(),
                    "metrics": {"auc": 0.70}
                }
            ]
        }

        history = get_model_history(project)

        assert history["trend"] == "declining"

    def test_trend_detection_stable(self):
        """Test detecting stable trend"""
        base_time = datetime.now()

        project = {
            "runs": [
                {
                    "run_id": "run_001",
                    "timestamp": (base_time - timedelta(days=2)).isoformat(),
                    "metrics": {"auc": 0.80}
                },
                {
                    "run_id": "run_002",
                    "timestamp": base_time.isoformat(),
                    "metrics": {"auc": 0.82}
                }
            ]
        }

        history = get_model_history(project)

        assert history["trend"] == "stable"

    def test_insights_generation(self, sample_project):
        """Test insights are generated"""
        history = get_model_history(sample_project)

        assert "insights" in history
        assert isinstance(history["insights"], list)

    def test_empty_history(self):
        """Test history with no runs"""
        project = {"runs": []}
        history = get_model_history(project)

        assert history["timeline"] == []
        assert history["trend"] == "none"
        assert history["total_runs"] == 0


class TestSuggestDeletableModels:
    """Test cleanup suggestions"""

    def test_suggest_with_defaults(self, sample_project):
        """Test suggestions with default parameters"""
        suggestions = suggest_deletable_models(sample_project)

        assert "delete" in suggestions
        assert "archive" in suggestions
        assert "keep" in suggestions

    def test_keep_best_n(self):
        """Test keeping best N models"""
        base_time = datetime.now()

        project = {
            "runs": [
                {
                    "run_id": f"run_{i:03d}",
                    "timestamp": (base_time - timedelta(days=i)).isoformat(),
                    "metrics": {"auc": 0.70 + i * 0.02},
                    "duration_sec": 20
                }
                for i in range(10)
            ]
        }

        suggestions = suggest_deletable_models(project, keep_best_n=3)

        # Should keep at least 3 models
        assert len(suggestions["keep"]) >= 3

    def test_min_auc_threshold(self, sample_project):
        """Test minimum AUC threshold"""
        suggestions = suggest_deletable_models(
            sample_project,
            min_auc=0.80,
            keep_best_n=1
        )

        # Models with AUC < 0.80 should be suggested for deletion
        for model in suggestions["delete"]:
            # Find the run
            run = next((r for r in sample_project["runs"]
                       if r["run_id"] == model["run_id"]), None)
            if run:
                assert run["metrics"]["auc"] < 0.80

    def test_max_age_days(self, sample_project):
        """Test maximum age threshold"""
        suggestions = suggest_deletable_models(
            sample_project,
            max_age_days=2,
            keep_best_n=1
        )

        # Recent models should be kept
        for model in suggestions["keep"]:
            if "Recent" in model["reason"]:
                run = next((r for r in sample_project["runs"]
                           if r["run_id"] == model["run_id"]), None)
                assert run is not None

    def test_empty_project(self):
        """Test suggestions for empty project"""
        project = {"runs": []}
        suggestions = suggest_deletable_models(project)

        assert suggestions["delete"] == []
        assert suggestions["archive"] == []
        assert suggestions["keep"] == []


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_malformed_timestamp(self):
        """Test handling of malformed timestamp"""
        project = {
            "runs": [{
                "run_id": "run_001",
                "timestamp": "invalid-timestamp",
                "metrics": {"auc": 0.80},
                "duration_sec": 20
            }]
        }

        # Should not crash
        score = calculate_model_score(project["runs"][0])
        assert score > 0

    def test_negative_duration(self):
        """Test handling of negative duration"""
        run = {
            "metrics": {"auc": 0.80},
            "duration_sec": -10,
            "timestamp": datetime.now().isoformat()
        }

        # Should handle gracefully
        score = calculate_model_score(run)
        assert score > 0

    def test_missing_duration(self):
        """Test handling of missing duration"""
        run = {
            "metrics": {"auc": 0.80},
            "timestamp": datetime.now().isoformat()
        }

        score = calculate_model_score(run)
        assert score == 8.0  # Should use only AUC


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
