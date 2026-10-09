"""File system utilities with user-friendly API.

This module provides simplified file system operations including:
- copy, move, remove with pattern filtering
- directory operations (ensure, search, listdir)
- safe operations that prevent accidental deletion of root/home directories
"""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Callable, List, Literal, Optional, Union

PathLike = Union[str, Path]
Mode = Literal["all", "ignore", "include"]


class FileOperationError(Exception):
    """Base exception for file operation errors."""

    pass


class UnsafePathError(FileOperationError):
    """Raised when attempting to operate on protected paths like root or home."""

    pass


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def _validate_mode(mode: str) -> None:
    """Validate mode parameter."""
    valid_modes = ("ignore", "include", "all")
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode: {mode!r}. Must be one of {valid_modes}")


def _is_safe_path(path: PathLike) -> bool:
    """Check if a path is safe to operate on (not root or home directory)."""
    abs_path = os.path.abspath(str(path))
    unsafe_paths = ["/", os.path.expanduser("~")]
    return abs_path not in unsafe_paths


def _ensure_safe_path(path: PathLike, operation: str) -> None:
    """Raise UnsafePathError if path is root or home directory."""
    if not _is_safe_path(path):
        raise UnsafePathError(
            f"Cannot {operation} root or home directory: {path}"
        )


def ensure(target_dir: PathLike) -> Path:
    """Ensure that the specified directory exists, creating it if necessary.

    Args:
        target_dir: The directory path to ensure existence of.

    Returns:
        Path object of the ensured directory.
    """
    path = _to_path(target_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def current_dir(file: PathLike) -> Path:
    """Get the directory containing the given file.

    Args:
        file: The file path (typically __file__).

    Returns:
        Path object of the directory containing the file.

    Example:
        >>> current_dir(__file__)
        PosixPath('/path/to/current/directory')
    """
    return _to_path(file).resolve().parent


def is_empty_dir(directory: PathLike) -> bool:
    """Check if the specified directory is empty.

    Args:
        directory: The path to the directory to check.

    Returns:
        True if the directory is empty, False otherwise.

    Raises:
        NotADirectoryError: If the path is not a directory.
        FileNotFoundError: If the directory does not exist.
    """
    path = _to_path(directory)
    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    with os.scandir(path) as scan:
        return not any(scan)


def _match_files(files: List[str], patterns: List[str]) -> List[str]:
    """Match files against patterns using fnmatch."""
    matched = []
    for pattern in patterns:
        matched.extend(fnmatch.filter(files, pattern))
    return list(set(matched))


def _movetree_includes(
    src: PathLike, dst: PathLike, patterns: List[str]
) -> int:
    """Move files matching patterns from src to dst."""
    src_path = _to_path(src)
    dst_path = _to_path(dst)
    dst_path.mkdir(parents=True, exist_ok=True)

    moved_count = 0
    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)
        rel_path = root_path.relative_to(src_path)
        dest_dir = dst_path / rel_path
        dest_dir.mkdir(parents=True, exist_ok=True)

        matched_files = _match_files(files, patterns)
        for file in matched_files:
            src_file = root_path / file
            dst_file = dest_dir / file
            shutil.move(str(src_file), str(dst_file))
            moved_count += 1

        if moved_count > 0 and is_empty_dir(root_path):
            root_path.rmdir()

    return moved_count


def _movetree_ignores(
    src: PathLike, dst: PathLike, patterns: Optional[List[str]] = None
) -> int:
    """Move files NOT matching patterns from src to dst."""
    src_path = _to_path(src)
    dst_path = _to_path(dst)
    dst_path.mkdir(parents=True, exist_ok=True)

    patterns = patterns or []
    moved_count = 0

    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)
        rel_path = root_path.relative_to(src_path)
        dest_dir = dst_path / rel_path
        dest_dir.mkdir(parents=True, exist_ok=True)

        ignored_files = set(_match_files(files, patterns)) if patterns else set()
        for file in files:
            if file not in ignored_files:
                src_file = root_path / file
                dst_file = dest_dir / file
                shutil.move(str(src_file), str(dst_file))
                moved_count += 1

        if moved_count > 0 and is_empty_dir(root_path):
            root_path.rmdir()

    return moved_count


