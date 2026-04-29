"""Model weight management utilities"""

import os
import sys


def download_weights(model_name="unimolv1", weight_dir=None):
    """
    Download model weights using unimol_tools weighthub

    Args:
        model_name: Model name (unimolv1, unimolv2-84m, etc.)
        weight_dir: Custom weight directory (optional)

    Returns:
        dict with download status
    """
    try:
        # Import from installed unimol_tools
        from unimol_tools.weights import weighthub

        # Set custom weight directory if provided
        if weight_dir:
            os.environ['UNIMOL_WEIGHT_DIR'] = weight_dir
            weighthub.WEIGHT_DIR = weight_dir

        # Map model names to weight files
        weight_map = {
            'unimolv1': 'mol_pre_all_h_220816.pt',
            'unimolv2-84m': 'unimol2_checkpoint_84m.pt',
            'unimolv2-164m': 'unimol2_checkpoint_164m.pt',
            'unimolv2-310m': 'unimol2_checkpoint_310m.pt',
            'unimolv2-570m': 'unimol2_checkpoint_570m.pt',
            'unimolv2-1.1B': 'unimol2_checkpoint_1.1B.pt',
        }

        pretrain_file = weight_map.get(model_name)
        if not pretrain_file:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(weight_map.keys())}")

        save_path = weighthub.WEIGHT_DIR

        # Check if already downloaded
        if os.path.exists(os.path.join(save_path, pretrain_file)):
            return {
                "status": "exists",
                "model": model_name,
                "path": os.path.join(save_path, pretrain_file),
                "message": f"{model_name} already downloaded"
            }

        # Download
        print(f"Downloading {model_name} ({pretrain_file})...")

        if model_name.startswith('unimolv2'):
            weighthub.weight_download_v2(pretrain_file, save_path)
        else:
            weighthub.weight_download(pretrain_file, save_path)

        return {
            "status": "downloaded",
            "model": model_name,
            "path": os.path.join(save_path, pretrain_file),
            "message": f"{model_name} downloaded successfully"
        }

    except ImportError as e:
        raise RuntimeError(
            "unimol_tools not installed or weighthub not available. "
            "Install with: pip install unimol_tools huggingface_hub"
        )
    except Exception as e:
        return {
            "status": "error",
            "model": model_name,
            "error": str(e)
        }


def list_downloaded_weights():
    """List all downloaded weights"""
    try:
        from unimol_tools.weights import weighthub

        weight_dir = weighthub.WEIGHT_DIR

        if not os.path.exists(weight_dir):
            return {
                "weight_dir": weight_dir,
                "weights": [],
                "message": "Weight directory not found"
            }

        # List all .pt files
        weights = [f for f in os.listdir(weight_dir) if f.endswith('.pt')]

        return {
            "weight_dir": weight_dir,
            "weights": weights,
            "total": len(weights)
        }

    except Exception as e:
        return {
            "error": str(e)
        }


def get_weight_info():
    """Get weight directory and environment info"""
    try:
        from unimol_tools.weights import weighthub

        return {
            "weight_dir": weighthub.WEIGHT_DIR,
            "hf_endpoint": os.environ.get('HF_ENDPOINT', 'not set'),
            "custom_dir": 'UNIMOL_WEIGHT_DIR' in os.environ,
            "exists": os.path.exists(weighthub.WEIGHT_DIR)
        }
    except:
        return {
            "error": "unimol_tools not available"
        }


if __name__ == "__main__":
    # CLI interface for weight management
    import argparse

    parser = argparse.ArgumentParser(description="Uni-Mol weight management")
    parser.add_argument('--download', type=str, help="Download model (unimolv1, unimolv2-84m, etc.)")
    parser.add_argument('--list', action='store_true', help="List downloaded weights")
    parser.add_argument('--info', action='store_true', help="Show weight directory info")
    parser.add_argument('--dir', type=str, help="Custom weight directory")

    args = parser.parse_args()

    if args.info or (not args.download and not args.list):
        info = get_weight_info()
        print("Weight Directory Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")

    if args.list:
        result = list_downloaded_weights()
        print(f"\nDownloaded Weights ({result.get('total', 0)}):")
        for w in result.get('weights', []):
            print(f"  - {w}")

    if args.download:
        result = download_weights(args.download, args.dir)
        print(f"\nDownload Result:")
        print(f"  Status: {result['status']}")
        print(f"  Model: {result['model']}")
        if 'path' in result:
            print(f"  Path: {result['path']}")
        if 'message' in result:
            print(f"  Message: {result['message']}")
        if 'error' in result:
            print(f"  Error: {result['error']}", file=sys.stderr)
