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

from .uri import URIPath, resolve_path, join_uri, LocalPath

PathLike = Union[str, Path, URIPath]


def _to_path(p: Union[str, Path]) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def _read_text(path: PathLike, encoding: str = "utf-8") -> str:
    from .ops import read
    return read(path, encoding=encoding)  # type: ignore[return-value]


def _write_text(path: PathLike, content: str, encoding: str = "utf-8") -> None:
    from .ops import write
    write(path, content, encoding=encoding)


def load_yaml_full(
    yaml_file: PathLike,
    base_path: PathLike,
    encoding: str = "utf-8",
) -> Any:
    """Load a YAML file with support for !include / !inc directives.

    Include paths are resolved relative to *base_path*, which may be a
    local directory or any URI-backed directory.

    Example:
        >>> # config.yml contains: data: !include data.yml
        >>> config = load_yaml_full("config.yml", "./configs")
        >>> config = load_yaml_full(
        ...     "archive:./bundle.zip:/config.yml",
        ...     "archive:./bundle.zip:/",
        ... )
    """
    content = _read_text(yaml_file, encoding)
    base = resolve_path(base_path)

    if isinstance(base, LocalPath):
        local_base = str(Path(base.path))
        yaml.add_constructor("!inc", yaml_include.Constructor(base_dir=local_base))
        yaml.add_constructor("!include", yaml_include.Constructor(base_dir=local_base))
        return yaml.full_load(content)

    def _include_constructor(loader: Any, node: Any) -> Any:
        rel = loader.construct_scalar(node)
        included = _read_text(join_uri(base, rel), encoding)
        return yaml.safe_load(included)

    loader = yaml.FullLoader
    yaml.add_constructor("!inc", _include_constructor, Loader=loader)
    yaml.add_constructor("!include", _include_constructor, Loader=loader)
    return yaml.load(content, Loader=loader)


def load_yaml_safe(
    yaml_file: PathLike,
    encoding: str = "utf-8",
) -> Any:
    """Safely load a YAML file without executing include directives.

    Include directives (!include, !inc) are ignored and return None.
    Supports local paths and URI backends.
    """
    content = _read_text(yaml_file, encoding)

    yaml.add_constructor("!include", lambda loader, node: None, Loader=yaml.SafeLoader)
    yaml.add_constructor("!inc", lambda loader, node: None, Loader=yaml.SafeLoader)

    return yaml.safe_load(content)


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
    """Write an object to a YAML file (local path or URI)."""
    content = yaml.dump(
        obj,
        sort_keys=sort_keys,
        default_flow_style=default_flow_style,
        allow_unicode=allow_unicode,
    )
    _write_text(yaml_file, content, encoding=encoding)


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
    """Load all documents from a multi-document YAML file (local or URI)."""
    content = _read_text(yaml_file, encoding)
    return list(yaml.safe_load_all(content))


def dump_yaml_all(
    objects: List[Any],
    yaml_file: PathLike,
    encoding: str = "utf-8",
    sort_keys: bool = False,
) -> None:
    """Write multiple documents to a YAML file (local or URI)."""
    content = yaml.dump_all(objects, sort_keys=sort_keys, allow_unicode=True)
    _write_text(yaml_file, content, encoding=encoding)


def update_yaml_key(
    yaml_file: PathLike,
    key: str,
    value: Any,
    encoding: str = "utf-8",
) -> None:
    """Update or add a top-level key in a YAML file (local or URI)."""
    from .ops import exists
    if not exists(yaml_file):
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
    """Append a key-value pair at the top level of a YAML file (local or URI)."""
    from .ops import exists
    if not exists(yaml_file):
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    content = _read_text(yaml_file, "utf-8")
    if content and not content.endswith("\n"):
        content += "\n"
    content += f"\n{key}: {value}\n"
    _write_text(yaml_file, content, "utf-8")


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
