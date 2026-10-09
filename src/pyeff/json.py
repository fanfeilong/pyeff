"""JSON file utilities with user-friendly API.

This module provides simplified JSON file operations with:
- Type hints for better IDE support
- Proper exception handling
- Optional async support (requires aiofiles)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union

PathLike = Union[str, Path]


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def load_json(path: PathLike, encoding: str = "utf-8") -> Any:
    """Load and parse a JSON file.

    Args:
        path: Path to the JSON file.
        encoding: File encoding (default: utf-8).

    Returns:
        Parsed JSON data (dict, list, or primitive).

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    file_path = _to_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with open(file_path, "r", encoding=encoding) as f:
        return json.load(f)


def dump_json(
    obj: Any,
    path: PathLike,
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> None:
    """Write an object to a JSON file.

    Args:
        obj: Python object to serialize.
        path: Destination file path.
        encoding: File encoding (default: utf-8).
        indent: Number of spaces for indentation (default: 2).
        ensure_ascii: If True, escape non-ASCII characters (default: False).
        sort_keys: If True, sort dictionary keys (default: False).

    Raises:
        TypeError: If the object is not JSON serializable.
    """
    file_path = _to_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding=encoding) as f:
        json.dump(obj, f, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)


def loads(s: str) -> Any:
    """Parse a JSON string.

    Args:
        s: JSON string to parse.

    Returns:
        Parsed JSON data.

    Raises:
        json.JSONDecodeError: If the string contains invalid JSON.
    """
    return json.loads(s)


def dumps(
    obj: Any,
    indent: Optional[int] = None,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> str:
    """Serialize an object to a JSON string.

    Args:
        obj: Python object to serialize.
        indent: Number of spaces for indentation (None for compact).
        ensure_ascii: If True, escape non-ASCII characters.
        sort_keys: If True, sort dictionary keys.

    Returns:
        JSON string representation.

    Raises:
        TypeError: If the object is not JSON serializable.
    """
    return json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)


def merge(base: dict, update: dict, deep: bool = True) -> dict:
    """Merge two dictionaries, with update values taking precedence.

    Args:
        base: Base dictionary.
        update: Dictionary with values to merge in.
        deep: If True, recursively merge nested dicts (default: True).

    Returns:
        New merged dictionary.
    """
    result = base.copy()

    for key, value in update.items():
        if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge(result[key], value, deep=True)
        else:
            result[key] = value

    return result


try:
    import aiofiles

    async def load_json_async(path: PathLike, encoding: str = "utf-8") -> Any:
        """Asynchronously load and parse a JSON file.

        Args:
            path: Path to the JSON file.
            encoding: File encoding (default: utf-8).

        Returns:
            Parsed JSON data.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.

        Note:
            Requires the 'aiofiles' package: pip install pyeff[async]
        """
        file_path = _to_path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")

        async with aiofiles.open(file_path, "r", encoding=encoding) as f:
            content = await f.read()
            return json.loads(content)

    async def dump_json_async(
        obj: Any,
        path: PathLike,
        encoding: str = "utf-8",
        indent: int = 2,
        ensure_ascii: bool = False,
        sort_keys: bool = False,
    ) -> None:
        """Asynchronously write an object to a JSON file.

        Args:
            obj: Python object to serialize.
            path: Destination file path.
            encoding: File encoding (default: utf-8).
            indent: Number of spaces for indentation (default: 2).
            ensure_ascii: If True, escape non-ASCII characters.
            sort_keys: If True, sort dictionary keys.

        Raises:
            TypeError: If the object is not JSON serializable.

        Note:
            Requires the 'aiofiles' package: pip install pyeff[async]
        """
        file_path = _to_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        content = json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
        async with aiofiles.open(file_path, "w", encoding=encoding) as f:
            await f.write(content)

    ASYNC_AVAILABLE = True

except ImportError:
    ASYNC_AVAILABLE = False

    async def load_json_async(path: PathLike, encoding: str = "utf-8") -> Any:
        """Async JSON loading - requires aiofiles package."""
        raise ImportError(
            "Async support requires 'aiofiles' package. "
            "Install with: pip install pyeff[async]"
        )

    async def dump_json_async(
        obj: Any,
        path: PathLike,
        encoding: str = "utf-8",
        indent: int = 2,
        ensure_ascii: bool = False,
        sort_keys: bool = False,
    ) -> None:
        """Async JSON dumping - requires aiofiles package."""
        raise ImportError(
            "Async support requires 'aiofiles' package. "
            "Install with: pip install pyeff[async]"
        )
