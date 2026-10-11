"""Hash utilities for strings and files.

This module provides utilities for generating hashes:
- String hashing with various algorithms
- File hashing
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal, Union

PathLike = Union[str, Path]
Algorithm = Literal["md5", "sha1", "sha224", "sha256", "sha384", "sha512"]


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


def hash_string(
    input_string: str,
    algorithm: Algorithm = "sha256",
) -> str:
    """Generate a hash of a string.

    Args:
        input_string: The string to hash.
        algorithm: Hash algorithm to use. One of:
            md5, sha1, sha224, sha256, sha384, sha512

    Returns:
        Hexadecimal hash digest.

    Raises:
        ValueError: If the algorithm is not supported.
    """
    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(
            f"Unsupported algorithm: {algorithm}. "
            f"Use one of: md5, sha1, sha224, sha256, sha384, sha512"
        )

    hasher.update(input_string.encode("utf-8"))
    return hasher.hexdigest()


def hash_bytes(
    data: bytes,
    algorithm: Algorithm = "sha256",
) -> str:
    """Generate a hash of bytes.

    Args:
        data: Bytes to hash.
        algorithm: Hash algorithm to use.

    Returns:
        Hexadecimal hash digest.

    Raises:
        ValueError: If the algorithm is not supported.
    """
    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    hasher.update(data)
    return hasher.hexdigest()


def hash_file(
    file_path: PathLike,
    algorithm: Algorithm = "sha256",
    chunk_size: int = 8192,
) -> str:
    """Generate a hash of a file (local path or URI).

    Local files are hashed in chunks. Remote / archive URIs are read via
    unified ops then hashed in memory.
    """
    from .uri import resolve_path, LocalPath, looks_like_uri, URIPath

    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    is_uri = isinstance(file_path, URIPath) or (
        isinstance(file_path, str) and looks_like_uri(file_path)
    )
    if not is_uri and not isinstance(file_path, URIPath):
        # Bare path or Path — try local chunked read first
        path = _to_path(file_path)  # type: ignore[arg-type]
        if path.exists():
            if not path.is_file():
                raise ValueError(f"Path is not a file: {file_path}")
            with open(path, "rb") as f:
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()

    uri_path = resolve_path(file_path)
    if isinstance(uri_path, LocalPath):
        path = _to_path(uri_path.path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    from .ops import read
    data = read(uri_path, binary=True)
    assert isinstance(data, bytes)
    hasher.update(data)
    return hasher.hexdigest()


def md5(data: Union[str, bytes]) -> str:
    """Generate MD5 hash.

    Args:
        data: String or bytes to hash.

    Returns:
        Hexadecimal MD5 hash.
    """
    if isinstance(data, str):
        return hash_string(data, "md5")
    return hash_bytes(data, "md5")


def sha256(data: Union[str, bytes]) -> str:
    """Generate SHA256 hash.

    Args:
        data: String or bytes to hash.

    Returns:
        Hexadecimal SHA256 hash.
    """
    if isinstance(data, str):
        return hash_string(data, "sha256")
    return hash_bytes(data, "sha256")


def sha512(data: Union[str, bytes]) -> str:
    """Generate SHA512 hash.

    Args:
        data: String or bytes to hash.

    Returns:
        Hexadecimal SHA512 hash.
    """
    if isinstance(data, str):
        return hash_string(data, "sha512")
    return hash_bytes(data, "sha512")
