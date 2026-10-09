"""Logging utilities for structured output.

This module provides utilities for formatted logging output:
- Section headers and tables
- File content logging
- Visual separators
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

from loguru import logger

PathLike = Union[str, Path]


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def logger_file_info(
    file_path: PathLike,
    skip_empty: bool = True,
    encoding: str = "utf-8",
) -> None:
    """Log the contents of a file with a header.

    Args:
        file_path: Path to the file to log.
        skip_empty: If True, skip empty lines.
        encoding: File encoding (default: utf-8).

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = _to_path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    logger_table_begin(f"show file: {file_path}")

    with open(path, "r", encoding=encoding) as f:
        for line in f:
            line = line.rstrip("\n")
            if skip_empty and not line.strip():
                continue
            logger.info(line)

    logger_table_end()


def logger_section(
    content: Union[str, Iterable[str]],
    separator: str = "---------------",
) -> None:
    """Log content within visual separators.

    Args:
        content: String or iterable of strings to log.
        separator: Separator line style.
    """
    logger.info("")
    logger.info(separator)

    if isinstance(content, str):
        logger.info(content)
    else:
        for line in content:
            logger.info(line)

    logger.info(separator)


def logger_table_begin(
    title: str,
    separator: str = "---------------",
) -> None:
    """Begin a logging section with a title.

    Args:
        title: Section title.
        separator: Separator line style.
    """
    logger.info("")
    logger.info(separator)
    logger.info(title)
    logger.info(separator)


def logger_table_end(
    tail_title: Optional[str] = None,
    separator: str = "---------------",
) -> None:
    """End a logging section.

    Args:
        tail_title: Optional closing title.
        separator: Separator line style.
    """
    logger.info(separator)
    if tail_title is not None:
        logger.info(tail_title)
    logger.info("")


def logger_list(
    items: Iterable[str],
    title: Optional[str] = None,
    prefix: str = "  - ",
) -> None:
    """Log a list of items.

    Args:
        items: Items to log.
        title: Optional title before the list.
        prefix: Prefix for each item.
    """
    if title:
        logger.info(title)

    for item in items:
        logger.info(f"{prefix}{item}")


def logger_dict(
    data: dict,
    title: Optional[str] = None,
    indent: int = 2,
) -> None:
    """Log a dictionary in a readable format.

    Args:
        data: Dictionary to log.
        title: Optional title before the dict.
        indent: Number of spaces for indentation.
    """
    if title:
        logger.info(title)

    def _log_dict(d: dict, level: int = 0) -> None:
        prefix = " " * (level * indent)
        for key, value in d.items():
            if isinstance(value, dict):
                logger.info(f"{prefix}{key}:")
                _log_dict(value, level + 1)
            else:
                logger.info(f"{prefix}{key}: {value}")

    _log_dict(data)


def logger_separator(
    char: str = "-",
    length: int = 50,
) -> None:
    """Log a separator line.

    Args:
        char: Character to use for separator.
        length: Length of separator line.
    """
    logger.info(char * length)


def logger_blank(count: int = 1) -> None:
    """Log blank lines.

    Args:
        count: Number of blank lines.
    """
    for _ in range(count):
        logger.info("")
