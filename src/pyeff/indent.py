"""Indentation detection utilities.

This module provides utilities for detecting and working with
code indentation patterns.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

PathLike = Union[str, Path]


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def get_python_file_func_indent_spaces(
    filepath: PathLike,
    func: str,
    encoding: str = "utf-8",
) -> str:
    """Get the indentation used inside a Python function.

    This function finds the specified function definition and returns
    the whitespace used for the first indented line within it.

    Args:
        filepath: Path to the Python file.
        func: Name of the function to find (e.g., "def my_func").
        encoding: File encoding (default: utf-8).

    Returns:
        String of spaces/tabs representing the indentation.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the function is not found or has no indented lines.
    """
    path = _to_path(filepath)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(path, "r", encoding=encoding) as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        if stripped and stripped.startswith(func):
            i += 1
            while i < len(lines):
                line = lines[i]
                stripped = line.lstrip()

                if stripped:
                    pos = line.find(stripped)
                    if pos > 0:
                        return line[:pos]

                i += 1

        i += 1

    raise ValueError(f"No indented lines found for function: {func}")


def detect_indent(lines: List[str]) -> str:
    """Detect the indentation style used in a list of lines.

    Examines lines to find the most common indentation unit.

    Args:
        lines: List of code lines to examine.

    Returns:
        String representing the indentation unit (spaces or tabs).

    Raises:
        ValueError: If no indentation can be detected.
    """
    indents: List[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped and line != stripped:
            indent = line[: len(line) - len(stripped)]
            if indent:
                indents.append(indent)

    if not indents:
        raise ValueError("No indentation found in lines")

    min_indent = min(indents, key=len)

    if "\t" in min_indent:
        return "\t"

    return min_indent


def normalize_indent(
    lines: List[str],
    indent: str = "    ",
) -> List[str]:
    """Normalize indentation in lines to use a consistent style.

    Args:
        lines: Lines to normalize.
        indent: Target indentation string (default: 4 spaces).

    Returns:
        List of lines with normalized indentation.
    """
    try:
        current_indent = detect_indent(lines)
    except ValueError:
        return lines

    result: List[str] = []
    for line in lines:
        if not line.strip():
            result.append(line)
            continue

        leading = line[: len(line) - len(line.lstrip())]
        content = line.lstrip()

        if current_indent:
            level = leading.count(current_indent)
            new_leading = indent * level
        else:
            new_leading = ""

        result.append(new_leading + content)

    return result


def get_indent_level(line: str, indent_unit: Optional[str] = None) -> int:
    """Get the indentation level of a line.

    Args:
        line: Line to analyze.
        indent_unit: Indentation unit (auto-detect if None).

    Returns:
        Number of indentation levels.
    """
    if not line or not line.strip():
        return 0

    leading = line[: len(line) - len(line.lstrip())]

    if indent_unit is None:
        if "\t" in leading:
            return leading.count("\t")
        else:
            space_count = len(leading)
            return space_count // 4 if space_count else 0

    return leading.count(indent_unit)


def expand_tabs(lines: List[str], tabsize: int = 4) -> List[str]:
    """Expand tabs to spaces.

    Args:
        lines: Lines to process.
        tabsize: Number of spaces per tab (default: 4).

    Returns:
        Lines with tabs expanded to spaces.
    """
    return [line.expandtabs(tabsize) for line in lines]


def convert_to_tabs(lines: List[str], spaces: int = 4) -> List[str]:
    """Convert leading spaces to tabs.

    Args:
        lines: Lines to process.
        spaces: Number of spaces per tab (default: 4).

    Returns:
        Lines with leading spaces converted to tabs.
    """
    result: List[str] = []
    space_pattern = " " * spaces

    for line in lines:
        if not line.strip():
            result.append(line)
            continue

        leading = line[: len(line) - len(line.lstrip())]
        content = line.lstrip()

        tab_count = leading.count(space_pattern)
        remaining_spaces = len(leading) - (tab_count * spaces)
        new_leading = "\t" * tab_count + " " * remaining_spaces

        result.append(new_leading + content)

    return result
