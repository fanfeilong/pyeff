"""Git utilities.

This module provides utilities for working with Git repositories:
- Getting commit information
- Checking repository status
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, TypedDict, Union

PathLike = Union[str, Path]


class CommitInfo(TypedDict):
    """Information about a Git commit."""

    commit_hash: str
    author: str
    email: str
    date: str
    message: str


class GitError(Exception):
    """Raised when a Git operation fails."""

    pass


def _run_git(
    args: List[str],
    cwd: Optional[PathLike] = None,
) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(cwd) if cwd else None,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git command failed: git {' '.join(args)}\n{e.stderr}")
    except FileNotFoundError:
        raise GitError("Git is not installed or not in PATH")


def get_current_commit_info(cwd: Optional[PathLike] = None) -> CommitInfo:
    """Get information about the current (HEAD) commit.

    Args:
        cwd: Working directory (default: current directory).

    Returns:
        CommitInfo with hash, author, email, date, and message.

    Raises:
        GitError: If not in a git repository or git fails.
    """
    return CommitInfo(
        commit_hash=_run_git(["rev-parse", "HEAD"], cwd),
        author=_run_git(["log", "-1", "--pretty=format:%an"], cwd),
        email=_run_git(["log", "-1", "--pretty=format:%ae"], cwd),
        date=_run_git(["log", "-1", "--pretty=format:%ad"], cwd),
        message=_run_git(["log", "-1", "--pretty=format:%s"], cwd),
    )


def get_commit_hash(
    short: bool = False,
    cwd: Optional[PathLike] = None,
) -> str:
    """Get the current commit hash.

    Args:
        short: If True, return short hash.
        cwd: Working directory.

    Returns:
        Commit hash string.

    Raises:
        GitError: If not in a git repository.
    """
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    return _run_git(args, cwd)


def get_branch_name(cwd: Optional[PathLike] = None) -> str:
    """Get the current branch name.

    Args:
        cwd: Working directory.

    Returns:
        Current branch name.

    Raises:
        GitError: If not in a git repository.
    """
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)


def is_dirty(cwd: Optional[PathLike] = None) -> bool:
    """Check if the working directory has uncommitted changes.

    Args:
        cwd: Working directory.

    Returns:
        True if there are uncommitted changes.

    Raises:
        GitError: If not in a git repository.
    """
    try:
        output = _run_git(["status", "--porcelain"], cwd)
        return bool(output)
    except GitError:
        raise


def get_remote_url(
    remote: str = "origin",
    cwd: Optional[PathLike] = None,
) -> Optional[str]:
    """Get the URL of a remote.

    Args:
        remote: Remote name (default: origin).
        cwd: Working directory.

    Returns:
        Remote URL, or None if remote doesn't exist.

    Raises:
        GitError: If not in a git repository.
    """
    try:
        return _run_git(["remote", "get-url", remote], cwd)
    except GitError:
        return None


def get_tags(cwd: Optional[PathLike] = None) -> List[str]:
    """Get all tags in the repository.

    Args:
        cwd: Working directory.

    Returns:
        List of tag names.

    Raises:
        GitError: If not in a git repository.
    """
    output = _run_git(["tag", "-l"], cwd)
    return output.splitlines() if output else []


def get_latest_tag(cwd: Optional[PathLike] = None) -> Optional[str]:
    """Get the latest tag reachable from HEAD.

    Args:
        cwd: Working directory.

    Returns:
        Latest tag name, or None if no tags exist.

    Raises:
        GitError: If not in a git repository.
    """
    try:
        return _run_git(["describe", "--tags", "--abbrev=0"], cwd)
    except GitError:
        return None


def get_root_dir(cwd: Optional[PathLike] = None) -> Path:
    """Get the root directory of the git repository.

    Args:
        cwd: Working directory.

    Returns:
        Path to repository root.

    Raises:
        GitError: If not in a git repository.
    """
    return Path(_run_git(["rev-parse", "--show-toplevel"], cwd))


def is_git_repo(cwd: Optional[PathLike] = None) -> bool:
    """Check if the directory is inside a git repository.

    Args:
        cwd: Directory to check.

    Returns:
        True if inside a git repository.
    """
    try:
        _run_git(["rev-parse", "--git-dir"], cwd)
        return True
    except GitError:
        return False
