"""Tests for pyeff.ops module (unified operations)."""

import pytest
from pathlib import Path

from pyeff.ops import (
    copy, remove, search, exists, listdir, read, write, move,
    CopyError, RemoveError, ReadError, WriteError, FileInfo,
)
from pyeff.uri import local, docker, ssh, archive


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def sample_tree(temp_dir):
    """Create a sample directory structure."""
    src_dir = temp_dir / "src_data"
    src_dir.mkdir()
    
    (src_dir / "file1.txt").write_text("content1")
    (src_dir / "file2.md").write_text("content2")
    (src_dir / "file3.py").write_text("print('hello')")
    
    sub = src_dir / "subdir"
    sub.mkdir()
    (sub / "file4.txt").write_text("content4")
    (sub / "file5.md").write_text("content5")
    
    return src_dir


class TestLocalToLocal:
    def test_copy_with_uri_strings(self, sample_tree, temp_dir):
        """Test copy with URI strings."""
        dst = temp_dir / "copy_dst"
        count = copy(f"local:{sample_tree}", f"local:{dst}")
        
        assert count == 5
        assert (dst / "file1.txt").exists()
        assert (dst / "subdir" / "file4.txt").exists()
    
    def test_copy_with_path_builders(self, sample_tree, temp_dir):
        """Test copy with path builder objects."""
        dst = temp_dir / "copy_dst"
        count = copy(local(str(sample_tree)), local(str(dst)))
        
        assert count == 5
        assert (dst / "file1.txt").exists()
    
    def test_copy_mixed(self, sample_tree, temp_dir):
        """Test copy with mixed URI string and path builder."""
        dst = temp_dir / "copy_dst"
        count = copy(f"local:{sample_tree}", local(str(dst)))
        
        assert count == 5
        assert (dst / "file1.txt").exists()
    
    def test_copy_with_pattern(self, sample_tree, temp_dir):
        """Test copy with pattern filtering."""
        dst = temp_dir / "copy_dst"
        count = copy(
            f"local:{sample_tree}",
            f"local:{dst}",
            mode="include",
            patterns=["*.txt"]
        )
        
        assert count == 2
        assert (dst / "file1.txt").exists()
        assert not (dst / "file2.md").exists()


class TestLocalToArchive:
    def test_compress_with_uri_strings(self, sample_tree, temp_dir):
        """Test compression with URI strings."""
        archive_path = temp_dir / "backup.zip"
        count = copy(f"local:{sample_tree}", f"archive:{archive_path}")
        
        assert count == 5
        assert archive_path.exists()
    
    def test_compress_with_path_builders(self, sample_tree, temp_dir):
        """Test compression with path builders."""
        archive_path = temp_dir / "backup.tar.gz"
        count = copy(local(str(sample_tree)), archive(str(archive_path)))
        
        assert count == 5
        assert archive_path.exists()
    
    def test_compress_with_pattern(self, sample_tree, temp_dir):
        """Test compression with pattern filtering."""
        archive_path = temp_dir / "backup.zip"
        count = copy(
            f"local:{sample_tree}",
            f"archive:{archive_path}",
            mode="include",
            patterns=["*.txt"]
        )
        
        assert count == 2


class TestArchiveToLocal:
    def test_extract_with_uri_strings(self, sample_tree, temp_dir):
        """Test extraction with URI strings."""
        archive_path = temp_dir / "backup.zip"
        copy(f"local:{sample_tree}", f"archive:{archive_path}")
        
        extract_dir = temp_dir / "extracted"
        count = copy(f"archive:{archive_path}", f"local:{extract_dir}")
        
        assert count == 5
        assert (extract_dir / "file1.txt").exists()
    
    def test_extract_with_path_builders(self, sample_tree, temp_dir):
        """Test extraction with path builders."""
        archive_path = temp_dir / "backup.tar.gz"
        copy(local(str(sample_tree)), archive(str(archive_path)))
        
        extract_dir = temp_dir / "extracted"
        count = copy(archive(str(archive_path)), local(str(extract_dir)))
        
        assert count == 5
        assert (extract_dir / "file1.txt").read_text() == "content1"
    
    def test_extract_with_pattern(self, sample_tree, temp_dir):
        """Test extraction with pattern filtering."""
        archive_path = temp_dir / "backup.zip"
        copy(f"local:{sample_tree}", f"archive:{archive_path}")
        
        extract_dir = temp_dir / "extracted"
        count = copy(
            f"archive:{archive_path}",
            f"local:{extract_dir}",
            mode="include",
            patterns=["*.txt"]
        )
        
        assert count == 2
        assert (extract_dir / "file1.txt").exists()
        assert not (extract_dir / "file2.md").exists()


class TestCopyError:
    def test_archive_to_archive(self, sample_tree, temp_dir):
        """Test re-packing one archive into another."""
        src_arc = temp_dir / "src.zip"
        dst_arc = temp_dir / "dst.zip"
        copy(f"local:{sample_tree}", f"archive:{src_arc}")
        count = copy(f"archive:{src_arc}", f"archive:{dst_arc}")
        assert count == 5
        assert dst_arc.exists()
    
    def test_archive_exists_no_overwrite(self, sample_tree, temp_dir):
        """Test that existing archive without overwrite raises error."""
        archive_path = temp_dir / "backup.zip"
        archive_path.touch()
        
        with pytest.raises(CopyError, match="Archive already exists"):
            copy(f"local:{sample_tree}", f"archive:{archive_path}")
    
    def test_archive_exists_with_overwrite(self, sample_tree, temp_dir):
        """Test that existing archive with overwrite works."""
        archive_path = temp_dir / "backup.zip"
        archive_path.touch()
        
        count = copy(f"local:{sample_tree}", f"archive:{archive_path}", overwrite=True)
        assert count == 5


