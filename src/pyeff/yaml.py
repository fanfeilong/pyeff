"""YAML file utilities with user-friendly API.

This module provides simplified YAML file operations with:
- Support for !include / !inc directives
- Type hints for better IDE support
- Proper exception handling
- Optional async support (requires aiofiles)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Union

import yaml
import yaml_include

PathLike = Union[str, Path]


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def load_yaml_full(
    yaml_file: PathLike,
    base_path: PathLike,
    encoding: str = "utf-8",
) -> Any:
    """Load a YAML file with support for !include / !inc directives.

    This function processes YAML files that contain include directives,
    resolving them relative to the specified base path.

    Args:
        yaml_file: Path to the YAML file to load.
        base_path: Base directory for resolving include paths.
        encoding: File encoding (default: utf-8).

    Returns:
        Parsed YAML data with included files resolved.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.

    Example:
        >>> # config.yml contains: data: !include data.yml
        >>> config = load_yaml_full("config.yml", "./configs")
    """
    file_path = _to_path(yaml_file)
    base = _to_path(base_path)

    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    yaml.add_constructor("!inc", yaml_include.Constructor(base_dir=str(base)))
    yaml.add_constructor("!include", yaml_include.Constructor(base_dir=str(base)))

    with open(file_path, "r", encoding=encoding) as f:
        return yaml.full_load(f)


def load_yaml_safe(
    yaml_file: PathLike,
    encoding: str = "utf-8",
) -> Any:
    """Safely load a YAML file without executing include directives.

    Include directives (!include, !inc) are ignored and return None.
    This is useful when you want to load YAML without resolving includes.

    Args:
        yaml_file: Path to the YAML file to load.
        encoding: File encoding (default: utf-8).

    Returns:
        Parsed YAML data (includes return None).

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    file_path = _to_path(yaml_file)

    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    yaml.add_constructor("!include", lambda loader, node: None, Loader=yaml.SafeLoader)
    yaml.add_constructor("!inc", lambda loader, node: None, Loader=yaml.SafeLoader)

    with open(file_path, "r", encoding=encoding) as f:
        return yaml.safe_load(f)


def load_yaml(
    yaml_file: PathLike,
    encoding: str = "utf-8",
) -> Any:
    """Load a YAML file using safe loader.

    This is an alias for load_yaml_safe() for simpler API.

    Args:
        yaml_file: Path to the YAML file to load.
        encoding: File encoding (default: utf-8).

    Returns:
        Parsed YAML data.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    return load_yaml_safe(yaml_file, encoding)


def dump_yaml(
    obj: Any,
    yaml_file: PathLike,
    encoding: str = "utf-8",
    sort_keys: bool = False,
    default_flow_style: bool = False,
    allow_unicode: bool = True,
) -> None:
    """Write an object to a YAML file.

    Args:
        obj: Python object to serialize.
        yaml_file: Destination file path.
        encoding: File encoding (default: utf-8).
        sort_keys: If True, sort dictionary keys (default: False).
        default_flow_style: If True, use flow style (default: False).
        allow_unicode: If True, allow unicode characters (default: True).

    Raises:
        yaml.YAMLError: If the object cannot be serialized.
    """
    file_path = _to_path(yaml_file)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding=encoding) as f:
        yaml.dump(
            obj,
            f,
            sort_keys=sort_keys,
            default_flow_style=default_flow_style,
            allow_unicode=allow_unicode,
        )


def loads(s: str) -> Any:
    """Parse a YAML string.

    Args:
        s: YAML string to parse.

    Returns:
        Parsed YAML data.

    Raises:
        yaml.YAMLError: If the string contains invalid YAML.
    """
    return yaml.safe_load(s)


def dumps(
    obj: Any,
    sort_keys: bool = False,
    default_flow_style: bool = False,
    allow_unicode: bool = True,
) -> str:
    """Serialize an object to a YAML string.

    Args:
        obj: Python object to serialize.
        sort_keys: If True, sort dictionary keys.
        default_flow_style: If True, use flow style.
        allow_unicode: If True, allow unicode characters.

    Returns:
        YAML string representation.

    Raises:
        yaml.YAMLError: If the object cannot be serialized.
    """
    return yaml.dump(
        obj,
        sort_keys=sort_keys,
        default_flow_style=default_flow_style,
        allow_unicode=allow_unicode,
    )


def load_yaml_all(
    yaml_file: PathLike,
    encoding: str = "utf-8",
) -> List[Any]:
    """Load all documents from a multi-document YAML file.

    Args:
        yaml_file: Path to the YAML file.
        encoding: File encoding (default: utf-8).

    Returns:
        List of parsed YAML documents.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    file_path = _to_path(yaml_file)

    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    with open(file_path, "r", encoding=encoding) as f:
        return list(yaml.safe_load_all(f))


