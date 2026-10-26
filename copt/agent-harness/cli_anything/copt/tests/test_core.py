import pytest

from cli_anything.copt.core.backend import (
    CoptError,
    parse_attributes,
    validate_model,
    validate_parameters,
)


def test_parse_attributes_extracts_numeric_values_and_status():
    output = """COPT>  get Rows
  IntAttr:  [Current] 4
COPT>  get LpStatus
  IntAttr:  [Current] 1 optimal
COPT>  get LpObjval
  DblAttr:  [Current] 88.2
"""
    assert parse_attributes(output) == {
        "Rows": 4,
        "LpStatus": 1,
        "LpStatusText": "optimal",
        "LpObjval": 88.2,
    }


def test_parse_attributes_uses_requested_names_when_copt_echoes_to_terminal():
    output = "  IntAttr:  [Current] 83\n  IntAttr:  [Current] 8 timeout\n"
    assert parse_attributes(output, requested=["Cols", "MipStatus"]) == {
        "Cols": 83,
        "MipStatus": 8,
        "MipStatusText": "timeout",
    }


def test_parse_attributes_rejects_missing_requested_value():
    with pytest.raises(CoptError, match="Expected 2 COPT attributes, got 1"):
        parse_attributes("  IntAttr:  [Current] 83\n", requested=["Cols", "Rows"])


def test_parse_attributes_accepts_copt_seconds_suffix():
    assert parse_attributes(
        "  DblAttr:  [Current] 0.125s\n", requested=["SolvingTime"]
    ) == {"SolvingTime": 0.125}


def test_validate_model_accepts_existing_lp(tmp_path):
    model = tmp_path / "a model.lp"
    model.write_text("Minimize\n obj: x\nEnd\n")
    assert validate_model(model) == model.resolve()


def test_validate_model_rejects_missing_file(tmp_path):
    with pytest.raises(CoptError, match="does not exist"):
        validate_model(tmp_path / "missing.lp")


def test_validate_model_rejects_unsupported_format(tmp_path):
    model = tmp_path / "x.txt"
    model.write_text("x")
    with pytest.raises(CoptError, match="format"):
        validate_model(model)


def test_validate_parameters_rejects_nonpositive_limit():
    with pytest.raises(CoptError, match="TimeLimit"):
        validate_parameters(time_limit=0, threads=None, rel_gap=None)


def test_validate_parameters_rejects_negative_gap():
    with pytest.raises(CoptError, match="RelGap"):
        validate_parameters(time_limit=None, threads=None, rel_gap=-0.1)


def test_validate_parameters_returns_documented_set_commands():
    assert validate_parameters(time_limit=5, threads=2, rel_gap=0.01) == [
        "set TimeLimit 5", "set Threads 2", "set RelGap 0.01"
    ]
