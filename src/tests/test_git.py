"""Tests for pyeff.git module."""

import pytest
from pathlib import Path

from pyeff.git import (
    is_git_repo,
    get_root_dir,
    get_branch_name,
    get_commit_hash,
    GitError,
)


class TestIsGitRepo:
    def test_is_git_repo_true(self):
        assert is_git_repo() is True

    def test_is_git_repo_false(self, tmp_path):
        assert is_git_repo(tmp_path) is False


class TestGetRootDir:
    def test_get_root_dir(self):
        root = get_root_dir()
        assert root.exists()
        assert (root / ".git").exists()


class TestGetBranchName:
    def test_get_branch_name(self):
        branch = get_branch_name()
        assert isinstance(branch, str)
        assert len(branch) > 0


class TestGetCommitHash:
    def test_get_commit_hash(self):
        commit = get_commit_hash()
        assert isinstance(commit, str)
        assert len(commit) == 40

    def test_get_commit_hash_short(self):
        commit = get_commit_hash(short=True)
        assert isinstance(commit, str)
        assert len(commit) < 40
