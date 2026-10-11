"""Local file system operations (alias for fs module).

This module provides a consistent interface for local file operations,
matching the API style of docker and ssh modules.

Example:
    >>> from pyeff import local
    >>> 
    >>> local.copy("./src", "./dst", mode="ignore", patterns=["*.pyc"])
    >>> local.remove("./temp")
    >>> files = local.search("./data", patterns=["*.csv"])
"""

from __future__ import annotations

from .fs import (
    copy,
    move,
    remove,
    search,
    search_iter,
    listdir,
    listdir_iter,
    walk,
    walk_iter,
    exists,
    ensure,
    is_empty_dir,
    file_size,
    tree,
    current_dir,
    FileOperationError,
    UnsafePathError,
)

from .lines import (
    load_all_text as read_text,
    dump_all_text as write_text,
    load_lines as read_lines,
    dump_lines as write_lines,
)

__all__ = [
    "copy",
    "move",
    "remove",
    "search",
    "search_iter",
    "listdir",
    "listdir_iter",
    "walk",
    "walk_iter",
    "exists",
    "ensure",
    "is_empty_dir",
    "file_size",
    "tree",
    "current_dir",
    "read_text",
    "write_text",
    "read_lines",
    "write_lines",
    "FileOperationError",
    "UnsafePathError",
]
