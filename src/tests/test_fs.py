"""Tests for pyeff.fs module."""

import pytest
from pathlib import Path

from pyeff.fs import (
    copy,
    current_dir,
    ensure,
    exists,
    file_size,
    is_empty_dir,
    listdir,
    move,
    remove,
    search,
    tree,
    walk,
    FileOperationError,
    UnsafePathError,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def sample_tree(temp_dir):
    """Create a sample directory structure."""
    (temp_dir / "file1.txt").write_text("content1")
    (temp_dir / "file2.md").write_text("content2")
    (temp_dir / "sub1").mkdir()
    (temp_dir / "sub1" / "file3.txt").write_text("content3")
    (temp_dir / "sub1" / "file4.md").write_text("content4")
    (temp_dir / "sub2").mkdir()
    (temp_dir / "sub2" / "file5.txt").write_text("content5")
    return temp_dir


class TestEnsure:
    def test_create_new_directory(self, temp_dir):
        new_dir = temp_dir / "new_dir"
        result = ensure(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()
        assert result == new_dir

    def test_existing_directory(self, temp_dir):
        result = ensure(temp_dir)
        assert temp_dir.exists()
        assert result == temp_dir

    def test_nested_directory(self, temp_dir):
        nested = temp_dir / "a" / "b" / "c"
        result = ensure(nested)
        assert nested.exists()
        assert result == nested


class TestCurrentDir:
    def test_current_dir(self):
        result = current_dir(__file__)
        assert result.is_dir()
        assert result == Path(__file__).resolve().parent


class TestIsEmptyDir:
    def test_empty_directory(self, temp_dir):
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        assert is_empty_dir(empty_dir) is True

    def test_non_empty_directory(self, sample_tree):
        assert is_empty_dir(sample_tree) is False

    def test_nonexistent_directory(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            is_empty_dir(temp_dir / "nonexistent")

    def test_not_a_directory(self, sample_tree):
        with pytest.raises(NotADirectoryError):
            is_empty_dir(sample_tree / "file1.txt")


class TestCopy:
    def test_copy_file(self, sample_tree, temp_dir):
        src = sample_tree / "file1.txt"
        dst = temp_dir / "copy" / "file1_copy.txt"
        count = copy(src, dst)
        assert count == 1
        assert dst.exists()
        assert dst.read_text() == "content1"

    def test_copy_directory_all(self, sample_tree, temp_dir):
        dst = temp_dir / "copy_all"
        count = copy(sample_tree, dst)
        assert count >= 5
        assert (dst / "file1.txt").exists()
        assert (dst / "sub1" / "file3.txt").exists()

    def test_copy_directory_include_pattern(self, sample_tree, temp_dir):
        dst = temp_dir / "copy_include"
        count = copy(sample_tree, dst, mode="include", patterns=["*.txt"])
        assert (dst / "file1.txt").exists()
        assert not (dst / "file2.md").exists()

    def test_copy_directory_ignore_pattern(self, sample_tree, temp_dir):
        dst = temp_dir / "copy_ignore"
        count = copy(sample_tree, dst, mode="ignore", patterns=["*.md"])
        assert (dst / "file1.txt").exists()
        assert not (dst / "file2.md").exists()

    def test_copy_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            copy(temp_dir / "nonexistent", temp_dir / "dst")

    def test_copy_invalid_mode(self, sample_tree, temp_dir):
        with pytest.raises(ValueError):
            copy(sample_tree, temp_dir / "dst", mode="invalid")


class TestRemove:
    def test_remove_file(self, sample_tree):
        file_path = sample_tree / "file1.txt"
        assert file_path.exists()
        count = remove(file_path)
        assert count == 1
        assert not file_path.exists()

    def test_remove_directory(self, sample_tree, temp_dir):
        dst = temp_dir / "to_remove"
        copy(sample_tree, dst)
        count = remove(dst)
        assert count > 0
        assert not dst.exists()

    def test_remove_with_include_pattern(self, sample_tree, temp_dir):
        dst = temp_dir / "to_remove"
        copy(sample_tree, dst)
        remove(dst, mode="include", patterns=["*.md"])
        assert (dst / "file1.txt").exists()
        assert not (dst / "file2.md").exists()

    def test_remove_nonexistent_missing_ok(self, temp_dir):
        count = remove(temp_dir / "nonexistent", missing_ok=True)
        assert count == 0

    def test_remove_nonexistent_missing_not_ok(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            remove(temp_dir / "nonexistent", missing_ok=False)

    def test_remove_list(self, sample_tree):
        files = [sample_tree / "file1.txt", sample_tree / "file2.md"]
        count = remove(files)
        assert count == 2
        assert not files[0].exists()
        assert not files[1].exists()


class TestMove:
    def test_move_file(self, sample_tree, temp_dir):
        src = sample_tree / "file1.txt"
        dst = temp_dir / "moved" / "file1.txt"
        count = move(src, dst)
        assert count == 1
        assert dst.exists()
        assert not src.exists()

    def test_move_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            move(temp_dir / "nonexistent", temp_dir / "dst")


class TestSearch:
    def test_search_all(self, sample_tree):
        results = search(sample_tree)
        assert len(results) >= 5

    def test_search_include_pattern(self, sample_tree):
        results = search(sample_tree, mode="include", patterns=["*.txt"])
        assert all(r.suffix == ".txt" for r in results)
        assert len(results) == 3

    def test_search_ignore_pattern(self, sample_tree):
        results = search(sample_tree, mode="ignore", patterns=["*.md"])
        assert all(r.suffix != ".md" for r in results)

    def test_search_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            search(temp_dir / "nonexistent")


class TestListdir:
    def test_listdir_all(self, sample_tree):
        results = listdir(sample_tree)
        assert len(results) >= 4

    def test_listdir_with_extension(self, sample_tree):
        results = listdir(sample_tree, extensions=[".txt"])
        assert all(r.suffix == ".txt" for r in results)

    def test_listdir_sorted(self, sample_tree):
        results = listdir(sample_tree, sort=True)
        assert results == sorted(results)

    def test_listdir_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            listdir(temp_dir / "nonexistent")


class TestExists:
    def test_exists_file(self, sample_tree):
        assert exists(sample_tree / "file1.txt") is True

    def test_exists_directory(self, sample_tree):
        assert exists(sample_tree / "sub1") is True

    def test_not_exists(self, sample_tree):
        assert exists(sample_tree / "nonexistent") is False


class TestFileSize:
    def test_file_size(self, sample_tree):
        size = file_size(sample_tree / "file1.txt")
        assert size == len("content1")

    def test_file_size_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            file_size(temp_dir / "nonexistent")

    def test_file_size_directory(self, sample_tree):
        with pytest.raises(IsADirectoryError):
            file_size(sample_tree / "sub1")


class TestTree:
    def test_tree(self, sample_tree):
        result = tree(sample_tree)
        assert isinstance(result, str)
        assert "file1.txt" in result
        assert "sub1" in result

    def test_tree_max_depth(self, sample_tree):
        result = tree(sample_tree, max_depth=0)
        assert "file1.txt" in result
        assert "file3.txt" not in result

    def test_tree_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            tree(temp_dir / "nonexistent")


class TestWalk:
    def test_walk_all(self, sample_tree):
        results = walk(sample_tree)
        assert len(results) >= 5

    def test_walk_with_file_filter(self, sample_tree):
        results = walk(sample_tree, file_filter=lambda p: p.suffix == ".txt")
        assert all(r.suffix == ".txt" for r in results)
        assert len(results) == 3

    def test_walk_with_dir_filter(self, sample_tree):
        results = walk(sample_tree, dir_filter=lambda p: p.name != "sub2")
        names = [r.name for r in results]
        assert "file5.txt" not in names
