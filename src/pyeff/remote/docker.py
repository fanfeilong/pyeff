"""Docker container file operations.

This module provides file operations for Docker containers with
the same API as local fs operations.

Example:
    >>> from pyeff.remote.docker import DockerRemote
    >>> 
    >>> # Using context manager
    >>> with DockerRemote("my-container") as docker:
    ...     docker.copy_from("/app/logs", "./logs")
    ...     docker.remove("/tmp/cache")
    >>> 
    >>> # Or using standalone functions
    >>> from pyeff.remote import docker_copy, docker_search
    >>> docker_copy("my-container:/app/data", "./local/")
    >>> files = docker_search("my-container:/logs", patterns=["*.log"])
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .base import (
    Mode,
    PathLike,
    PatternFilter,
    ProgressCallback,
    RemoteBackend,
    RemoteConnectionError,
    RemoteError,
    RemoteFileInfo,
    RemoteFileNotFoundError,
)


def _run_docker(
    args: List[str],
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run a docker command."""
    cmd = ["docker"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
        )
        return result
    except subprocess.CalledProcessError as e:
        if "No such container" in (e.stderr or ""):
            raise RemoteConnectionError(f"Container not found: {e.stderr}")
        elif "not found" in (e.stderr or "").lower():
            raise RemoteFileNotFoundError(e.stderr)
        else:
            raise RemoteError(f"Docker command failed: {e.stderr}")
    except FileNotFoundError:
        raise RemoteError(
            "Docker CLI not found. Please install Docker and ensure it's in PATH."
        )


def _parse_container_path(path: str) -> Tuple[Optional[str], str]:
    """Parse container:path format.
    
    Returns:
        Tuple of (container_name, path). container_name is None for local paths.
    """
    if ":" in path and not path.startswith("/") and not path.startswith("."):
        parts = path.split(":", 1)
        if len(parts) == 2 and "/" in parts[1]:
            container_name = parts[0]
            if len(container_name) == 1 and container_name.isalpha():
                return None, path
            return container_name, parts[1]
    return None, path


