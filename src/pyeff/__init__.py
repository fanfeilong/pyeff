"""pyeff - User-friendly Python utilities for daily coding tasks.

This library provides simplified APIs for common operations:
- fs: File system operations (copy, move, remove, search)
- json: JSON file reading and writing
- yaml: YAML file handling with include support
- lines: Text line manipulation and parsing
- shell: Shell command execution
- logger: Structured logging output
- hash: String and file hashing
- git: Git repository utilities
- indent: Indentation detection and manipulation
"""

from __future__ import annotations

__version__ = "0.2.0"
__author__ = "Fan Fei Long"
__email__ = "fanfeilong@gmail.com"

from . import archive
from . import fs
from . import git
from . import hash
from . import indent
from . import json
from . import lines
from . import logger
from . import shell
from . import yaml

from .fs import (
    clear_pattern_cache,
    copy,
    current_dir,
    ensure,
    exists,
    file_size,
    is_empty_dir,
    listdir,
    listdir_iter,
    move,
    remove,
    search,
    search_iter,
    tree,
    walk,
    walk_iter,
    FileOperationError,
    UnsafePathError,
)

from .json import (
    dump_json,
    dumps as json_dumps,
    load_json,
    loads as json_loads,
    merge as json_merge,
)

from .yaml import (
    dump_yaml,
    dumps as yaml_dumps,
    load_yaml,
    load_yaml_all,
    load_yaml_full,
    load_yaml_safe,
    loads as yaml_loads,
    merge as yaml_merge,
)

from .lines import (
    clear_regex_cache,
    dump_all_text,
    dump_lines,
    extract,
    find,
    find_index,
    grep,
    grep_iter,
    insert,
    load_all_text,
    load_lines,
    load_lines_iter,
    replace,
    replace_iter,
    split,
    split_struct,
)

from .shell import (
    compress_to_tar_gz,
    extract_from_tar,
    is_command_available,
    run,
    run_cmds,
    run_output,
    which,
)

from .archive import (
    add_to_archive,
    archive_info,
    compress,
    compress_files,
    compress_parallel,
    extract,
    extract_file,
    is_archive,
    list_archive,
    list_archive_iter,
    ArchiveError,
    ArchiveInfo,
)

from .logger import (
    logger_blank,
    logger_dict,
    logger_file_info,
    logger_list,
    logger_section,
    logger_separator,
    logger_table_begin,
    logger_table_end,
)

from .hash import (
    hash_bytes,
    hash_file,
    hash_string,
    md5,
    sha256,
    sha512,
)

from .git import (
    get_branch_name,
    get_commit_hash,
    get_current_commit_info,
    get_latest_tag,
    get_remote_url,
    get_root_dir,
    get_tags,
    is_dirty,
    is_git_repo,
    GitError,
)

from .indent import (
    convert_to_tabs,
    detect_indent,
    expand_tabs,
    get_indent_level,
    get_python_file_func_indent_spaces,
    normalize_indent,
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "fs",
    "git",
    "hash",
    "indent",
    "json",
    "lines",
    "logger",
    "shell",
    "yaml",
    "copy",
    "current_dir",
    "ensure",
    "exists",
    "file_size",
    "is_empty_dir",
    "listdir",
    "move",
    "remove",
    "search",
    "tree",
    "walk",
    "walk_iter",
    "search_iter",
    "listdir_iter",
    "clear_pattern_cache",
    "FileOperationError",
    "UnsafePathError",
    "dump_json",
    "json_dumps",
    "load_json",
    "json_loads",
    "json_merge",
    "dump_yaml",
    "yaml_dumps",
    "load_yaml",
    "load_yaml_all",
    "load_yaml_full",
    "load_yaml_safe",
    "yaml_loads",
    "yaml_merge",
    "dump_all_text",
    "dump_lines",
    "extract",
    "find",
    "find_index",
    "grep",
    "insert",
    "load_all_text",
    "load_lines",
    "replace",
    "replace_iter",
    "split",
    "split_struct",
    "load_lines_iter",
    "grep_iter",
    "clear_regex_cache",
    "compress_to_tar_gz",
    "extract_from_tar",
    "is_command_available",
    "run",
    "run_cmds",
    "run_output",
    "which",
    "archive",
    "add_to_archive",
    "archive_info",
    "compress",
    "compress_files",
    "compress_parallel",
    "extract",
    "extract_file",
    "is_archive",
    "list_archive",
    "list_archive_iter",
    "ArchiveError",
    "ArchiveInfo",
    "logger_blank",
    "logger_dict",
    "logger_file_info",
    "logger_list",
    "logger_section",
    "logger_separator",
    "logger_table_begin",
    "logger_table_end",
    "hash_bytes",
    "hash_file",
    "hash_string",
    "md5",
    "sha256",
    "sha512",
    "get_branch_name",
    "get_commit_hash",
    "get_current_commit_info",
    "get_latest_tag",
    "get_remote_url",
    "get_root_dir",
    "get_tags",
    "is_dirty",
    "is_git_repo",
    "GitError",
    "convert_to_tabs",
    "detect_indent",
    "expand_tabs",
    "get_indent_level",
    "get_python_file_func_indent_spaces",
    "normalize_indent",
]