def dump_yaml_all(
    objects: List[Any],
    yaml_file: PathLike,
    encoding: str = "utf-8",
    sort_keys: bool = False,
) -> None:
    """Write multiple documents to a YAML file.

    Args:
        objects: List of Python objects to serialize.
        yaml_file: Destination file path.
        encoding: File encoding (default: utf-8).
        sort_keys: If True, sort dictionary keys.

    Raises:
        yaml.YAMLError: If an object cannot be serialized.
    """
    file_path = _to_path(yaml_file)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding=encoding) as f:
        yaml.dump_all(objects, f, sort_keys=sort_keys, allow_unicode=True)


def update_yaml_key(
    yaml_file: PathLike,
    key: str,
    value: Any,
    encoding: str = "utf-8",
) -> None:
    """Update or add a top-level key in a YAML file.

    This preserves the existing file content and adds/updates the key.
    Note: This is a simple implementation that appends to the file.

    Args:
        yaml_file: Path to the YAML file.
        key: Key to update or add.
        value: Value to set.
        encoding: File encoding (default: utf-8).

    Raises:
        FileNotFoundError: If the YAML file does not exist.
    """
    file_path = _to_path(yaml_file)

    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    data = load_yaml_safe(yaml_file, encoding)
    if data is None:
        data = {}

    data[key] = value
    dump_yaml(data, yaml_file, encoding)


def override_yaml_top_key(
    yaml_file: PathLike,
    key: str,
    value: Any,
) -> None:
    """Append or update a key-value pair at the top level of a YAML file.

    This is a legacy function that appends directly to the file.
    Consider using update_yaml_key() for safer operations.

    Args:
        yaml_file: Path to the YAML file to modify.
        key: Key to add or update.
        value: Value to set.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
    """
    file_path = _to_path(yaml_file)

    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lines.append(f"\n{key}: {value}\n")

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


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

    async def load_yaml_async(
        yaml_file: PathLike,
        encoding: str = "utf-8",
    ) -> Any:
        """Asynchronously load a YAML file.

        Args:
            yaml_file: Path to the YAML file.
            encoding: File encoding (default: utf-8).

        Returns:
            Parsed YAML data.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            yaml.YAMLError: If the file contains invalid YAML.

        Note:
            Requires the 'aiofiles' package: pip install pyeff[async]
        """
        file_path = _to_path(yaml_file)

        if not file_path.exists():
            raise FileNotFoundError(f"YAML file not found: {yaml_file}")

        async with aiofiles.open(file_path, "r", encoding=encoding) as f:
            content = await f.read()
            return yaml.safe_load(content)

    async def dump_yaml_async(
        obj: Any,
        yaml_file: PathLike,
        encoding: str = "utf-8",
        sort_keys: bool = False,
    ) -> None:
        """Asynchronously write an object to a YAML file.

        Args:
            obj: Python object to serialize.
            yaml_file: Destination file path.
            encoding: File encoding (default: utf-8).
            sort_keys: If True, sort dictionary keys.

        Note:
            Requires the 'aiofiles' package: pip install pyeff[async]
        """
        file_path = _to_path(yaml_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        content = yaml.dump(obj, sort_keys=sort_keys, allow_unicode=True)
        async with aiofiles.open(file_path, "w", encoding=encoding) as f:
            await f.write(content)

    ASYNC_AVAILABLE = True

except ImportError:
    ASYNC_AVAILABLE = False

    async def load_yaml_async(yaml_file: PathLike, encoding: str = "utf-8") -> Any:
        """Async YAML loading - requires aiofiles package."""
        raise ImportError(
            "Async support requires 'aiofiles' package. "
            "Install with: pip install pyeff[async]"
        )

    async def dump_yaml_async(
        obj: Any,
        yaml_file: PathLike,
        encoding: str = "utf-8",
        sort_keys: bool = False,
    ) -> None:
        """Async YAML dumping - requires aiofiles package."""
        raise ImportError(
            "Async support requires 'aiofiles' package. "
            "Install with: pip install pyeff[async]"
        )
