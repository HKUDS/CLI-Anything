"""Manages s&box localization/translation files."""

import json
import os
from typing import Any, Dict, List, Optional


def create_translation_file(
    lang: str = "en",
    initial_keys: Optional[Dict[str, str]] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new translation JSON file.

    Args:
        lang: Language code (e.g. "en", "fr", "de").
        initial_keys: Initial key-value pairs.
        output_path: Output file path.

    Returns:
        Dict with lang, path, key_count, data.
    """
    data = initial_keys or {}

    result = {
        "lang": lang,
        "key_count": len(data),
        "data": data,
    }

    if output_path:
        if not output_path.endswith(".json"):
            output_path += ".json"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        result["path"] = os.path.abspath(output_path)

    return result


def load_translations(file_path: str) -> Dict[str, str]:
    """Load a translation file and return the key-value dict."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_translations(file_path: str, data: Dict[str, str]) -> None:
    """Save a translation dict to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def list_keys(file_path: str) -> List[str]:
    """List all translation keys in a file."""
    data = load_translations(file_path)
    return sorted(data.keys())


def get_key(file_path: str, key: str) -> Optional[str]:
    """Get the value for a translation key. Returns None if not found."""
    data = load_translations(file_path)
    return data.get(key)


def set_key(file_path: str, key: str, value: str) -> Dict[str, str]:
    """Set a translation key-value pair. Creates or updates.

    Returns the full updated translations dict.
    """
    data = load_translations(file_path)
    data[key] = value
    save_translations(file_path, data)
    return data


def remove_key(file_path: str, key: str) -> bool:
    """Remove a translation key.

    Returns True if key existed and was removed, False if not found.
    """
    data = load_translations(file_path)
    if key not in data:
        return False
    del data[key]
    save_translations(file_path, data)
    return True


def bulk_set( file_path: str, keys: Dict[str, str] ) -> Dict[str, str]:
    """Set multiple translation key-value pairs at once.

    Args:
        file_path: Path to the translation JSON file.
        keys: Dict of key-value pairs to set.

    Returns:
        The full updated translations dict.
    """
    data = load_translations( file_path )
    data.update( keys )
    save_translations( file_path, data )
    return data
