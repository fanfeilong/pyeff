"""Tests for pyeff.ops module (unified copy operations)."""

import pytest
from pathlib import Path

from pyeff.ops import copy, CopyError
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
    def test_unsupported_operation(self):
        """Test that unsupported operations raise CopyError."""
        with pytest.raises(CopyError, match="Unsupported copy operation"):
            copy("archive:./a.zip", "archive:./b.zip")
    
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
    def test_invalid_uri_format(self):
        """Test that invalid URI format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URI format"):
            copy("invalid", "local:./dst")
    
    def test_unknown_scheme(self):
        """Test that unknown scheme raises ValueError."""
        with pytest.raises(ValueError, match="Unknown URI scheme"):
            copy("ftp:./src", "local:./dst")


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