def move(
    src: PathLike,
    dst: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
) -> int:
    """Move files or directories from src to dst.

    Args:
        src: Source path (file or directory).
        dst: Destination path.
        mode: How to apply patterns:
            - "all": Move all files (patterns ignored)
            - "include": Only move files matching patterns
            - "ignore": Move files NOT matching patterns
        patterns: List of glob patterns (e.g., ["*.txt", "*.md"])

    Returns:
        Number of files moved.

    Raises:
        ValueError: If mode is invalid.
        FileNotFoundError: If source does not exist.
        UnsafePathError: If trying to move root or home directory.
    """
    _validate_mode(mode)
    src_path = _to_path(src)

    if not src_path.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    _ensure_safe_path(src, "move")
    _ensure_safe_path(dst, "move to")

    if src_path.is_file():
        dst_path = _to_path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        return 1

    if mode == "include" and patterns:
        return _movetree_includes(src, dst, patterns)
    elif mode == "ignore" and patterns:
        return _movetree_ignores(src, dst, patterns)
    else:
        return _movetree_ignores(src, dst)


def _copytree_includes(
    src: PathLike,
    dst: PathLike,
    patterns: List[str],
    dirs_exist_ok: bool = False,
) -> int:
    """Copy files matching patterns from src to dst."""
    src_path = _to_path(src)
    dst_path = _to_path(dst)

    if not dirs_exist_ok and dst_path.exists():
        raise FileExistsError(f"Destination already exists: {dst}")

    dst_path.mkdir(parents=True, exist_ok=True)
    copied_count = 0

    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)
        rel_path = root_path.relative_to(src_path)
        dest_dir = dst_path / rel_path
        dest_dir.mkdir(parents=True, exist_ok=True)

        matched_files = _match_files(files, patterns)
        for file in matched_files:
            src_file = root_path / file
            dst_file = dest_dir / file
            shutil.copy2(str(src_file), str(dst_file))
            copied_count += 1

    return copied_count


def _copytree_ignores(
    src: PathLike,
    dst: PathLike,
    patterns: Optional[List[str]] = None,
    dirs_exist_ok: bool = False,
) -> int:
    """Copy files NOT matching patterns from src to dst."""
    src_path = _to_path(src)
    dst_path = _to_path(dst)

    if not dirs_exist_ok and dst_path.exists():
        raise FileExistsError(f"Destination already exists: {dst}")

    dst_path.mkdir(parents=True, exist_ok=True)
    patterns = patterns or []
    copied_count = 0

    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)
        rel_path = root_path.relative_to(src_path)
        dest_dir = dst_path / rel_path
        dest_dir.mkdir(parents=True, exist_ok=True)

        ignored_files = set(_match_files(files, patterns)) if patterns else set()
        for file in files:
            if file not in ignored_files:
                src_file = root_path / file
                dst_file = dest_dir / file
                shutil.copy2(str(src_file), str(dst_file))
                copied_count += 1

    return copied_count


