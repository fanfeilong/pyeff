"""Text line manipulation utilities.

This module provides utilities for working with text files line by line:
- Loading and saving lines
- Splitting lines by patterns
- Structured parsing based on indentation
- Pattern matching and extraction
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, TypedDict, Union

PathLike = Union[str, Path]


class Block(TypedDict, total=False):
    """Represents a parsed block of code/text."""

    name: str
    pattern: Optional[str]
    lines: List[str]
    body: List["Block"]
    indent: int


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def load_all_text(file_name: PathLike, encoding: str = "utf-8") -> str:
    """Load and return the entire content of a text file.

    Args:
        file_name: Path to the text file.
        encoding: File encoding (default: utf-8).

    Returns:
        The contents of the file as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    file_path = _to_path(file_name)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_name}")

    with open(file_path, "r", encoding=encoding) as f:
        return f.read()


def dump_all_text(
    content: str,
    file_name: PathLike,
    encoding: str = "utf-8",
) -> None:
    """Write content to a file.

    Args:
        content: Text content to write.
        file_name: Destination file path.
        encoding: File encoding (default: utf-8).
    """
    file_path = _to_path(file_name)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding=encoding) as f:
        f.write(content)


def load_lines(
    file_name: PathLike,
    remove_newline: bool = False,
    encoding: str = "utf-8",
) -> List[str]:
    """Load lines from a text file.

    Args:
        file_name: Path to the text file.
        remove_newline: If True, strip trailing newline from each line.
        encoding: File encoding (default: utf-8).

    Returns:
        List of lines from the file.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    file_path = _to_path(file_name)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_name}")

    with open(file_path, "r", encoding=encoding) as f:
        lines = f.readlines()

    if remove_newline:
        lines = [line.rstrip("\n") for line in lines]

    return lines


def dump_lines(
    lines: List[str],
    file_name: PathLike,
    append_newline: bool = False,
    encoding: str = "utf-8",
) -> None:
    """Write lines to a file.

    Args:
        lines: List of lines to write.
        file_name: Destination file path.
        append_newline: If True, append newline to each line.
        encoding: File encoding (default: utf-8).
    """
    file_path = _to_path(file_name)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if append_newline:
        lines = [line + "\n" for line in lines]

    with open(file_path, "w", encoding=encoding) as f:
        f.writelines(lines)


def split(lines: List[str], *patterns: Union[str, Pattern[str]]) -> List[List[str]]:
    """Split lines into groups based on pattern matches.

    Lines matching any pattern start a new group.

    Args:
        lines: List of lines to split.
        patterns: Regex patterns (strings or compiled patterns).

    Returns:
        List of line groups.

    Example:
        >>> split(["# Header", "line1", "# Another", "line2"], r"^#.*")
        [['# Header', 'line1'], ['# Another', 'line2']]
    """
    compiled_patterns: List[Pattern[str]] = []
    for pattern in patterns:
        if isinstance(pattern, str):
            compiled_patterns.append(re.compile(pattern))
        else:
            compiled_patterns.append(pattern)

    result: List[List[str]] = [[]]

    for line in lines:
        matched = False
        for pattern in compiled_patterns:
            if re.match(pattern, line):
                result.append([line])
                matched = True
                break

        if not matched:
            result[-1].append(line)

    return [group for group in result if group]


def split_struct(
    lines: List[str],
    pattern_dict: Dict[str, Dict[str, Any]],
    calc_indent: Callable[[Block, List[Block], int], int],
) -> List[Block]:
    """Parse lines into structured blocks based on patterns and indentation.

    This function parses text into a hierarchical structure based on
    pattern matching and indentation levels.

    Args:
        lines: Lines to parse.
        pattern_dict: Dictionary mapping block names to pattern specs.
            Each spec has a "pattern" key with string or list of patterns.
        calc_indent: Function to calculate block indentation.
            Takes (block, preceding_blocks, current_indent) -> indent level.

    Returns:
        List of top-level blocks with nested body blocks.

    Example:
        >>> pattern_dict = {
        ...     "function": {"pattern": r"^def\\s+.*"},
        ...     "class": {"pattern": r"^class\\s+.*"},
        ... }
        >>> def calc_indent(block, pre, cur):
        ...     return len(block["lines"][0]) - len(block["lines"][0].lstrip())
        >>> blocks = split_struct(code_lines, pattern_dict, calc_indent)
    """
    current_block: Block = {"name": "top", "pattern": None, "lines": [], "body": []}
    block_stack: List[Block] = [current_block]

    for line in lines:
        for name, item in pattern_dict.items():
            pattern = item["pattern"]
            patterns_list: List[str] = []

            if isinstance(pattern, str):
                patterns_list.append(pattern)
            elif isinstance(pattern, list):
                patterns_list.extend(pattern)

            matched = False
            for p in patterns_list:
                if re.match(p, line):
                    current_block = {
                        "name": name,
                        "pattern": pattern,
                        "lines": [],
                        "body": [],
                    }
                    block_stack.append(current_block)
                    matched = True
                    break

            if matched:
                break

        current_block["lines"].append(line)

    i = 0
    cur_indent = 0
    cur_depth = 0
    indent_depth_map: Dict[int, int] = {}
    pre_indent_last_block_stack: List[Optional[Block]] = []
    pre_indent_last_block: Optional[Block] = None
    cur_indent_last_block: Optional[Block] = None

    top_indent: Optional[int] = None
    top_blocks: List[Block] = []

    while i < len(block_stack):
        pre_blocks = block_stack[0:i]
        block = block_stack[i]
        block_indent = calc_indent(block, pre_blocks, cur_indent)
        block["indent"] = block_indent

        if block_indent < 0:
            i += 1
            continue

        if top_indent is None:
            top_indent = block_indent
            cur_depth = 0
            indent_depth_map[block_indent] = cur_depth
            cur_indent = block_indent

        if block_indent > cur_indent:
            if pre_indent_last_block:
                pre_indent_last_block["body"].append(block)
            elif cur_indent_last_block:
                cur_indent_last_block["body"].append(block)

            pre_indent_last_block_stack.append(pre_indent_last_block)
            pre_indent_last_block = cur_indent_last_block
            cur_indent_last_block = block

            cur_depth += 1
            indent_depth_map[block_indent] = cur_depth

        elif block_indent < cur_indent:
            target_depth = indent_depth_map.get(block_indent, 0)
            offset = cur_depth - target_depth

            for _ in range(offset):
                if pre_indent_last_block_stack:
                    pre_indent_last_block = pre_indent_last_block_stack.pop()
                else:
                    pre_indent_last_block = None
                cur_depth -= 1

            cur_indent_last_block = block

            if pre_indent_last_block:
                pre_indent_last_block["body"].append(block)
        else:
            cur_indent_last_block = block

            if pre_indent_last_block:
                pre_indent_last_block["body"].append(block)

        cur_indent = block_indent

        if top_indent is not None and block_indent == top_indent:
            top_blocks.append(block)

        i += 1

    return top_blocks


def py_tabspaces(lines: List[str]) -> str:
    """Detect the indentation style used in Python code.

    Examines lines to find the leading whitespace of the first indented line.

    Args:
        lines: List of code lines to examine.

    Returns:
        String representing the indentation (spaces or tabs).

    Raises:
        ValueError: If no indented lines are found.
    """
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            pos = line.find(stripped)
            if pos > 0:
                tab_spaces = []
                for char in line[:pos]:
                    if char in (" ", "\t"):
                        tab_spaces.append(char)
                return "".join(tab_spaces)

    raise ValueError("No indented lines found.")


def insert(
    source_lines: List[str],
    insert_lines: List[str],
    patterns: List[str],
    append_newline: bool = False,
    insert_before: bool = False,
) -> List[str]:
    """Insert lines before or after lines matching patterns.

    Args:
        source_lines: Original lines.
        insert_lines: Lines to insert.
        patterns: Regex patterns to match.
        append_newline: If True, append newline to inserted lines.
        insert_before: If True, insert before match; otherwise after.

    Returns:
        Modified list of lines.
    """
    new_lines: List[str] = []

    for line in source_lines:
        is_match = any(re.search(pattern, line) for pattern in patterns)

        if is_match:
            if not insert_before:
                new_lines.append(line)

            for insert_line in insert_lines:
                if append_newline:
                    insert_line = insert_line + "\n"
                new_lines.append(insert_line)

            if insert_before:
                new_lines.append(line)
        else:
            new_lines.append(line)

    return new_lines


def find(lines: List[str], *patterns: str) -> bool:
    """Check if any line matches any of the given patterns.

    Args:
        lines: Lines to search.
        patterns: Regex patterns to match.

    Returns:
        True if any line matches any pattern.
    """
    for line in lines:
        for pattern in patterns:
            if re.match(pattern, line):
                return True
    return False


def find_index(lines: List[str], *patterns: str) -> int:
    """Find the index of the first line matching any pattern.

    Args:
        lines: Lines to search.
        patterns: Regex patterns to match.

    Returns:
        Index of first matching line, or -1 if not found.
    """
    for i, line in enumerate(lines):
        for pattern in patterns:
            if re.match(pattern, line):
                return i
    return -1


def grep(lines: List[str], pattern: str, invert: bool = False) -> List[str]:
    """Filter lines matching a pattern.

    Args:
        lines: Lines to filter.
        pattern: Regex pattern to match.
        invert: If True, return non-matching lines.

    Returns:
        List of matching (or non-matching) lines.
    """
    compiled = re.compile(pattern)
    if invert:
        return [line for line in lines if not compiled.search(line)]
    return [line for line in lines if compiled.search(line)]


def replace(
    lines: List[str],
    pattern: str,
    replacement: str,
    count: int = 0,
) -> List[str]:
    """Replace pattern matches in lines.

    Args:
        lines: Lines to process.
        pattern: Regex pattern to match.
        replacement: Replacement string.
        count: Max replacements per line (0 for all).

    Returns:
        List of lines with replacements made.
    """
    compiled = re.compile(pattern)
    return [compiled.sub(replacement, line, count=count) for line in lines]


def pair_match(
    lines: List[str],
    first: Callable[[str], bool],
    second: Callable[[str], bool],
) -> Tuple[bool, int]:
    """Find a pair of consecutive lines where first matches one and second matches next.

    Args:
        lines: Lines to search.
        first: Predicate for first line.
        second: Predicate for second line.

    Returns:
        Tuple of (found, index of second line).
    """
    for i in range(len(lines) - 1):
        if first(lines[i]) and second(lines[i]):
            return True, i

        if first(lines[i]) and second(lines[i + 1]):
            return True, i + 1

    return False, 0


def continue_match(
    lines: List[str],
    first: Callable[[str], bool],
    second: Callable[[str], bool],
) -> Tuple[bool, int]:
    """Find where first condition is met, followed eventually by second.

    Args:
        lines: Lines to search.
        first: Predicate for start condition.
        second: Predicate for end condition.

    Returns:
        Tuple of (found, index of line matching second).
    """
    match_count = 0

    for i, line in enumerate(lines):
        if first(line):
            match_count += 1

        if second(line):
            if match_count == 1:
                return True, i
            match_count = 0

    return False, 0


def extract(
    lines: List[str],
    start: Callable[[str], bool],
    finish: Callable[[str], bool],
) -> Tuple[List[str], int]:
    """Extract lines from start condition to finish condition.

    Args:
        lines: Lines to extract from.
        start: Predicate for start line.
        finish: Predicate for end line.

    Returns:
        Tuple of (extracted lines, end index).
    """
    results: List[str] = []
    enter = False
    j = 0

    while j < len(lines):
        line = lines[j]
        is_enter = False

        if not enter and start(line):
            enter = True
            is_enter = True

        if enter:
            results.append(line)

        if not is_enter and enter and finish(line):
            break

        j += 1

    return results, j


def count_indent(line: str) -> int:
    """Count the leading whitespace characters in a line.

    Args:
        line: Line to analyze.

    Returns:
        Number of leading whitespace characters.
    """
    return len(line) - len(line.lstrip())


def dedent(lines: List[str], spaces: Optional[int] = None) -> List[str]:
    """Remove common leading whitespace from lines.

    Args:
        lines: Lines to dedent.
        spaces: Number of spaces to remove (None for auto-detect).

    Returns:
        Dedented lines.
    """
    if not lines:
        return lines

    if spaces is None:
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return lines
        spaces = min(count_indent(line) for line in non_empty)

    return [line[spaces:] if len(line) > spaces else line for line in lines]


def indent(lines: List[str], prefix: str = "    ") -> List[str]:
    """Add indentation to lines.

    Args:
        lines: Lines to indent.
        prefix: String to prepend to each line.

    Returns:
        Indented lines.
    """
    return [prefix + line if line.strip() else line for line in lines]
