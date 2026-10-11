"""Base classes and interfaces for remote operations.

This module defines the common interface that all remote backends
(Docker, SSH, K8s) must implement.
"""

from __future__ import annotations

import fnmatch
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import (
    Callable,
    Generator,
    List,
    Literal,
    Optional,
    Union,
)

PathLike = Union[str, Path]
Mode = Literal["all", "ignore", "include"]
ProgressCallback = Callable[[str, int, int], None]


class RemoteError(Exception):
    """Base exception for remote operations."""
    pass


class RemoteConnectionError(RemoteError):
    """Raised when connection to remote fails."""
    pass


class RemoteFileNotFoundError(RemoteError):
    """Raised when remote file/directory not found."""
    pass


class RemotePermissionError(RemoteError):
    """Raised when permission denied on remote."""
    pass


@dataclass
class RemoteFileInfo:
    """Information about a remote file."""
    
    name: str
    path: str
    size: int
    is_dir: bool
    is_file: bool
    mode: Optional[str] = None
    owner: Optional[str] = None
    modified: Optional[str] = None


@lru_cache(maxsize=128)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile and cache a fnmatch pattern as regex."""
    return re.compile(fnmatch.translate(pattern))


class PatternFilter:
    """Pattern filtering for remote files."""
    
    __slots__ = ("_patterns", "_compiled", "_mode")
    
    def __init__(self, mode: Mode = "all", patterns: Optional[List[str]] = None):
        self._mode = mode
        self._patterns = patterns or []
        self._compiled = [_compile_pattern(p) for p in self._patterns]
    
    def match(self, name: str) -> bool:
        """Check if name matches the filter criteria."""
        if self._mode == "all" or not self._compiled:
            return True
        
        basename = PurePosixPath(name).name
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


class RemoteBackend(ABC):
    """Abstract base class for remote file operations.
    
    All remote backends (Docker, SSH, K8s) should implement this interface
    to provide consistent API across different remote systems.
    """
    
    @abstractmethod
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files from remote to local.
        
        Args:
            remote_path: Path on remote system.
            local_path: Local destination path.
            mode: Filter mode ("all", "include", "ignore").
            patterns: Glob patterns for filtering.
            progress: Optional progress callback.
            
        Returns:
            Number of files copied.
        """
        pass
    
    @abstractmethod
    def copy_to(
        self,
        local_path: PathLike,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files from local to remote.
        
        Args:
            local_path: Local source path.
            remote_path: Path on remote system.
            mode: Filter mode.
            patterns: Glob patterns for filtering.
            progress: Optional progress callback.
            
        Returns:
            Number of files copied.
        """
        pass
    
    @abstractmethod
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        """Remove files on remote.
        
        Args:
            remote_path: Path on remote system.
            mode: Filter mode.
            patterns: Glob patterns for filtering.
            recursive: Whether to remove directories recursively.
            
        Returns:
            Number of files removed.
        """
        pass
    
    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        """Check if path exists on remote.
        
        Args:
            remote_path: Path to check.
            
        Returns:
            True if path exists.
        """
        pass
    
    @abstractmethod
    def is_file(self, remote_path: str) -> bool:
        """Check if path is a file on remote."""
        pass
    
    @abstractmethod
    def is_dir(self, remote_path: str) -> bool:
        """Check if path is a directory on remote."""
        pass
    
    @abstractmethod
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        """List files in remote directory.
        
        Args:
            remote_path: Directory path on remote.
            mode: Filter mode.
            patterns: Glob patterns for filtering.
            
        Returns:
            List of RemoteFileInfo objects.
        """
        pass
    
    @abstractmethod
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        """Search for files on remote.
        
        Args:
            remote_path: Root directory to search.
            mode: Filter mode.
            patterns: Glob patterns for filtering.
            recursive: Whether to search recursively.
            
        Returns:
            List of matching file paths.
        """
        pass
    
    @abstractmethod
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        """Read text file from remote.
        
        Args:
            remote_path: Path to file.
            encoding: Text encoding.
            
        Returns:
            File contents as string.
        """
        pass
    
    @abstractmethod
    def read_bytes(self, remote_path: str) -> bytes:
        """Read binary file from remote.
        
        Args:
            remote_path: Path to file.
            
        Returns:
            File contents as bytes.
        """
        pass
    
    @abstractmethod
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """Write text file to remote.
        
        Args:
            remote_path: Path to file.
            content: Text content to write.
            encoding: Text encoding.
        """
        pass
    
    @abstractmethod
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        """Write binary file to remote.
        
        Args:
            remote_path: Path to file.
            content: Binary content to write.
        """
        pass
    
    def copy(
        self,
        src: str,
        dst: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files (auto-detect direction based on path format).
        
        Args:
            src: Source path (local or remote).
            dst: Destination path (local or remote).
            mode: Filter mode.
            patterns: Glob patterns.
            progress: Progress callback.
            
        Returns:
            Number of files copied.
        """
        src_is_remote = self._is_remote_path(src)
        dst_is_remote = self._is_remote_path(dst)
        
        if src_is_remote and not dst_is_remote:
            return self.copy_from(
                self._strip_remote_prefix(src),
                dst,
                mode=mode,
                patterns=patterns,
                progress=progress,
            )
        elif not src_is_remote and dst_is_remote:
            return self.copy_to(
                src,
                self._strip_remote_prefix(dst),
                mode=mode,
                patterns=patterns,
                progress=progress,
            )
        else:
            raise RemoteError(
                "Copy requires one local and one remote path. "
                "For remote-to-remote copy, use two separate operations."
            )
    
    def _is_remote_path(self, path: str) -> bool:
        """Check if path is a remote path (to be overridden by subclasses)."""
        return False
    
    def _strip_remote_prefix(self, path: str) -> str:
        """Strip remote prefix from path (to be overridden by subclasses)."""
        return path