def copy(
    src: PathLike,
    dst: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    dirs_exist_ok: bool = False,
    follow_symlinks: bool = True,
    copy_metadata: bool = False,
) -> int:
    """Copy a file or directory from src to dst.

    Args:
        src: Source path (file or directory).
        dst: Destination path.
        mode: How to apply patterns:
            - "all": Copy all files (patterns ignored)
            - "include": Only copy files matching patterns
            - "ignore": Copy files NOT matching patterns
        patterns: List of glob patterns (e.g., ["*.txt", "*.md"])
        dirs_exist_ok: If True, don't raise error if dst exists.
        follow_symlinks: Whether to follow symbolic links.
        copy_metadata: Whether to copy file metadata (uses copy2 vs copy).

    Returns:
        Number of files copied.

    Raises:
        ValueError: If mode is invalid.
        FileNotFoundError: If source does not exist.
        FileExistsError: If dst exists and dirs_exist_ok is False.
    """
    _validate_mode(mode)
    src_path = _to_path(src)

    if not src_path.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    if src_path.is_file():
        dst_path = _to_path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if copy_metadata:
            shutil.copy2(str(src_path), str(dst_path), follow_symlinks=follow_symlinks)
        else:
            shutil.copy(str(src_path), str(dst_path), follow_symlinks=follow_symlinks)
        return 1

    if mode == "include" and patterns:
        return _copytree_includes(src, dst, patterns, dirs_exist_ok)
    elif mode == "ignore" and patterns:
        return _copytree_ignores(src, dst, patterns, dirs_exist_ok)
    else:
        return _copytree_ignores(src, dst, [], dirs_exist_ok)


def _removetree_includes(src: PathLike, patterns: List[str]) -> int:
    """Remove files matching patterns from src."""
    src_path = _to_path(src)
    removed_count = 0

    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)
        matched_files = _match_files(files, patterns)
        for file in matched_files:
            file_path = root_path / file
            file_path.unlink()
            removed_count += 1

    return removed_count


def _removetree_ignores(src: PathLike, patterns: List[str]) -> int:
    """Remove files NOT matching patterns from src."""
    src_path = _to_path(src)
    removed_count = 0

    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)
        ignored_files = set(_match_files(files, patterns)) if patterns else set()
        for file in files:
            if file not in ignored_files:
                file_path = root_path / file
                file_path.unlink()
                removed_count += 1

    return removed_count


def remove(
    src: Union[PathLike, List[PathLike]],
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    missing_ok: bool = True,
) -> int:
    """Remove file(s) or directory.

    Args:
        src: Path or list of paths to remove.
        mode: How to apply patterns:
            - "all": Remove all files/directory
            - "include": Only remove files matching patterns
            - "ignore": Remove files NOT matching patterns
        patterns: List of glob patterns (e.g., ["*.txt", "*.md"])
        missing_ok: If True, don't raise error if path doesn't exist.

    Returns:
        Number of files/directories removed.

    Raises:
        ValueError: If mode is invalid.
        FileNotFoundError: If path doesn't exist and missing_ok is False.
        UnsafePathError: If trying to remove root or home directory.
    """
    _validate_mode(mode)

    if isinstance(src, (list, tuple)):
        total = 0
        for item in src:
            total += _remove_single(item, mode, patterns, missing_ok)
        return total
    return _remove_single(src, mode, patterns, missing_ok)


def _remove_single(
    src: PathLike,
    mode: Mode,
    patterns: Optional[List[str]],
    missing_ok: bool,
) -> int:
    """Remove a single file or directory."""
    src_path = _to_path(src)

    if not src_path.exists():
        if missing_ok:
            return 0
        raise FileNotFoundError(f"Path not found: {src}")

    _ensure_safe_path(src, "remove")

    if mode == "include" and patterns:
        return _removetree_includes(src, patterns)
    elif mode == "ignore" and patterns:
        return _removetree_ignores(src, patterns)
    else:
        if src_path.is_file():
            src_path.unlink()
            return 1
        else:
            count = sum(1 for _ in src_path.rglob("*") if _.is_file())
            shutil.rmtree(str(src_path))
            return count + 1


def search(
    src: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
) -> List[Path]:
    """Search for files in a directory.

    Args:
        src: Directory to search in.
        mode: How to apply patterns:
            - "all": Return all files
            - "include": Only return files matching patterns
            - "ignore": Return files NOT matching patterns
        patterns: List of glob patterns (e.g., ["*.txt", "*.md"])

    Returns:
        List of Path objects for matching files.

    Raises:
        ValueError: If mode is invalid.
        FileNotFoundError: If source directory doesn't exist.
        NotADirectoryError: If source is not a directory.
    """
    _validate_mode(mode)
    src_path = _to_path(src)

    if not src_path.exists():
        raise FileNotFoundError(f"Directory not found: {src}")
    if not src_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {src}")

    results: List[Path] = []
    patterns = patterns or []

    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)

        if mode == "include" and patterns:
            matched = _match_files(files, patterns)
            results.extend(root_path / f for f in matched)
        elif mode == "ignore" and patterns:
            ignored = set(_match_files(files, patterns))
            results.extend(root_path / f for f in files if f not in ignored)
        else:
            results.extend(root_path / f for f in files)

    return results