class TestURIValidation:
    def test_bare_path_treated_as_local(self, sample_tree, temp_dir):
        """Bare paths (no scheme) resolve as local paths."""
        dst = temp_dir / "bare_dst"
        count = copy(str(sample_tree), str(dst))
        assert count == 5
        assert (dst / "file1.txt").exists()
    
    def test_unknown_scheme_treated_as_local_path(self, temp_dir):
        """Unknown schemes like ftp: fall back to local path (may not exist)."""
        with pytest.raises(FileNotFoundError):
            copy("ftp:./src", f"local:{temp_dir / 'dst'}")


class TestProgress:
    def test_copy_with_progress(self, sample_tree, temp_dir):
        """Test copy with progress callback."""
        dst = temp_dir / "copy_dst"
        progress_calls = []
        
        def on_progress(name, current, total):
            progress_calls.append((name, current, total))
        
        copy(f"local:{sample_tree}", f"local:{dst}", progress=on_progress)
        
        # Note: local-to-local copy doesn't support progress yet
        # This test just ensures it doesn't error


class TestRemove:
    def test_remove_local_file(self, temp_dir):
        """Test removing a local file."""
        file = temp_dir / "to_remove.txt"
        file.write_text("content")
        
        assert file.exists()
        remove(f"local:{file}")
        assert not file.exists()
    
    def test_remove_local_directory(self, sample_tree, temp_dir):
        """Test removing a local directory."""
        assert sample_tree.exists()
        remove(f"local:{sample_tree}")
        assert not sample_tree.exists()
    
    def test_remove_with_pattern(self, sample_tree, temp_dir):
        """Test removing with pattern filter."""
        count = remove(f"local:{sample_tree}", mode="include", patterns=["*.txt"])
        
        assert count == 2
        assert (sample_tree / "file2.md").exists()
        assert not (sample_tree / "file1.txt").exists()
    
    def test_remove_missing_ok(self, temp_dir):
        """Test removing non-existent path with missing_ok."""
        result = remove(f"local:{temp_dir}/nonexistent", missing_ok=True)
        assert result == 0


class TestSearch:
    def test_search_local(self, sample_tree):
        """Test searching local files with include pattern."""
        files = search(f"local:{sample_tree}", mode="include", patterns=["*.txt"])
        
        assert len(files) == 2
        assert any("file1.txt" in str(f) for f in files)
    
    def test_search_all_files(self, sample_tree):
        """Test searching all files."""
        files = search(f"local:{sample_tree}")
        assert len(files) == 5
    
    def test_search_with_path_builder(self, sample_tree):
        """Test searching with path builder and include pattern."""
        files = search(local(str(sample_tree)), mode="include", patterns=["*.md"])
        assert len(files) == 2


class TestExists:
    def test_exists_local_file(self, sample_tree):
        """Test checking if local file exists."""
        assert exists(f"local:{sample_tree}/file1.txt") is True
        assert exists(f"local:{sample_tree}/nonexistent.txt") is False
    
    def test_exists_local_directory(self, sample_tree):
        """Test checking if local directory exists."""
        assert exists(f"local:{sample_tree}") is True
        assert exists(f"local:{sample_tree}/subdir") is True
    
    def test_exists_with_path_builder(self, sample_tree):
        """Test exists with path builder."""
        assert exists(local(str(sample_tree / "file1.txt"))) is True


class TestListdir:
    def test_listdir_local(self, sample_tree):
        """Test listing local directory."""
        items = listdir(f"local:{sample_tree}")
        
        assert len(items) == 4  # 3 files + 1 subdir
        assert all(isinstance(i, FileInfo) for i in items)
        
        names = [i.name for i in items]
        assert "file1.txt" in names
        assert "subdir" in names
    
    def test_listdir_with_path_builder(self, sample_tree):
        """Test listdir with path builder."""
        items = listdir(local(str(sample_tree)))
        assert len(items) == 4


class TestReadWrite:
    def test_read_local_text(self, sample_tree):
        """Test reading local text file."""
        content = read(f"local:{sample_tree}/file1.txt")
        assert content == "content1"
    
    def test_read_local_binary(self, sample_tree):
        """Test reading local binary file."""
        content = read(f"local:{sample_tree}/file1.txt", binary=True)
        assert content == b"content1"
    
    def test_write_local_text(self, temp_dir):
        """Test writing local text file."""
        file = temp_dir / "written.txt"
        write(f"local:{file}", "hello world")
        
        assert file.read_text() == "hello world"
    
    def test_write_local_binary(self, temp_dir):
        """Test writing local binary file."""
        file = temp_dir / "written.bin"
        write(f"local:{file}", b"\x00\x01\x02")
        
        assert file.read_bytes() == b"\x00\x01\x02"
    
    def test_read_write_with_path_builder(self, temp_dir):
        """Test read/write with path builder."""
        file = temp_dir / "test.txt"
        write(local(str(file)), "test content")
        content = read(local(str(file)))
        assert content == "test content"


class TestMove:
    def test_move_local_file(self, temp_dir):
        """Test moving a local file."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("content")
        
        move(f"local:{src}", f"local:{dst}")
        
        assert not src.exists()
        assert dst.read_text() == "content"
    
    def test_move_local_directory(self, sample_tree, temp_dir):
        """Test moving a local directory."""
        dst = temp_dir / "moved"
        
        move(f"local:{sample_tree}", f"local:{dst}")
        
        assert not sample_tree.exists()
        assert (dst / "file1.txt").read_text() == "content1"
