"""Archive utilities for zip and tar operations.

This module provides a unified API for archive operations:
- Consistent interface for zip, tar, tar.gz, tar.bz2, tar.xz
- Pattern filtering (include/ignore) like fs.copy/move/remove
- Streaming extraction for memory efficiency
- Progress callbacks for large archives

Performance optimizations:
- Native Python zipfile/tarfile (no subprocess)
- Streaming I/O for large files
- Parallel compression support (for zip)
- Generator-based iteration
"""

from __future__ import annotations

import fnmatch
import os
import re
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import (
    BinaryIO,
    Callable,
    Generator,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
)

PathLike = Union[str, Path]
Mode = Literal["all", "ignore", "include"]
ArchiveFormat = Literal["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "tgz", "tbz2", "txz"]
ProgressCallback = Callable[[str, int, int], None]


class ArchiveError(Exception):
    """Base exception for archive operations."""

    pass


@dataclass
class ArchiveInfo:
    """Information about an archive member."""

    name: str
    size: int
    compressed_size: int
    is_dir: bool
    is_file: bool


def _to_path(p: PathLike) -> Path:
    """Convert string or Path to Path object."""
    return Path(p) if not isinstance(p, Path) else p


@lru_cache(maxsize=128)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile and cache a fnmatch pattern as regex."""
    return re.compile(fnmatch.translate(pattern))


class PatternFilter:
    """Efficient pattern filtering for archive members."""

    __slots__ = ("_patterns", "_compiled", "_mode")

    def __init__(self, mode: Mode = "all", patterns: Optional[List[str]] = None):
        self._mode = mode
        self._patterns = patterns or []
        self._compiled = [_compile_pattern(p) for p in self._patterns]

    def match(self, name: str) -> bool:
        """Check if name matches the filter criteria."""
        if self._mode == "all" or not self._compiled:
            return True

        basename = os.path.basename(name)
        matches = any(p.match(basename) for p in self._compiled)

        if self._mode == "include":
            return matches
        else:
            return not matches

    def filter(self, names: List[str]) -> Generator[str, None, None]:
        """Yield names that match the filter criteria."""
        for name in names:
            if self.match(name):
                yield name


def _detect_format(path: PathLike) -> ArchiveFormat:
    """Detect archive format from file extension."""
    path_str = str(path).lower()

    if path_str.endswith(".zip"):
        return "zip"
    elif path_str.endswith(".tar.gz") or path_str.endswith(".tgz"):
        return "tar.gz"
    elif path_str.endswith(".tar.bz2") or path_str.endswith(".tbz2"):
        return "tar.bz2"
    elif path_str.endswith(".tar.xz") or path_str.endswith(".txz"):
        return "tar.xz"
    elif path_str.endswith(".tar"):
        return "tar"
    else:
        raise ArchiveError(f"Unknown archive format: {path}")


def _get_tar_mode(fmt: ArchiveFormat, write: bool = False) -> str:
    """Get tarfile mode string for format."""
    prefix = "w" if write else "r"

    if fmt in ("tar.gz", "tgz"):
        return f"{prefix}:gz"
    elif fmt in ("tar.bz2", "tbz2"):
        return f"{prefix}:bz2"
    elif fmt in ("tar.xz", "txz"):
        return f"{prefix}:xz"
    else:
        return prefix


def _get_zip_compression(level: int = 6) -> Tuple[int, int]:
    """Get zipfile compression type and level."""
    return zipfile.ZIP_DEFLATED, level


def list_archive(
    archive_path: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
) -> List[ArchiveInfo]:
    """List contents of an archive.

    Args:
        archive_path: Path to the archive file.
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.

    Returns:
        List of ArchiveInfo objects.

    Raises:
        FileNotFoundError: If archive doesn't exist.
        ArchiveError: If archive format is unsupported.
    """
    path = _to_path(archive_path)
    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    fmt = _detect_format(path)
    filter_obj = PatternFilter(mode, patterns)
    results: List[ArchiveInfo] = []

    if fmt == "zip":
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if filter_obj.match(info.filename):
                    results.append(
                        ArchiveInfo(
                            name=info.filename,
                            size=info.file_size,
                            compressed_size=info.compress_size,
                            is_dir=info.is_dir(),
                            is_file=not info.is_dir(),
                        )
                    )
    else:
        tar_mode = _get_tar_mode(fmt, write=False)
        with tarfile.open(path, tar_mode) as tf:
            for member in tf.getmembers():
                if filter_obj.match(member.name):
                    results.append(
                        ArchiveInfo(
                            name=member.name,
                            size=member.size,
                            compressed_size=member.size,
                            is_dir=member.isdir(),
                            is_file=member.isfile(),
                        )
                    )

    return results


def list_archive_iter(
    archive_path: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
) -> Generator[ArchiveInfo, None, None]:
    """List contents of an archive (generator version).

    Memory-efficient generator for large archives.

    Args:
        archive_path: Path to the archive file.
        mode: Filter mode.
        patterns: Glob patterns for filtering.

    Yields:
        ArchiveInfo objects.
    """
    path = _to_path(archive_path)
    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    fmt = _detect_format(path)
    filter_obj = PatternFilter(mode, patterns)

    if fmt == "zip":
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if filter_obj.match(info.filename):
                    yield ArchiveInfo(
                        name=info.filename,
                        size=info.file_size,
                        compressed_size=info.compress_size,
                        is_dir=info.is_dir(),
                        is_file=not info.is_dir(),
                    )
    else:
        tar_mode = _get_tar_mode(fmt, write=False)
        with tarfile.open(path, tar_mode) as tf:
            for member in tf.getmembers():
                if filter_obj.match(member.name):
                    yield ArchiveInfo(
                        name=member.name,
                        size=member.size,
                        compressed_size=member.size,
                        is_dir=member.isdir(),
                        is_file=member.isfile(),
                    )


def compress(
    source: PathLike,
    output: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    format: Optional[ArchiveFormat] = None,
    compression_level: int = 6,
    follow_symlinks: bool = True,
    progress: Optional[ProgressCallback] = None,
) -> int:
    """Compress files/directory to an archive.

    Args:
        source: Source file or directory to compress.
        output: Output archive path.
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        format: Archive format (auto-detected from output extension if None).
        compression_level: Compression level (0-9, default 6).
        follow_symlinks: Whether to follow symbolic links.
        progress: Optional callback(filename, current, total).

    Returns:
        Number of files compressed.

    Raises:
        FileNotFoundError: If source doesn't exist.
        FileExistsError: If output already exists.
        ArchiveError: If format is unsupported.

    Example:
        >>> compress("./src", "backup.tar.gz", mode="ignore", patterns=["*.pyc"])
        >>> compress("./docs", "docs.zip", mode="include", patterns=["*.md", "*.txt"])
    """
    src_path = _to_path(source)
    out_path = _to_path(output)

    if not src_path.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    if out_path.exists():
        raise FileExistsError(f"Output already exists: {output}")

    fmt = format or _detect_format(out_path)
    filter_obj = PatternFilter(mode, patterns)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if src_path.is_file():
        files_to_add = [(src_path, src_path.name)]
    else:
        files_to_add = []
        for root, dirs, files in os.walk(src_path, followlinks=follow_symlinks):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                arcname = str(file_path.relative_to(src_path))
                if filter_obj.match(arcname):
                    files_to_add.append((file_path, arcname))

    total = len(files_to_add)
    count = 0

    if fmt == "zip":
        compression, level = _get_zip_compression(compression_level)
        with zipfile.ZipFile(out_path, "w", compression, compresslevel=level) as zf:
            for file_path, arcname in files_to_add:
                zf.write(file_path, arcname)
                count += 1
                if progress:
                    progress(arcname, count, total)
    else:
        tar_mode = _get_tar_mode(fmt, write=True)
        with tarfile.open(out_path, tar_mode) as tf:
            for file_path, arcname in files_to_add:
                tf.add(file_path, arcname, recursive=False)
                count += 1
                if progress:
                    progress(arcname, count, total)

    return count


def compress_files(
    files: List[PathLike],
    output: PathLike,
    base_dir: Optional[PathLike] = None,
    format: Optional[ArchiveFormat] = None,
    compression_level: int = 6,
    progress: Optional[ProgressCallback] = None,
) -> int:
    """Compress a list of files to an archive.

    Args:
        files: List of file paths to compress.
        output: Output archive path.
        base_dir: Base directory for relative paths in archive.
        format: Archive format (auto-detected if None).
        compression_level: Compression level (0-9).
        progress: Optional progress callback.

    Returns:
        Number of files compressed.

    Example:
        >>> compress_files(["a.txt", "b.txt"], "files.zip")
        >>> compress_files(glob("*.py"), "scripts.tar.gz", base_dir="./src")
    """
    out_path = _to_path(output)
    base = _to_path(base_dir) if base_dir else None

    if out_path.exists():
        raise FileExistsError(f"Output already exists: {output}")

    fmt = format or _detect_format(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    files_to_add: List[Tuple[Path, str]] = []
    for f in files:
        file_path = _to_path(f)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {f}")

        if base and file_path.is_relative_to(base):
            arcname = str(file_path.relative_to(base))
        else:
            arcname = file_path.name

        files_to_add.append((file_path, arcname))

    total = len(files_to_add)
    count = 0

    if fmt == "zip":
        compression, level = _get_zip_compression(compression_level)
        with zipfile.ZipFile(out_path, "w", compression, compresslevel=level) as zf:
            for file_path, arcname in files_to_add:
                zf.write(file_path, arcname)
                count += 1
                if progress:
                    progress(arcname, count, total)
    else:
        tar_mode = _get_tar_mode(fmt, write=True)
        with tarfile.open(out_path, tar_mode) as tf:
            for file_path, arcname in files_to_add:
                tf.add(file_path, arcname, recursive=False)
                count += 1
                if progress:
                    progress(arcname, count, total)

    return count


def extract(
    archive_path: PathLike,
    output_dir: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    overwrite: bool = False,
    progress: Optional[ProgressCallback] = None,
) -> int:
    """Extract files from an archive.

    Args:
        archive_path: Path to the archive file.
        output_dir: Directory to extract files to.
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        overwrite: Whether to overwrite existing files.
        progress: Optional callback(filename, current, total).

    Returns:
        Number of files extracted.

    Raises:
        FileNotFoundError: If archive doesn't exist.
        ArchiveError: If format is unsupported.

    Example:
        >>> extract("backup.tar.gz", "./restore")
        >>> extract("data.zip", "./data", mode="include", patterns=["*.csv"])
    """
    path = _to_path(archive_path)
    out_dir = _to_path(output_dir)

    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    fmt = _detect_format(path)
    filter_obj = PatternFilter(mode, patterns)

    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0

    if fmt == "zip":
        with zipfile.ZipFile(path, "r") as zf:
            members = [m for m in zf.infolist() if filter_obj.match(m.filename)]
            total = len(members)

            for info in members:
                target = out_dir / info.filename

                if target.exists() and not overwrite:
                    continue

                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as dst:
                        _copy_stream(src, dst)

                count += 1
                if progress:
                    progress(info.filename, count, total)
    else:
        tar_mode = _get_tar_mode(fmt, write=False)
        with tarfile.open(path, tar_mode) as tf:
            members = [m for m in tf.getmembers() if filter_obj.match(m.name)]
            total = len(members)

            for member in members:
                target = out_dir / member.name

                if target.exists() and not overwrite:
                    continue

                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tf.extractfile(member) as src:
                        if src:
                            with open(target, "wb") as dst:
                                _copy_stream(src, dst)

                count += 1
                if progress:
                    progress(member.name, count, total)

    return count


def extract_file(
    archive_path: PathLike,
    member_name: str,
    output_path: Optional[PathLike] = None,
) -> bytes:
    """Extract a single file from an archive.

    Args:
        archive_path: Path to the archive.
        member_name: Name of the member to extract.
        output_path: If provided, write to this path; otherwise return bytes.

    Returns:
        File contents as bytes (if output_path is None).

    Raises:
        FileNotFoundError: If archive or member doesn't exist.
    """
    path = _to_path(archive_path)
    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    fmt = _detect_format(path)

    if fmt == "zip":
        with zipfile.ZipFile(path, "r") as zf:
            try:
                data = zf.read(member_name)
            except KeyError:
                raise FileNotFoundError(f"Member not found: {member_name}")
    else:
        tar_mode = _get_tar_mode(fmt, write=False)
        with tarfile.open(path, tar_mode) as tf:
            try:
                member = tf.getmember(member_name)
                f = tf.extractfile(member)
                if f is None:
                    raise ArchiveError(f"Cannot extract: {member_name}")
                data = f.read()
            except KeyError:
                raise FileNotFoundError(f"Member not found: {member_name}")

    if output_path:
        out = _to_path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)

    return data


def _copy_stream(
    src: BinaryIO,
    dst: BinaryIO,
    buffer_size: int = 1024 * 1024,
) -> int:
    """Copy data between streams with buffering."""
    total = 0
    while True:
        chunk = src.read(buffer_size)
        if not chunk:
            break
        dst.write(chunk)
        total += len(chunk)
    return total


def add_to_archive(
    archive_path: PathLike,
    files: List[PathLike],
    base_dir: Optional[PathLike] = None,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
) -> int:
    """Add files to an existing archive.

    Args:
        archive_path: Path to the archive.
        files: Files to add.
        base_dir: Base directory for relative paths.
        mode: Filter mode.
        patterns: Glob patterns for filtering.

    Returns:
        Number of files added.

    Note:
        Only zip format supports adding to existing archives efficiently.
        For tar formats, this creates a new archive.
    """
    path = _to_path(archive_path)
    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    fmt = _detect_format(path)
    filter_obj = PatternFilter(mode, patterns)
    base = _to_path(base_dir) if base_dir else None

    count = 0

    if fmt == "zip":
        with zipfile.ZipFile(path, "a") as zf:
            for f in files:
                file_path = _to_path(f)
                if not file_path.exists():
                    continue

                if base and file_path.is_relative_to(base):
                    arcname = str(file_path.relative_to(base))
                else:
                    arcname = file_path.name

                if filter_obj.match(arcname):
                    zf.write(file_path, arcname)
                    count += 1
    else:
        raise ArchiveError(
            f"Adding to existing {fmt} archives is not supported. "
            "Create a new archive instead."
        )

    return count


def archive_info(archive_path: PathLike) -> dict:
    """Get information about an archive.

    Args:
        archive_path: Path to the archive.

    Returns:
        Dictionary with archive information.
    """
    path = _to_path(archive_path)
    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    fmt = _detect_format(path)
    stat = path.stat()

    info = {
        "path": str(path),
        "format": fmt,
        "size": stat.st_size,
        "file_count": 0,
        "dir_count": 0,
        "total_size": 0,
        "compressed_size": stat.st_size,
    }

    if fmt == "zip":
        with zipfile.ZipFile(path, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    info["dir_count"] += 1
                else:
                    info["file_count"] += 1
                    info["total_size"] += member.file_size
    else:
        tar_mode = _get_tar_mode(fmt, write=False)
        with tarfile.open(path, tar_mode) as tf:
            for member in tf.getmembers():
                if member.isdir():
                    info["dir_count"] += 1
                elif member.isfile():
                    info["file_count"] += 1
                    info["total_size"] += member.size

    return info


def is_archive(path: PathLike) -> bool:
    """Check if a file is a supported archive.

    Args:
        path: Path to check.

    Returns:
        True if the file is a supported archive format.
    """
    try:
        _detect_format(path)
        return True
    except ArchiveError:
        return False


def compress_parallel(
    source: PathLike,
    output: PathLike,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    workers: int = 4,
    compression_level: int = 6,
    progress: Optional[ProgressCallback] = None,
) -> int:
    """Compress files using parallel workers (zip only).

    Uses multiple threads for compression, which can significantly
    speed up compression of many small files.

    Args:
        source: Source directory to compress.
        output: Output archive path (must be .zip).
        mode: Filter mode.
        patterns: Glob patterns for filtering.
        workers: Number of parallel workers.
        compression_level: Compression level (0-9).
        progress: Optional progress callback.

    Returns:
        Number of files compressed.

    Note:
        Parallel compression only works for zip format.
        For tar formats, use regular compress().
    """
    src_path = _to_path(source)
    out_path = _to_path(output)

    fmt = _detect_format(out_path)
    if fmt != "zip":
        return compress(
            source, output, mode, patterns,
            format=fmt, compression_level=compression_level, progress=progress
        )

    if not src_path.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    if out_path.exists():
        raise FileExistsError(f"Output already exists: {output}")

    filter_obj = PatternFilter(mode, patterns)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    files_to_add: List[Tuple[Path, str]] = []
    for root, dirs, files in os.walk(src_path):
        root_path = Path(root)
        for file in files:
            file_path = root_path / file
            arcname = str(file_path.relative_to(src_path))
            if filter_obj.match(arcname):
                files_to_add.append((file_path, arcname))

    total = len(files_to_add)
    count = 0
    compression, level = _get_zip_compression(compression_level)

    with zipfile.ZipFile(out_path, "w", compression, compresslevel=level) as zf:
        lock = __import__("threading").Lock()

        def compress_file(item: Tuple[Path, str]) -> str:
            file_path, arcname = item
            data = file_path.read_bytes()
            with lock:
                zf.writestr(arcname, data)
            return arcname

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for arcname in executor.map(compress_file, files_to_add):
                count += 1
                if progress:
                    progress(arcname, count, total)

    return count