def listdir(
    source_dir: PathLike,
    extensions: Optional[List[str]] = None,
    sort: bool = True,
    abs_path: bool = True,
) -> List[Path]:
    """List files in a directory.

    Args:
        source_dir: Directory to list files from.
        extensions: List of extensions to filter by (e.g., [".txt", ".md"]).
        sort: Whether to sort the results alphabetically.
        abs_path: Whether to return absolute paths.

    Returns:
        List of Path objects for files in the directory.

    Raises:
        FileNotFoundError: If directory doesn't exist.
        NotADirectoryError: If path is not a directory.
    """
    dir_path = _to_path(source_dir)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {source_dir}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {source_dir}")

    extensions = extensions or []
    files = list(dir_path.iterdir())

    if extensions:
        files = [f for f in files if f.suffix in extensions or f.name.endswith(tuple(extensions))]

    if abs_path:
        files = [f.resolve() for f in files]

    if sort:
        files = sorted(files)

    return files


def exists(path: PathLike) -> bool:
    """Check if a path exists.

    Args:
        path: Path to check.

    Returns:
        True if the path exists, False otherwise.
    """
    return _to_path(path).exists()


def file_size(path: PathLike) -> int:
    """Get the size of a file in bytes.

    Args:
        path: Path to the file.

    Returns:
        Size of the file in bytes.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        IsADirectoryError: If the path is a directory.
    """
    file_path = _to_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if file_path.is_dir():
        raise IsADirectoryError(f"Path is a directory: {path}")
    return file_path.stat().st_size


def tree(
    path: PathLike,
    max_depth: Optional[int] = None,
    show_hidden: bool = False,
    prefix: str = "",
) -> str:
    """Generate a tree representation of a directory structure.

    Args:
        path: Root directory path.
        max_depth: Maximum depth to traverse (None for unlimited).
        show_hidden: Whether to show hidden files (starting with .).
        prefix: Internal use for recursive formatting.

    Returns:
        String representation of the directory tree.

    Raises:
        FileNotFoundError: If the path doesn't exist.
        NotADirectoryError: If the path is not a directory.
    """
    root_path = _to_path(path)

    if not root_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    def _tree_recursive(dir_path: Path, prefix: str, depth: int) -> List[str]:
        if max_depth is not None and depth > max_depth:
            return []

        lines = []
        entries = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))

        if not show_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                lines.extend(_tree_recursive(entry, prefix + extension, depth + 1))

        return lines

    result = [str(root_path)]
    result.extend(_tree_recursive(root_path, "", 0))
    return "\n".join(result)


def walk(
    path: PathLike,
    file_filter: Optional[Callable[[Path], bool]] = None,
    dir_filter: Optional[Callable[[Path], bool]] = None,
) -> List[Path]:
    """Walk through a directory tree and return all matching files.

    Args:
        path: Root directory to walk.
        file_filter: Optional function to filter files (returns True to include).
        dir_filter: Optional function to filter directories (returns True to descend).

    Returns:
        List of Path objects for all matching files.

    Raises:
        FileNotFoundError: If the path doesn't exist.
        NotADirectoryError: If the path is not a directory.
    """
    root_path = _to_path(path)

    if not root_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    results: List[Path] = []

    for root, dirs, files in os.walk(root_path):
        root_p = Path(root)

        if dir_filter:
            dirs[:] = [d for d in dirs if dir_filter(root_p / d)]

        for file in files:
            file_path = root_p / file
            if file_filter is None or file_filter(file_path):
                results.append(file_path)

    return results
