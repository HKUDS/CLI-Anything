"""Pytest fixtures"""

import pytest
import pandas as pd
import os
import tempfile


@pytest.fixture
def classification_data():
    """Classification task test data (60 samples)"""
    base_data = pd.DataFrame({
        "SMILES": ["CCO", "CC(=O)O", "CC", "CCC", "CCCC", "CCCCC"],
        "TARGET": [0, 1, 0, 1, 0, 1]
    })
    # Repeat 10 times for sufficient samples
    return pd.concat([base_data] * 10, ignore_index=True)


@pytest.fixture
def regression_data(tmp_path):
    """Regression task test data"""
    base_data = pd.DataFrame({
        "SMILES": ["CCO", "CC(=O)O", "CC", "CCC", "CCCC", "CCCCC"],
        "TARGET": [0.1, 0.5, 0.2, 0.8, 0.3, 0.9]
    })
    data = pd.concat([base_data] * 10, ignore_index=True)

    # Create temporary CSV files
    train_path = str(tmp_path / "regression_train.csv")
    test_path = str(tmp_path / "regression_test.csv")

    data.to_csv(train_path, index=False)
    data.iloc[:20].to_csv(test_path, index=False)

    return {"train": train_path, "test": test_path}


@pytest.fixture
def binary_classification_data(tmp_path):
    """Binary classification test data with CSV files"""
    base_data = pd.DataFrame({
        "SMILES": ["CCO", "CC(=O)O", "CC", "CCC", "CCCC", "CCCCC"],
        "TARGET": [0, 1, 0, 1, 0, 1]
    })
    data = pd.concat([base_data] * 10, ignore_index=True)

    train_path = str(tmp_path / "binary_train.csv")
    test_path = str(tmp_path / "binary_test.csv")

    data.to_csv(train_path, index=False)
    data.iloc[:20].to_csv(test_path, index=False)

    return {"train": train_path, "test": test_path}


@pytest.fixture
def multiclass_data(tmp_path):
    """Multiclass classification test data"""
    base_data = pd.DataFrame({
        "SMILES": ["CCO", "CC(=O)O", "CC", "CCC", "CCCC", "CCCCC"],
        "TARGET": [0, 1, 2, 0, 1, 2]
    })
    data = pd.concat([base_data] * 10, ignore_index=True)

    train_path = str(tmp_path / "multiclass_train.csv")
    test_path = str(tmp_path / "multiclass_test.csv")

    data.to_csv(train_path, index=False)
    data.iloc[:20].to_csv(test_path, index=False)

    return {"train": train_path, "test": test_path}


@pytest.fixture
def multilabel_classification_data(tmp_path):
    """Multilabel classification test data"""
    base_data = pd.DataFrame({
        "SMILES": ["CCO", "CC(=O)O", "CC", "CCC", "CCCC", "CCCCC"],
        "TARGET": [0, 1, 0, 1, 0, 1],
        "TARGET_1": [1, 0, 1, 0, 1, 0],
        "TARGET_2": [1, 1, 0, 0, 1, 1]
    })
    data = pd.concat([base_data] * 10, ignore_index=True)

    train_path = str(tmp_path / "multilabel_class_train.csv")
    test_path = str(tmp_path / "multilabel_class_test.csv")

    data.to_csv(train_path, index=False)
    data.iloc[:20].to_csv(test_path, index=False)

    return {"train": train_path, "test": test_path}


@pytest.fixture
def multilabel_regression_data(tmp_path):
    """Multilabel regression test data"""
    base_data = pd.DataFrame({
        "SMILES": ["CCO", "CC(=O)O", "CC", "CCC", "CCCC", "CCCCC"],
        "TARGET": [0.1, 0.5, 0.2, 0.8, 0.3, 0.9],
        "TARGET_1": [1.2, 1.5, 1.1, 1.8, 1.3, 1.7],
        "TARGET_2": [2.1, 2.5, 2.2, 2.8, 2.3, 2.9]
    })
    data = pd.concat([base_data] * 10, ignore_index=True)

    train_path = str(tmp_path / "multilabel_reg_train.csv")
    test_path = str(tmp_path / "multilabel_reg_test.csv")

    data.to_csv(train_path, index=False)
    data.iloc[:20].to_csv(test_path, index=False)

    return {"train": train_path, "test": test_path}


@pytest.fixture
def tmp_dir(tmp_path):
    """Temporary directory"""
    return str(tmp_path)


def _resolve_cli(name):
    """Resolve installed CLI command"""
    import shutil
    import sys

    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)

    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]

    if force:
        raise RuntimeError(f"{name} not found. Install with: pip install -e .")

    # Dev mode fallback
    module = "cli_anything.unimol_tools.unimol_tools_cli"
    print(f"[_resolve_cli] Fallback to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]