class DockerRemote(RemoteBackend):
    """Docker container file operations.
    
    Provides file operations for Docker containers with the same
    API as local fs operations.
    
    Args:
        container: Container name or ID.
        
    Example:
        >>> with DockerRemote("my-app") as docker:
        ...     docker.copy_from("/app/logs", "./logs")
        ...     files = docker.search("/data", patterns=["*.csv"])
    """
    
    def __init__(self, container: str):
        self.container = container
        self._verified = False
    
    def __enter__(self) -> "DockerRemote":
        self._verify_container()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
    
    def _verify_container(self) -> None:
        """Verify container exists and is running."""
        if self._verified:
            return
        
        result = _run_docker(
            ["inspect", "--format", "{{.State.Running}}", self.container],
            check=False,
        )
        
        if result.returncode != 0:
            raise RemoteConnectionError(f"Container not found: {self.container}")
        
        if result.stdout.strip().lower() != "true":
            raise RemoteConnectionError(f"Container not running: {self.container}")
        
        self._verified = True
    
    def _exec(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute command in container."""
        self._verify_container()
        return _run_docker(["exec", self.container] + cmd, check=check)
    
    def _is_remote_path(self, path: str) -> bool:
        """Check if path is a container path."""
        container, _ = _parse_container_path(path)
        return container is not None
    
    def _strip_remote_prefix(self, path: str) -> str:
        """Strip container: prefix from path."""
        _, remote_path = _parse_container_path(path)
        return remote_path
    
    def exists(self, remote_path: str) -> bool:
        """Check if path exists in container."""
        result = self._exec(["test", "-e", remote_path], check=False)
        return result.returncode == 0
    
    def is_file(self, remote_path: str) -> bool:
        """Check if path is a file in container."""
        result = self._exec(["test", "-f", remote_path], check=False)
        return result.returncode == 0
    
    def is_dir(self, remote_path: str) -> bool:
        """Check if path is a directory in container."""
        result = self._exec(["test", "-d", remote_path], check=False)
        return result.returncode == 0
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        """List files in container directory."""
        if not self.is_dir(remote_path):
            raise RemoteFileNotFoundError(f"Directory not found: {remote_path}")
        
        result = self._exec(["ls", "-la", remote_path])
        lines = result.stdout.strip().split("\n")
        
        filter_obj = PatternFilter(mode, patterns)
        files: List[RemoteFileInfo] = []
        
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 9:
                continue
            
            mode_str = parts[0]
            size = int(parts[4]) if parts[4].isdigit() else 0
            name = " ".join(parts[8:])
            
            if name in (".", ".."):
                continue
            
            if not filter_obj.match(name):
                continue
            
            is_dir = mode_str.startswith("d")
            full_path = f"{remote_path.rstrip('/')}/{name}"
            
            files.append(RemoteFileInfo(
                name=name,
                path=full_path,
                size=size,
                is_dir=is_dir,
                is_file=not is_dir,
                mode=mode_str,
            ))
        
        return files
    
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        """Search for files in container."""
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        find_args = ["find", remote_path]
        if not recursive:
            find_args.extend(["-maxdepth", "1"])
        find_args.extend(["-type", "f"])
        
        result = self._exec(find_args, check=False)
        if result.returncode != 0:
            return []
        
        all_files = result.stdout.strip().split("\n")
        all_files = [f for f in all_files if f]
        
        filter_obj = PatternFilter(mode, patterns)
        return [f for f in all_files if filter_obj.match(f)]
    
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files from container to local."""
        self._verify_container()
        local = Path(local_path)
        
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        if mode == "all" and not patterns:
            local.parent.mkdir(parents=True, exist_ok=True)
            _run_docker(["cp", f"{self.container}:{remote_path}", str(local)])
            
            if progress:
                progress(remote_path, 1, 1)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        total = len(files)
        count = 0
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, remote_file in enumerate(files):
                rel_path = os.path.relpath(remote_file, remote_path)
                local_file = local / rel_path
                local_file.parent.mkdir(parents=True, exist_ok=True)
                
                tmp_file = Path(tmpdir) / f"file_{i}"
                _run_docker(["cp", f"{self.container}:{remote_file}", str(tmp_file)])
                shutil.move(str(tmp_file), str(local_file))
                
                count += 1
                if progress:
                    progress(remote_file, count, total)
        
        return count
    
    def copy_to(
        self,
        local_path: PathLike,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files from local to container."""
        self._verify_container()
        local = Path(local_path)
        
        if not local.exists():
            raise FileNotFoundError(f"Local path not found: {local_path}")
        
        if mode == "all" and not patterns:
            _run_docker(["cp", str(local), f"{self.container}:{remote_path}"])
            
            if progress:
                progress(str(local), 1, 1)
            return 1
        
        filter_obj = PatternFilter(mode, patterns)
        
        if local.is_file():
            if filter_obj.match(local.name):
                _run_docker(["cp", str(local), f"{self.container}:{remote_path}"])
                if progress:
                    progress(str(local), 1, 1)
                return 1
            return 0
        
        files_to_copy: List[Tuple[Path, str]] = []
        for root, dirs, files in os.walk(local):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                rel_path = file_path.relative_to(local)
                if filter_obj.match(str(rel_path)):
                    remote_file = f"{remote_path.rstrip('/')}/{rel_path}"
                    files_to_copy.append((file_path, remote_file))
        
        total = len(files_to_copy)
        count = 0
        
        for local_file, remote_file in files_to_copy:
            remote_dir = str(Path(remote_file).parent)
            self._exec(["mkdir", "-p", remote_dir], check=False)
            _run_docker(["cp", str(local_file), f"{self.container}:{remote_file}"])
            
            count += 1
            if progress:
                progress(str(local_file), count, total)
        
        return count
    
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        """Remove files in container."""
        if not self.exists(remote_path):
            return 0
        
        if mode == "all" and not patterns:
            rm_args = ["rm"]
            if recursive:
                rm_args.append("-rf")
            rm_args.append(remote_path)
            self._exec(rm_args)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        count = 0
        
        for remote_file in files:
            self._exec(["rm", "-f", remote_file], check=False)
            count += 1
        
        return count
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        """Read text file from container."""
        if not self.is_file(remote_path):
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        
        result = self._exec(["cat", remote_path])
        return result.stdout
    
    def read_bytes(self, remote_path: str) -> bytes:
        """Read binary file from container."""
        if not self.is_file(remote_path):
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            _run_docker(["cp", f"{self.container}:{remote_path}", tmp_path])
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            os.unlink(tmp_path)
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """Write text file to container."""
        with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            remote_dir = str(Path(remote_path).parent)
            self._exec(["mkdir", "-p", remote_dir], check=False)
            _run_docker(["cp", tmp_path, f"{self.container}:{remote_path}"])
        finally:
            os.unlink(tmp_path)
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        """Write binary file to container."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            remote_dir = str(Path(remote_path).parent)
            self._exec(["mkdir", "-p", remote_dir], check=False)
            _run_docker(["cp", tmp_path, f"{self.container}:{remote_path}"])
        finally:
            os.unlink(tmp_path)
    
    def copy(
        self,
        src: str,
        dst: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files between container and local filesystem.
        
        Direction is auto-detected based on path format:
        - Absolute path (starts with /) = container path
        - Relative path (starts with . or other) = local path
        
        Args:
            src: Source path (container or local).
            dst: Destination path (container or local).
            mode: Filter mode ("all", "include", "ignore").
            patterns: Glob patterns for filtering.
            progress: Optional progress callback.
            
        Returns:
            Number of files copied.
            
        Example:
            >>> with docker("my-container") as d:
            ...     d.copy("/app/logs", "./logs")      # container → local
            ...     d.copy("./config", "/app/config")  # local → container
        """
        src_is_remote = src.startswith("/")
        dst_is_remote = dst.startswith("/")
        
        if src_is_remote and dst_is_remote:
            raise RemoteError(
                "Both paths appear to be container paths. "
                "Use relative path (./...) for local path."
            )
        
        if not src_is_remote and not dst_is_remote:
            raise RemoteError(
                "Both paths appear to be local paths. "
                "Use absolute path (/...) for container path."
            )
        
        if src_is_remote:
            return self.copy_from(src, dst, mode, patterns, progress)
        else:
            return self.copy_to(src, dst, mode, patterns, progress)


def docker_copy(
    src: str,
    dst: str,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    progress: Optional[ProgressCallback] = None,
) -> int:
    """Copy files between Docker container and local filesystem.
    
    Args:
        src: Source path (container:path or local path).
        dst: Destination path (container:path or local path).
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        progress: Optional progress callback.
        
    Returns:
        Number of files copied.
        
    Example:
        >>> docker_copy("my-container:/app/logs", "./logs")
        >>> docker_copy("./config", "my-container:/app/config")
        >>> docker_copy("my-container:/data", "./data", 
        ...             mode="include", patterns=["*.csv"])
    """
    src_container, src_path = _parse_container_path(src)
    dst_container, dst_path = _parse_container_path(dst)
    
    if src_container and dst_container:
        raise RemoteError(
            "Container-to-container copy not supported. "
            "Use two separate operations."
        )
    
    if not src_container and not dst_container:
        raise RemoteError(
            "At least one path must be a container path (container:path)"
        )
    
    container = src_container or dst_container
    
    with DockerRemote(container) as docker:
        if src_container:
            return docker.copy_from(src_path, dst_path, mode, patterns, progress)
        else:
            return docker.copy_to(src_path, dst_path, mode, patterns, progress)


def docker_remove(
    path: str,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    recursive: bool = True,
) -> int:
    """Remove files in Docker container.
    
    Args:
        path: Container path (container:path format).
        mode: Filter mode.
        patterns: Glob patterns for filtering.
        recursive: Whether to remove directories recursively.
        
    Returns:
        Number of files removed.
        
    Example:
        >>> docker_remove("my-container:/tmp/cache")
        >>> docker_remove("my-container:/logs", mode="include", patterns=["*.tmp"])
    """
    container, remote_path = _parse_container_path(path)
    
    if not container:
        raise RemoteError("Path must be in container:path format")
    
    with DockerRemote(container) as docker:
        return docker.remove(remote_path, mode, patterns, recursive)


def docker_search(
    path: str,
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    recursive: bool = True,
) -> List[str]:
    """Search for files in Docker container.
    
    Args:
        path: Container path (container:path format).
        mode: Filter mode.
        patterns: Glob patterns for filtering.
        recursive: Whether to search recursively.
        
    Returns:
        List of matching file paths.
        
    Example:
        >>> docker_search("my-container:/logs", patterns=["*.log"])
        >>> docker_search("my-container:/data", mode="include", patterns=["*.csv"])
    """
    container, remote_path = _parse_container_path(path)
    
    if not container:
        raise RemoteError("Path must be in container:path format")
    
    with DockerRemote(container) as docker:
        return docker.search(remote_path, mode, patterns, recursive)


def docker_exists(path: str) -> bool:
    """Check if path exists in Docker container.
    
    Args:
        path: Container path (container:path format).
        
    Returns:
        True if path exists.
        
    Example:
        >>> docker_exists("my-container:/app/config.json")
    """
    container, remote_path = _parse_container_path(path)
    
    if not container:
        raise RemoteError("Path must be in container:path format")
    
    with DockerRemote(container) as docker:
        return docker.exists(remote_path)


def docker_read(path: str, encoding: Optional[str] = "utf-8") -> Union[str, bytes]:
    """Read file from Docker container.
    
    Args:
        path: Container path (container:path format).
        encoding: Text encoding (None for binary).
        
    Returns:
        File contents as string or bytes.
        
    Example:
        >>> content = docker_read("my-container:/app/config.json")
        >>> data = docker_read("my-container:/app/data.bin", encoding=None)
    """
    container, remote_path = _parse_container_path(path)
    
    if not container:
        raise RemoteError("Path must be in container:path format")
    
    with DockerRemote(container) as docker:
        if encoding:
            return docker.read_text(remote_path, encoding)
        else:
            return docker.read_bytes(remote_path)


def docker_write(
    path: str,
    content: Union[str, bytes],
    encoding: str = "utf-8",
) -> None:
    """Write file to Docker container.
    
    Args:
        path: Container path (container:path format).
        content: Content to write (string or bytes).
        encoding: Text encoding (for string content).
        
    Example:
        >>> docker_write("my-container:/app/config.json", '{"key": "value"}')
        >>> docker_write("my-container:/app/data.bin", b"binary data")
    """
    container, remote_path = _parse_container_path(path)
    
    if not container:
        raise RemoteError("Path must be in container:path format")
    
    with DockerRemote(container) as docker:
        if isinstance(content, bytes):
            docker.write_bytes(remote_path, content)
        else:
            docker.write_text(remote_path, content, encoding)


def docker(container: str) -> DockerRemote:
    """Create a Docker remote interface.
    
    Factory function for creating DockerRemote instances with
    a cleaner API.
    
    Args:
        container: Container name or ID.
        
    Returns:
        DockerRemote instance (use as context manager).
        
    Example:
        >>> from pyeff.remote import docker
        >>> 
        >>> with docker("my-container") as d:
        ...     # copy() auto-detects direction based on path
        ...     d.copy("/app/logs", "./logs")      # container → local
        ...     d.copy("./config", "/app/config")  # local → container
        ...     
        ...     d.remove("/tmp/cache")
        ...     files = d.search("/data", patterns=["*.csv"])
    """
    return DockerRemote(container)
