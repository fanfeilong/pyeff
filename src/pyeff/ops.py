"""Unified file operations using URI-based paths.

This module provides unified operations that work across all backends
(local, Docker, SSH, archive) using URI-style paths.

Example:
    >>> from pyeff import copy
    >>> from pyeff.uri import local, docker, ssh, archive
    >>> 
    >>> # URI strings
    >>> copy("local:./src", "local:./dst")
    >>> copy("docker:my-container:/logs", "local:./logs")
    >>> copy("local:./data", "archive:./backup.zip")
    >>> 
    >>> # Path builders
    >>> copy(local("./src"), docker("container", "/app"))
    >>> copy(ssh("user@host", "/data", key="~/.ssh/id_rsa"), local("./backup"))
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Literal, Optional, Union

from .uri import (
    URIPath,
    LocalPath,
    DockerPath,
    SSHPath,
    ArchivePath,
    resolve_path,
)

Mode = Literal["all", "ignore", "include"]
ProgressCallback = Callable[[str, int, int], None]


class CopyError(Exception):
    """Error during copy operation."""
    pass


def copy(
    src: Union[str, URIPath],
    dst: Union[str, URIPath],
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    overwrite: bool = False,
    progress: Optional[ProgressCallback] = None,
) -> int:
    """Copy files between any two locations.
    
    Supports copying between local filesystem, Docker containers,
    SSH remotes, and archives using URI-style paths.
    
    Args:
        src: Source path (URI string or URIPath object).
        dst: Destination path (URI string or URIPath object).
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        overwrite: Whether to overwrite existing files.
        progress: Optional progress callback(filename, current, total).
        
    Returns:
        Number of files copied.
        
    Raises:
        CopyError: If copy operation fails.
        ValueError: If URI format is invalid.
        
    Example:
        >>> from pyeff import copy
        >>> 
        >>> # Local to local
        >>> copy("local:./src", "local:./dst")
        >>> 
        >>> # Docker to local
        >>> copy("docker:my-container:/app/logs", "local:./logs")
        >>> 
        >>> # Local to Docker
        >>> copy("local:./config", "docker:my-container:/app/config")
        >>> 
        >>> # SSH to local
        >>> copy("ssh:user@host:/var/log", "local:./logs")
        >>> 
        >>> # Local to archive (compress)
        >>> copy("local:./data", "archive:./backup.zip")
        >>> 
        >>> # Archive to local (extract)
        >>> copy("archive:./backup.zip", "local:./restore")
        >>> 
        >>> # With path builders for complex options
        >>> from pyeff.uri import ssh, local
        >>> copy(ssh("user@host", "/data", key="~/.ssh/id_rsa"), local("./backup"))
    """
    src_path = resolve_path(src)
    dst_path = resolve_path(dst)
    
    # Dispatch based on source and destination types
    handler = _get_copy_handler(src_path, dst_path)
    return handler(src_path, dst_path, mode, patterns, overwrite, progress)


def _get_copy_handler(src: URIPath, dst: URIPath):
    """Get the appropriate copy handler for source and destination types."""
    key = (src.scheme, dst.scheme)
    
    handlers = {
        ("local", "local"): _copy_local_to_local,
        ("local", "docker"): _copy_local_to_docker,
        ("local", "ssh"): _copy_local_to_ssh,
        ("local", "archive"): _copy_local_to_archive,
        ("docker", "local"): _copy_docker_to_local,
        ("docker", "docker"): _copy_docker_to_docker,
        ("docker", "ssh"): _copy_docker_to_ssh,
        ("ssh", "local"): _copy_ssh_to_local,
        ("ssh", "docker"): _copy_ssh_to_docker,
        ("ssh", "ssh"): _copy_ssh_to_ssh,
        ("archive", "local"): _copy_archive_to_local,
        ("archive", "docker"): _copy_archive_to_docker,
        ("archive", "ssh"): _copy_archive_to_ssh,
    }
    
    handler = handlers.get(key)
    if handler is None:
        raise CopyError(
            f"Unsupported copy operation: {src.scheme} → {dst.scheme}"
        )
    return handler


# Local operations

def _copy_local_to_local(
    src: LocalPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to local."""
    from .fs import copy as fs_copy
    return fs_copy(src.path, dst.path, mode=mode, patterns=patterns)


