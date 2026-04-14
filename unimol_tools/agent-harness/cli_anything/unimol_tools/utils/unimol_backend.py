"""Uni-Mol Backend Adapter - Wraps unimol_tools API"""

import os
import time
from typing import Dict, Any, Optional

try:
    from unimol_tools import MolTrain, MolPredict, UniMolRepr
    UNIMOL_AVAILABLE = True
except ImportError:
    UNIMOL_AVAILABLE = False


class UniMolError(Exception):
    """Base exception for Uni-Mol backend"""
    pass


class DataValidationError(UniMolError):
    """Data validation failed"""
    pass


class ModelNotFoundError(UniMolError):
    """Model not found"""
    pass


class TrainingError(UniMolError):
    """Training failed"""
    pass


class UniMolBackend:
    """Backend adapter - wraps unimol_tools API"""

    def __init__(self):
        if not UNIMOL_AVAILABLE:
            raise RuntimeError(
                "unimol_tools not found. Install with:\n"
                "  pip install unimol_tools --upgrade\n"
                "  pip install huggingface_hub  # for automatic weight download"
            )

    def train(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Train model

        Args:
            config: Training configuration dict
                - task: classification/regression/multiclass/...
                - data_path: Training data path
                - save_path: Model save path
                - epochs: Training epochs
                - batch_size: Batch size
                - learning_rate: Learning rate
                - metrics: Evaluation metrics
                - ... (other params see MolTrain API)

        Returns:
            {
                "status": "completed",
                "metrics": {...},
                "model_path": "...",
                "duration_sec": 123.45
            }

        Raises:
            DataValidationError: Data validation failed
            TrainingError: Training failed
        """
        start_time = time.time()

        try:
            # Create trainer
            clf = MolTrain(
                task=config["task"],
                data_type=config.get("data_type", "molecule"),
                epochs=config["epochs"],
                batch_size=config["batch_size"],
                learning_rate=config["learning_rate"],
                early_stopping=config.get("early_stopping", 20),
                metrics=config["metrics"],
                split=config.get("split", "random"),
                kfold=config.get("kfold", 1),
                save_path=config["save_path"],
                remove_hs=config.get("remove_hs", False),
                conf_cache_level=config.get("conf_cache_level", 1),
                target_normalize=config.get("target_normalize", "auto"),
                use_cuda=config.get("use_gpu", "all") != "none",
                use_ddp=config.get("use_ddp", False),
                use_amp=config.get("use_amp", False),
                model_name=config.get("model_name", "unimolv1"),
                # model_size only for unimolv2
                **({"model_size": config.get("model_size", "84m")} if config.get("model_name") == "unimolv2" else {}),
                load_model_dir=config.get("load_model_dir"),
                freeze_layers=config.get("freeze_layers"),
            )

            # Train
            print(f"[UniMolBackend] Starting training: {config.get('task')}, {config.get('epochs')} epochs")
            metrics = clf.fit(data=config["data_path"])

            duration = time.time() - start_time

            # Try to load metrics from saved file (Uni-Mol saves to metric.result)
            metrics_json = {}
            metric_file = os.path.join(config["save_path"], "metric.result")
            if os.path.exists(metric_file):
                try:
                    import pickle
                    with open(metric_file, 'rb') as f:
                        saved_metrics = pickle.load(f)
                    metrics_json = self._convert_metrics_to_json(saved_metrics)
                    print(f"[UniMolBackend] Loaded metrics from {metric_file}")
                except Exception as e:
                    print(f"[UniMolBackend] Warning: Could not load metrics file: {e}")
                    metrics_json = self._convert_metrics_to_json(metrics)
            else:
                # Fall back to return value from fit()
                metrics_json = self._convert_metrics_to_json(metrics)

            print(f"[UniMolBackend] Training completed in {duration:.2f}s")
            print(f"[UniMolBackend] Metrics: {metrics_json}")

            return {
                "status": "completed",
                "metrics": metrics_json,
                "model_path": config["save_path"],
                "duration_sec": duration
            }

        except FileNotFoundError as e:
            raise DataValidationError(f"Training data not found: {e}")
        except ValueError as e:
            raise DataValidationError(f"Invalid configuration: {e}")
        except Exception as e:
            raise TrainingError(f"Training failed: {e}")

    @staticmethod
    def _convert_metrics_to_json(metrics):
        """Convert metrics (dict/list/numpy) to JSON-serializable format"""
        import numpy as np

        if metrics is None:
            return {}

        if isinstance(metrics, dict):
            result = {}
            for k, v in metrics.items():
                if isinstance(v, (np.integer, np.floating)):
                    result[k] = float(v)
                elif isinstance(v, np.ndarray):
                    result[k] = v.tolist()
                elif isinstance(v, (list, tuple)):
                    result[k] = [float(x) if isinstance(x, (np.integer, np.floating)) else x for x in v]
                else:
                    result[k] = v
            return result
        elif isinstance(metrics, (list, tuple)):
            return [float(x) if isinstance(x, (np.integer, np.floating)) else x for x in metrics]
        else:
            return {"value": float(metrics) if isinstance(metrics, (np.integer, np.floating)) else metrics}

    def predict(
        self,
        model_dir: str,
        data_path: str,
        output_path: str,
        metrics: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict

        Args:
            model_dir: Model directory
            data_path: Data path
            output_path: Output path
            metrics: Evaluation metrics (optional)

        Returns:
            {
                "status": "completed",
                "output_path": "...",
                "metrics": {...}
            }

        Raises:
            ModelNotFoundError: Model not found
            DataValidationError: Data validation failed
        """
        if not os.path.exists(model_dir):
            raise ModelNotFoundError(f"Model directory not found: {model_dir}")

        if not os.path.exists(data_path):
            raise DataValidationError(f"Data not found: {data_path}")

        try:
            print(f"[UniMolBackend] Loading model from {model_dir}")
            predictor = MolPredict(load_model=model_dir)

            # Uni-Mol's predict expects a directory, not a file
            # It will create files like: save_path/input_filename.predict.0.csv
            if output_path.endswith('.csv'):
                # If user specified a .csv file, use its parent directory
                save_dir = os.path.dirname(output_path)
                if not save_dir:
                    save_dir = '.'
            else:
                save_dir = output_path

            print(f"[UniMolBackend] Predicting on {data_path}")
            result_metrics = predictor.predict(
                data=data_path,
                save_path=save_dir,
                metrics=metrics
            )

            # Find the actual output file created by Uni-Mol
            data_basename = os.path.basename(data_path).replace('.csv', '')
            actual_output = os.path.join(save_dir, f"{data_basename}.predict.0.csv")

            # If user specified a specific filename, rename it
            if output_path.endswith('.csv') and actual_output != output_path:
                if os.path.exists(actual_output):
                    os.rename(actual_output, output_path)
                    print(f"[UniMolBackend] Renamed prediction file to {output_path}")
                    final_output = output_path
                else:
                    print(f"[UniMolBackend] Warning: Expected output {actual_output} not found")
                    final_output = actual_output
            else:
                final_output = actual_output

            print(f"[UniMolBackend] Prediction saved to {final_output}")

            # Handle metrics safely (could be None, dict, or numpy array)
            metrics_result = {}
            if result_metrics is not None:
                if isinstance(result_metrics, dict):
                    metrics_result = result_metrics
                else:
                    # If it's not a dict (e.g., numpy array), skip it
                    metrics_result = {}

            return {
                "status": "completed",
                "output_path": final_output,
                "metrics": metrics_result
            }

        except Exception as e:
            raise TrainingError(f"Prediction failed: {e}")

    def get_representation(
        self,
        data_path: str,
        model_name: str = "unimolv1",
        model_size: str = "84m",
        return_atomic_reprs: bool = False,
        batch_size: int = 32
    ) -> Dict[str, Any]:
        """
        Get molecular representations

        Args:
            data_path: Data path
            model_name: Model name
            model_size: Model size (unimolv2 only)
            return_atomic_reprs: Return atomic-level representations
            batch_size: Batch size

        Returns:
            {"cls_repr": array, "atomic_reprs": array (optional)}
        """
        kwargs = {
            "data_type": "molecule",
            "model_name": model_name,
            "batch_size": batch_size
        }

        # model_size only for unimolv2
        if model_name == "unimolv2":
            kwargs["model_size"] = model_size

        repr_model = UniMolRepr(**kwargs)

        reprs = repr_model.get_repr(
            data=data_path,
            return_atomic_reprs=return_atomic_reprs,
            return_tensor=True
        )

        return reprs

    @staticmethod
    def is_available() -> tuple[bool, str]:
        """Check if unimol_tools is available"""
        if not UNIMOL_AVAILABLE:
            return False, "unimol_tools not installed"

        # Check CUDA availability
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            device_count = torch.cuda.device_count() if cuda_available else 0
            return True, f"Available (CUDA: {cuda_available}, GPUs: {device_count})"
        except ImportError:
            return True, "Available (CPU only, PyTorch not found)"
