"""Tests for pyeff.hash module."""

import pytest
from pathlib import Path

from pyeff.hash import (
    hash_string,
    hash_bytes,
    hash_file,
    md5,
    sha256,
    sha512,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


class TestHashString:
    def test_hash_string_sha256(self):
        result = hash_string("hello")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_string_md5(self):
        result = hash_string("hello", algorithm="md5")
        assert len(result) == 32

    def test_hash_string_consistent(self):
        result1 = hash_string("test")
        result2 = hash_string("test")
        assert result1 == result2

    def test_hash_string_different_inputs(self):
        result1 = hash_string("test1")
        result2 = hash_string("test2")
        assert result1 != result2

    def test_hash_string_invalid_algorithm(self):
        with pytest.raises(ValueError):
            hash_string("test", algorithm="invalid")


class TestHashBytes:
    def test_hash_bytes_sha256(self):
        result = hash_bytes(b"hello")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_bytes_same_as_string(self):
        str_hash = hash_string("hello")
        bytes_hash = hash_bytes(b"hello")
        assert str_hash == bytes_hash


class TestHashFile:
    def test_hash_file(self, temp_dir):
        path = temp_dir / "test.txt"
        path.write_text("hello")

        result = hash_file(path)
        expected = hash_string("hello")
        assert result == expected

    def test_hash_file_nonexistent(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            hash_file(temp_dir / "nonexistent.txt")

    def test_hash_file_directory(self, temp_dir):
        with pytest.raises(ValueError):
            hash_file(temp_dir)


class TestShortcuts:
    def test_md5_string(self):
        result = md5("hello")
        assert len(result) == 32

    def test_md5_bytes(self):
        result = md5(b"hello")
        assert len(result) == 32

    def test_sha256_string(self):
        result = sha256("hello")
        assert len(result) == 64

    def test_sha512_string(self):
        result = sha512("hello")
        assert len(result) == 128
