"""Tests for pyeff.archive module."""

import pytest
from pathlib import Path

from pyeff.archive import (
    compress,
    compress_files,
    compress_parallel,
    extract,
    extract_file,
    list_archive,
    list_archive_iter,
    archive_info,
    add_to_archive,
    is_archive,
    ArchiveError,
    ArchiveInfo,
    PatternFilter,
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
    (temp_dir / "file3.py").write_text("print('hello')")
    
    sub = temp_dir / "subdir"
    sub.mkdir()
    (sub / "file4.txt").write_text("content4")
    (sub / "file5.md").write_text("content5")
    
    return temp_dir


class TestPatternFilter:
    def test_filter_all(self):
        f = PatternFilter(mode="all")
        assert f.match("file.txt") is True
        assert f.match("file.py") is True

    def test_filter_include(self):
        f = PatternFilter(mode="include", patterns=["*.txt"])
        assert f.match("file.txt") is True
        assert f.match("file.py") is False

    def test_filter_ignore(self):
        f = PatternFilter(mode="ignore", patterns=["*.txt"])
        assert f.match("file.txt") is False
        assert f.match("file.py") is True

    def test_filter_multiple_patterns(self):
        f = PatternFilter(mode="include", patterns=["*.txt", "*.md"])
        assert f.match("file.txt") is True
        assert f.match("file.md") is True
        assert f.match("file.py") is False


class TestCompressZip:
    def test_compress_directory(self, sample_tree, temp_dir):
        output = temp_dir / "output.zip"
        count = compress(sample_tree, output)
        
        assert output.exists()
        assert count == 5

    def test_compress_with_include_pattern(self, sample_tree, temp_dir):
        output = temp_dir / "output.zip"
        count = compress(sample_tree, output, mode="include", patterns=["*.txt"])
        
        assert count == 2
        
        members = list_archive(output)
        assert all(m.name.endswith(".txt") for m in members if m.is_file)

    def test_compress_with_ignore_pattern(self, sample_tree, temp_dir):
        output = temp_dir / "output.zip"
        count = compress(sample_tree, output, mode="ignore", patterns=["*.md"])
        
        assert count == 3
        
        members = list_archive(output)
        assert not any(m.name.endswith(".md") for m in members)

    def test_compress_single_file(self, temp_dir):
        file = temp_dir / "single.txt"
        file.write_text("content")
        output = temp_dir / "single.zip"
        
        count = compress(file, output)
        assert count == 1

    def test_compress_nonexistent_raises(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            compress(temp_dir / "nonexistent", temp_dir / "out.zip")

    def test_compress_existing_output_raises(self, sample_tree, temp_dir):
        output = temp_dir / "output.zip"
        output.touch()
        
        with pytest.raises(FileExistsError):
            compress(sample_tree, output)


class TestCompressTar:
    def test_compress_tar_gz(self, sample_tree, temp_dir):
        output = temp_dir / "output.tar.gz"
        count = compress(sample_tree, output)
        
        assert output.exists()
        assert count == 5

    def test_compress_tar_bz2(self, sample_tree, temp_dir):
        output = temp_dir / "output.tar.bz2"
        count = compress(sample_tree, output)
        
        assert output.exists()
        assert count == 5

    def test_compress_tar_xz(self, sample_tree, temp_dir):
        output = temp_dir / "output.tar.xz"
        count = compress(sample_tree, output)
        
        assert output.exists()
        assert count == 5

    def test_compress_tar(self, sample_tree, temp_dir):
        output = temp_dir / "output.tar"
        count = compress(sample_tree, output)
        
        assert output.exists()
        assert count == 5


class TestCompressFiles:
    def test_compress_file_list(self, sample_tree, temp_dir):
        files = [
            sample_tree / "file1.txt",
            sample_tree / "file2.md",
        ]
        output = temp_dir / "files.zip"
        
        count = compress_files(files, output)
        assert count == 2

    def test_compress_with_base_dir(self, sample_tree, temp_dir):
        files = list(sample_tree.glob("**/*.txt"))
        output = temp_dir / "files.zip"
        
        count = compress_files(files, output, base_dir=sample_tree)
        assert count == 2


class TestExtract:
    def test_extract_zip(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        extract_dir = temp_dir / "extracted"
        count = extract(archive, extract_dir)
        
        assert count == 5
        assert (extract_dir / "file1.txt").exists()
        assert (extract_dir / "subdir" / "file4.txt").exists()

    def test_extract_tar_gz(self, sample_tree, temp_dir):
        archive = temp_dir / "test.tar.gz"
        compress(sample_tree, archive)
        
        extract_dir = temp_dir / "extracted"
        count = extract(archive, extract_dir)
        
        assert count == 5
        assert (extract_dir / "file1.txt").read_text() == "content1"

    def test_extract_with_pattern(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        extract_dir = temp_dir / "extracted"
        count = extract(archive, extract_dir, mode="include", patterns=["*.txt"])
        
        assert count == 2
        assert (extract_dir / "file1.txt").exists()
        assert not (extract_dir / "file2.md").exists()

    def test_extract_nonexistent_raises(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            extract(temp_dir / "nonexistent.zip", temp_dir / "out")


class TestExtractFile:
    def test_extract_single_file(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        data = extract_file(archive, "file1.txt")
        assert data == b"content1"

    def test_extract_to_path(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        output = temp_dir / "extracted_file.txt"
        extract_file(archive, "file1.txt", output)
        
        assert output.read_text() == "content1"

    def test_extract_nonexistent_member(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        with pytest.raises(FileNotFoundError):
            extract_file(archive, "nonexistent.txt")


class TestListArchive:
    def test_list_zip(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        members = list_archive(archive)
        assert len(members) == 5
        assert all(isinstance(m, ArchiveInfo) for m in members)

    def test_list_tar_gz(self, sample_tree, temp_dir):
        archive = temp_dir / "test.tar.gz"
        compress(sample_tree, archive)
        
        members = list_archive(archive)
        assert len(members) == 5

    def test_list_with_pattern(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        members = list_archive(archive, mode="include", patterns=["*.txt"])
        assert len(members) == 2

    def test_list_iter(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        gen = list_archive_iter(archive)
        assert hasattr(gen, "__next__")
        
        members = list(gen)
        assert len(members) == 5


class TestArchiveInfo:
    def test_archive_info_zip(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        info = archive_info(archive)
        assert info["format"] == "zip"
        assert info["file_count"] == 5
        assert info["total_size"] > 0

    def test_archive_info_tar_gz(self, sample_tree, temp_dir):
        archive = temp_dir / "test.tar.gz"
        compress(sample_tree, archive)
        
        info = archive_info(archive)
        assert info["format"] == "tar.gz"
        assert info["file_count"] == 5


class TestAddToArchive:
    def test_add_to_zip(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress_files([sample_tree / "file1.txt"], archive)
        
        count = add_to_archive(archive, [sample_tree / "file2.md"])
        assert count == 1
        
        members = list_archive(archive)
        assert len(members) == 2

    def test_add_to_tar_raises(self, sample_tree, temp_dir):
        archive = temp_dir / "test.tar.gz"
        compress(sample_tree, archive)
        
        with pytest.raises(ArchiveError):
            add_to_archive(archive, [sample_tree / "file2.md"])


class TestIsArchive:
    def test_is_archive_zip(self, temp_dir):
        assert is_archive(temp_dir / "test.zip") is True

    def test_is_archive_tar_gz(self, temp_dir):
        assert is_archive(temp_dir / "test.tar.gz") is True

    def test_is_archive_unknown(self, temp_dir):
        assert is_archive(temp_dir / "test.unknown") is False


class TestCompressParallel:
    def test_compress_parallel_zip(self, sample_tree, temp_dir):
        output = temp_dir / "parallel.zip"
        count = compress_parallel(sample_tree, output, workers=2)
        
        assert count == 5
        assert output.exists()
        
        members = list_archive(output)
        assert len(members) == 5


class TestProgress:
    def test_compress_with_progress(self, sample_tree, temp_dir):
        output = temp_dir / "test.zip"
        progress_calls = []
        
        def progress(name, current, total):
            progress_calls.append((name, current, total))
        
        compress(sample_tree, output, progress=progress)
        
        assert len(progress_calls) == 5
        assert progress_calls[-1][1] == progress_calls[-1][2]

    def test_extract_with_progress(self, sample_tree, temp_dir):
        archive = temp_dir / "test.zip"
        compress(sample_tree, archive)
        
        extract_dir = temp_dir / "extracted"
        progress_calls = []
        
        def progress(name, current, total):
            progress_calls.append((name, current, total))
        
        extract(archive, extract_dir, progress=progress)
        
        assert len(progress_calls) == 5