def _copy_local_to_docker(
    src: LocalPath,
    dst: DockerPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to Docker container."""
    from .remote.docker import DockerRemote
    
    with DockerRemote(dst.container) as docker:
        return docker.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_local_to_ssh(
    src: LocalPath,
    dst: SSHPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to SSH remote."""
    from .remote.ssh import SSHRemote
    
    params = dst.get_connection_params()
    with SSHRemote(**params) as ssh:
        return ssh.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_local_to_archive(
    src: LocalPath,
    dst: ArchivePath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to archive (compress)."""
    from .archive import compress
    
    archive_path = Path(dst.archive_path)
    if archive_path.exists() and not overwrite:
        raise CopyError(f"Archive already exists: {dst.archive_path}")
    if archive_path.exists() and overwrite:
        archive_path.unlink()
    
    return compress(src.path, dst.archive_path, mode=mode, patterns=patterns, progress=progress)


# Docker operations

def _copy_docker_to_local(
    src: DockerPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy Docker container to local."""
    from .remote.docker import DockerRemote
    
    with DockerRemote(src.container) as docker:
        return docker.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_docker_to_docker(
    src: DockerPath,
    dst: DockerPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy between Docker containers (via local temp)."""
    import tempfile
    import shutil
    from .remote.docker import DockerRemote
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with DockerRemote(src.container) as src_docker:
            src_docker.copy_from(src.path, temp_dir, mode=mode, patterns=patterns)
        
        with DockerRemote(dst.container) as dst_docker:
            return dst_docker.copy_to(temp_dir, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_docker_to_ssh(
    src: DockerPath,
    dst: SSHPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy Docker to SSH (via local temp)."""
    import tempfile
    from .remote.docker import DockerRemote
    from .remote.ssh import SSHRemote
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with DockerRemote(src.container) as docker:
            docker.copy_from(src.path, temp_dir, mode=mode, patterns=patterns)
        
        params = dst.get_connection_params()
        with SSHRemote(**params) as ssh:
            return ssh.copy_to(temp_dir, dst.path, mode=mode, patterns=patterns, progress=progress)


# SSH operations

def _copy_ssh_to_local(
    src: SSHPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy SSH remote to local."""
    from .remote.ssh import SSHRemote
    
    params = src.get_connection_params()
    with SSHRemote(**params) as ssh:
        return ssh.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_ssh_to_docker(
    src: SSHPath,
    dst: DockerPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy SSH to Docker (via local temp)."""
    import tempfile
    from .remote.docker import DockerRemote
    from .remote.ssh import SSHRemote
    
    with tempfile.TemporaryDirectory() as temp_dir:
        params = src.get_connection_params()
        with SSHRemote(**params) as ssh:
            ssh.copy_from(src.path, temp_dir, mode=mode, patterns=patterns)
        
        with DockerRemote(dst.container) as docker:
            return docker.copy_to(temp_dir, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_ssh_to_ssh(
    src: SSHPath,
    dst: SSHPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy between SSH remotes (via local temp)."""
    import tempfile
    from .remote.ssh import SSHRemote
    
    with tempfile.TemporaryDirectory() as temp_dir:
        src_params = src.get_connection_params()
        with SSHRemote(**src_params) as src_ssh:
            src_ssh.copy_from(src.path, temp_dir, mode=mode, patterns=patterns)
        
        dst_params = dst.get_connection_params()
        with SSHRemote(**dst_params) as dst_ssh:
            return dst_ssh.copy_to(temp_dir, dst.path, mode=mode, patterns=patterns, progress=progress)


# Archive operations

def _copy_archive_to_local(
    src: ArchivePath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy archive to local (extract)."""
    from .archive import extract, extract_file
    
    if src.inner_path:
        # Extract specific file
        extract_file(src.archive_path, src.inner_path.lstrip('/'), dst.path)
        return 1
    else:
        return extract(src.archive_path, dst.path, mode=mode, patterns=patterns, 
                      overwrite=overwrite, progress=progress)


def _copy_archive_to_docker(
    src: ArchivePath,
    dst: DockerPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy archive to Docker (extract then copy)."""
    import tempfile
    from .archive import extract
    from .remote.docker import DockerRemote
    
    with tempfile.TemporaryDirectory() as temp_dir:
        extract(src.archive_path, temp_dir, mode=mode, patterns=patterns, overwrite=True)
        
        with DockerRemote(dst.container) as docker:
            return docker.copy_to(temp_dir, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_archive_to_ssh(
    src: ArchivePath,
    dst: SSHPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy archive to SSH (extract then copy)."""
    import tempfile
    from .archive import extract
    from .remote.ssh import SSHRemote
    
    with tempfile.TemporaryDirectory() as temp_dir:
        extract(src.archive_path, temp_dir, mode=mode, patterns=patterns, overwrite=True)
        
        params = dst.get_connection_params()
        with SSHRemote(**params) as ssh:
            return ssh.copy_to(temp_dir, dst.path, mode=mode, patterns=patterns, progress=progress)


__all__ = [
    "copy",
    "CopyError",
]
