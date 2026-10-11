"""Unified file operations using URI-based paths.

This module provides unified operations that work across all backends
(local, Docker, SSH, archive) using URI-style paths.

Example:
    >>> from pyeff import copy, remove, search, exists, read, write
    >>> from pyeff.uri import local, docker, ssh, archive
    >>> 
    >>> # Copy
    >>> copy("local:./src", "docker:my-container:/app")
    >>> copy("ssh:user@host:/data", "local:./backup")
    >>> 
    >>> # Remove
    >>> remove("local:./temp")
    >>> remove("docker:my-container:/tmp/cache")
    >>> 
    >>> # Search
    >>> files = search("ssh:user@host:/var/log", patterns=["*.log"])
    >>> 
    >>> # Exists
    >>> if exists("docker:my-container:/app/config.json"):
    ...     print("Config exists")
    >>> 
    >>> # Read/Write
    >>> content = read("ssh:user@host:/etc/config")
    >>> write("docker:my-container:/app/config.json", '{"key": "value"}')
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Literal, Optional, Union

from .uri import (
    URIPath,
    LocalPath,
    DockerPath,
    SSHPath,
    K8sPath,
    S3Path,
    GCSPath,
    AzurePath,
    HTTPPath,
    SMBPath,
    WebDAVPath,
    ArchivePath,
    resolve_path,
)

Mode = Literal["all", "ignore", "include"]
ProgressCallback = Callable[[str, int, int], None]


class OperationError(Exception):
    """Base error for unified operations."""
    pass


class CopyError(OperationError):
    """Error during copy operation."""
    pass


class RemoveError(OperationError):
    """Error during remove operation."""
    pass


class SearchError(OperationError):
    """Error during search operation."""
    pass


class ReadError(OperationError):
    """Error during read operation."""
    pass


class WriteError(OperationError):
    """Error during write operation."""
    pass


@dataclass
class FileInfo:
    """Information about a file."""
    name: str
    path: str
    size: int
    is_dir: bool
    is_file: bool


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
    
    _TEMP = _copy_via_temp
    
    handlers = {
        ("local", "local"): _copy_local_to_local,
        ("local", "docker"): _copy_local_to_docker,
        ("local", "ssh"): _copy_local_to_ssh,
        ("local", "k8s"): _copy_local_to_k8s,
        ("local", "s3"): _copy_local_to_s3,
        ("local", "gs"): _copy_local_to_gs,
        ("local", "az"): _copy_local_to_az,
        ("local", "http"): _copy_local_to_http,
        ("local", "https"): _copy_local_to_http,
        ("local", "smb"): _copy_local_to_smb,
        ("local", "webdav"): _copy_local_to_webdav,
        ("local", "webdavs"): _copy_local_to_webdav,
        ("local", "archive"): _copy_local_to_archive,
        ("docker", "local"): _copy_docker_to_local,
        ("docker", "docker"): _copy_docker_to_docker,
        ("docker", "ssh"): _copy_docker_to_ssh,
        ("ssh", "local"): _copy_ssh_to_local,
        ("ssh", "docker"): _copy_ssh_to_docker,
        ("ssh", "ssh"): _copy_ssh_to_ssh,
        ("k8s", "local"): _copy_k8s_to_local,
        ("s3", "local"): _copy_s3_to_local,
        ("gs", "local"): _copy_gs_to_local,
        ("az", "local"): _copy_az_to_local,
        ("http", "local"): _copy_http_to_local,
        ("https", "local"): _copy_http_to_local,
        ("smb", "local"): _copy_smb_to_local,
        ("webdav", "local"): _copy_webdav_to_local,
        ("webdavs", "local"): _copy_webdav_to_local,
        ("archive", "local"): _copy_archive_to_local,
        ("archive", "docker"): _copy_archive_to_docker,
        ("archive", "ssh"): _copy_archive_to_ssh,
        ("archive", "k8s"): _copy_archive_to_k8s,
    }
    
    remotes = (
        "docker", "ssh", "k8s", "s3", "gs", "az",
        "http", "https", "smb", "webdav", "webdavs",
    )
    for a in remotes:
        for b in remotes:
            if (a, b) not in handlers:
                handlers[(a, b)] = _TEMP
    for scheme in remotes:
        if ("archive", scheme) not in handlers:
            handlers[("archive", scheme)] = _copy_archive_via_temp
    
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


def _copy_local_to_k8s(
    src: LocalPath,
    dst: K8sPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to Kubernetes pod."""
    from .remote.k8s import K8sRemote
    
    params = dst.get_connection_params()
    with K8sRemote(**params) as k:
        return k.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_local_to_s3(
    src: LocalPath,
    dst: S3Path,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to S3."""
    from .remote.s3 import S3Remote
    
    with S3Remote(**dst.get_connection_params()) as client:
        return client.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_local_to_gs(
    src: LocalPath,
    dst: GCSPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to GCS."""
    from .remote.gcs import GCSRemote
    
    with GCSRemote(**dst.get_connection_params()) as client:
        return client.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_local_to_az(
    src: LocalPath,
    dst: AzurePath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to Azure Blob."""
    from .remote.azure import AzureRemote
    
    with AzureRemote(**dst.get_connection_params()) as client:
        return client.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_local_to_http(
    src: LocalPath,
    dst: HTTPPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Upload local file via HTTP PUT."""
    from .remote.http import HTTPRemote
    
    with HTTPRemote(**dst.get_connection_params()) as client:
        return client.copy_to(
            src.path, dst.get_url_path(),
            mode=mode, patterns=patterns, progress=progress,
        )


def _copy_local_to_smb(
    src: LocalPath,
    dst: SMBPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to SMB share."""
    from .remote.smb import SMBRemote
    
    with SMBRemote(**dst.get_connection_params()) as client:
        return client.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_local_to_webdav(
    src: LocalPath,
    dst: WebDAVPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy local to WebDAV."""
    from .remote.webdav import WebDAVRemote
    
    with WebDAVRemote(**dst.get_connection_params()) as client:
        return client.copy_to(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


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


def _open_remote(path: URIPath):
    """Open a remote backend context manager for a URI path."""
    if isinstance(path, DockerPath):
        from .remote.docker import DockerRemote
        return DockerRemote(path.container)
    elif isinstance(path, SSHPath):
        from .remote.ssh import SSHRemote
        return SSHRemote(**path.get_connection_params())
    elif isinstance(path, K8sPath):
        from .remote.k8s import K8sRemote
        return K8sRemote(**path.get_connection_params())
    elif isinstance(path, S3Path):
        from .remote.s3 import S3Remote
        return S3Remote(**path.get_connection_params())
    elif isinstance(path, GCSPath):
        from .remote.gcs import GCSRemote
        return GCSRemote(**path.get_connection_params())
    elif isinstance(path, AzurePath):
        from .remote.azure import AzureRemote
        return AzureRemote(**path.get_connection_params())
    elif isinstance(path, HTTPPath):
        from .remote.http import HTTPRemote
        return HTTPRemote(**path.get_connection_params())
    elif isinstance(path, SMBPath):
        from .remote.smb import SMBRemote
        return SMBRemote(**path.get_connection_params())
    elif isinstance(path, WebDAVPath):
        from .remote.webdav import WebDAVRemote
        return WebDAVRemote(**path.get_connection_params())
    else:
        raise CopyError(f"Not a remote path: {path.scheme}")


def _remote_path_arg(path: URIPath) -> str:
    """Get the path argument for remote backend operations."""
    if isinstance(path, HTTPPath):
        return path.get_url_path()
    return path.path


def _copy_via_temp(
    src: URIPath,
    dst: URIPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy between remotes via local temp directory."""
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with _open_remote(src) as src_remote:
            src_remote.copy_from(
                _remote_path_arg(src), temp_dir, mode=mode, patterns=patterns
            )
        
        with _open_remote(dst) as dst_remote:
            return dst_remote.copy_to(
                temp_dir, _remote_path_arg(dst),
                mode=mode, patterns=patterns, progress=progress,
            )


def _copy_archive_via_temp(
    src: ArchivePath,
    dst: URIPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Extract archive then copy to remote."""
    import tempfile
    from .archive import extract
    
    with tempfile.TemporaryDirectory() as temp_dir:
        extract(src.archive_path, temp_dir, mode=mode, patterns=patterns, overwrite=True)
        with _open_remote(dst) as dst_remote:
            return dst_remote.copy_to(
                temp_dir, _remote_path_arg(dst),
                mode=mode, patterns=patterns, progress=progress,
            )


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
    return _copy_via_temp(src, dst, mode, patterns, overwrite, progress)


# K8s operations

def _copy_k8s_to_local(
    src: K8sPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy Kubernetes pod to local."""
    from .remote.k8s import K8sRemote
    
    params = src.get_connection_params()
    with K8sRemote(**params) as k:
        return k.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_s3_to_local(
    src: S3Path,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy S3 to local."""
    from .remote.s3 import S3Remote
    
    with S3Remote(**src.get_connection_params()) as client:
        return client.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_gs_to_local(
    src: GCSPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy GCS to local."""
    from .remote.gcs import GCSRemote
    
    with GCSRemote(**src.get_connection_params()) as client:
        return client.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_az_to_local(
    src: AzurePath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy Azure Blob to local."""
    from .remote.azure import AzureRemote
    
    with AzureRemote(**src.get_connection_params()) as client:
        return client.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_http_to_local(
    src: HTTPPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Download HTTP(S) URL to local."""
    from .remote.http import HTTPRemote
    
    with HTTPRemote(**src.get_connection_params()) as client:
        return client.copy_from(
            src.get_url_path(), dst.path,
            mode=mode, patterns=patterns, progress=progress,
        )


def _copy_smb_to_local(
    src: SMBPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy SMB share to local."""
    from .remote.smb import SMBRemote
    
    with SMBRemote(**src.get_connection_params()) as client:
        return client.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


def _copy_webdav_to_local(
    src: WebDAVPath,
    dst: LocalPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy WebDAV to local."""
    from .remote.webdav import WebDAVRemote
    
    with WebDAVRemote(**src.get_connection_params()) as client:
        return client.copy_from(src.path, dst.path, mode=mode, patterns=patterns, progress=progress)


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


def _copy_archive_to_k8s(
    src: ArchivePath,
    dst: K8sPath,
    mode: Mode,
    patterns: Optional[List[str]],
    overwrite: bool,
    progress: Optional[ProgressCallback],
) -> int:
    """Copy archive to Kubernetes pod (extract then copy)."""
    import tempfile
    from .archive import extract
    from .remote.k8s import K8sRemote
    
    with tempfile.TemporaryDirectory() as temp_dir:
        extract(src.archive_path, temp_dir, mode=mode, patterns=patterns, overwrite=True)
        
        params = dst.get_connection_params()
        with K8sRemote(**params) as k:
            return k.copy_to(temp_dir, dst.path, mode=mode, patterns=patterns, progress=progress)


def remove(
    path: Union[str, URIPath],
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    recursive: bool = True,
    missing_ok: bool = True,
) -> int:
    """Remove files or directories.
    
    Args:
        path: Path to remove (URI string or URIPath object).
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        recursive: Whether to remove directories recursively.
        missing_ok: If True, don't raise error if path doesn't exist.
        
    Returns:
        Number of items removed.
        
    Example:
        >>> remove("local:./temp")
        >>> remove("docker:my-container:/tmp/cache")
        >>> remove("ssh:user@host:/var/log", patterns=["*.tmp"])
    """
    uri_path = resolve_path(path)
    
    if isinstance(uri_path, LocalPath):
        from .fs import remove as fs_remove
        return fs_remove(uri_path.path, mode=mode, patterns=patterns, missing_ok=missing_ok)
    
    elif isinstance(uri_path, DockerPath):
        from .remote.docker import DockerRemote
        with DockerRemote(uri_path.container) as docker:
            return docker.remove(uri_path.path, mode=mode, patterns=patterns, recursive=recursive)
    
    elif isinstance(uri_path, SSHPath):
        from .remote.ssh import SSHRemote
        params = uri_path.get_connection_params()
        with SSHRemote(**params) as ssh:
            return ssh.remove(uri_path.path, mode=mode, patterns=patterns, recursive=recursive)
    
    elif isinstance(uri_path, K8sPath):
        from .remote.k8s import K8sRemote
        params = uri_path.get_connection_params()
        with K8sRemote(**params) as k:
            return k.remove(uri_path.path, mode=mode, patterns=patterns, recursive=recursive)
    
    elif isinstance(uri_path, (S3Path, GCSPath, AzurePath, HTTPPath, SMBPath, WebDAVPath)):
        with _open_remote(uri_path) as client:
            return client.remove(
                _remote_path_arg(uri_path),
                mode=mode, patterns=patterns, recursive=recursive,
            )
    
    elif isinstance(uri_path, ArchivePath):
        raise RemoveError("Cannot remove from archive directly")
    
    else:
        raise RemoveError(f"Unsupported path type: {type(uri_path)}")


def search(
    path: Union[str, URIPath],
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    recursive: bool = True,
) -> List[str]:
    """Search for files.
    
    Args:
        path: Path to search in (URI string or URIPath object).
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        recursive: Whether to search subdirectories.
        
    Returns:
        List of matching file paths.
        
    Example:
        >>> files = search("local:./src", patterns=["*.py"])
        >>> files = search("docker:my-container:/logs", patterns=["*.log"])
        >>> files = search("ssh:user@host:/data", patterns=["*.csv"])
    """
    uri_path = resolve_path(path)
    
    if isinstance(uri_path, LocalPath):
        from .fs import search as fs_search
        return fs_search(uri_path.path, mode=mode, patterns=patterns)
    
    elif isinstance(uri_path, DockerPath):
        from .remote.docker import DockerRemote
        with DockerRemote(uri_path.container) as docker:
            return docker.search(uri_path.path, mode=mode, patterns=patterns, recursive=recursive)
    
    elif isinstance(uri_path, SSHPath):
        from .remote.ssh import SSHRemote
        params = uri_path.get_connection_params()
        with SSHRemote(**params) as ssh:
            return ssh.search(uri_path.path, mode=mode, patterns=patterns, recursive=recursive)
    
    elif isinstance(uri_path, K8sPath):
        from .remote.k8s import K8sRemote
        params = uri_path.get_connection_params()
        with K8sRemote(**params) as k:
            return k.search(uri_path.path, mode=mode, patterns=patterns, recursive=recursive)
    
    elif isinstance(uri_path, (S3Path, GCSPath, AzurePath, HTTPPath, SMBPath, WebDAVPath)):
        with _open_remote(uri_path) as client:
            return client.search(
                _remote_path_arg(uri_path),
                mode=mode, patterns=patterns, recursive=recursive,
            )
    
    elif isinstance(uri_path, ArchivePath):
        from .archive import list_archive
        members = list_archive(uri_path.archive_path, mode=mode, patterns=patterns)
        return [m.name for m in members if m.is_file]
    
    else:
        raise SearchError(f"Unsupported path type: {type(uri_path)}")


def exists(path: Union[str, URIPath]) -> bool:
    """Check if path exists.
    
    Args:
        path: Path to check (URI string or URIPath object).
        
    Returns:
        True if path exists, False otherwise.
        
    Example:
        >>> exists("local:./config.json")
        >>> exists("docker:my-container:/app/data")
        >>> exists("ssh:user@host:/var/log")
    """
    uri_path = resolve_path(path)
    
    if isinstance(uri_path, LocalPath):
        return Path(uri_path.path).exists()
    
    elif isinstance(uri_path, DockerPath):
        from .remote.docker import DockerRemote
        with DockerRemote(uri_path.container) as docker:
            return docker.exists(uri_path.path)
    
    elif isinstance(uri_path, SSHPath):
        from .remote.ssh import SSHRemote
        params = uri_path.get_connection_params()
        with SSHRemote(**params) as ssh:
            return ssh.exists(uri_path.path)
    
    elif isinstance(uri_path, K8sPath):
        from .remote.k8s import K8sRemote
        params = uri_path.get_connection_params()
        with K8sRemote(**params) as k:
            return k.exists(uri_path.path)
    
    elif isinstance(uri_path, (S3Path, GCSPath, AzurePath, HTTPPath, SMBPath, WebDAVPath)):
        with _open_remote(uri_path) as client:
            return client.exists(_remote_path_arg(uri_path))
    
    elif isinstance(uri_path, ArchivePath):
        from .archive import list_archive
        if not Path(uri_path.archive_path).exists():
            return False
        if uri_path.inner_path:
            members = list_archive(uri_path.archive_path)
            inner = uri_path.inner_path.lstrip('/')
            return any(m.name == inner or m.name.startswith(inner + '/') for m in members)
        return True
    
    else:
        return False


def listdir(
    path: Union[str, URIPath],
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
) -> List[FileInfo]:
    """List directory contents.
    
    Args:
        path: Directory path (URI string or URIPath object).
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        
    Returns:
        List of FileInfo objects.
        
    Example:
        >>> items = listdir("local:./src")
        >>> items = listdir("docker:my-container:/app")
        >>> items = listdir("ssh:user@host:/home/user")
    """
    uri_path = resolve_path(path)
    
    if isinstance(uri_path, LocalPath):
        from .fs import listdir as fs_listdir
        items = fs_listdir(uri_path.path)
        results = []
        for item in items:
            p = Path(item) if not isinstance(item, Path) else item
            results.append(FileInfo(
                name=p.name,
                path=str(p),
                size=p.stat().st_size if p.is_file() else 0,
                is_dir=p.is_dir(),
                is_file=p.is_file(),
            ))
        return results
    
    elif isinstance(uri_path, DockerPath):
        from .remote.docker import DockerRemote
        with DockerRemote(uri_path.container) as docker:
            items = docker.listdir(uri_path.path, mode=mode, patterns=patterns)
            return [FileInfo(
                name=i.name, path=i.path, size=i.size,
                is_dir=i.is_dir, is_file=i.is_file
            ) for i in items]
    
    elif isinstance(uri_path, SSHPath):
        from .remote.ssh import SSHRemote
        params = uri_path.get_connection_params()
        with SSHRemote(**params) as ssh:
            items = ssh.listdir(uri_path.path, mode=mode, patterns=patterns)
            return [FileInfo(
                name=i.name, path=i.path, size=i.size,
                is_dir=i.is_dir, is_file=i.is_file
            ) for i in items]
    
    elif isinstance(uri_path, K8sPath):
        from .remote.k8s import K8sRemote
        params = uri_path.get_connection_params()
        with K8sRemote(**params) as k:
            items = k.listdir(uri_path.path, mode=mode, patterns=patterns)
            return [FileInfo(
                name=i.name, path=i.path, size=i.size,
                is_dir=i.is_dir, is_file=i.is_file
            ) for i in items]
    
    elif isinstance(uri_path, (S3Path, GCSPath, AzurePath, SMBPath, WebDAVPath)):
        with _open_remote(uri_path) as client:
            items = client.listdir(
                _remote_path_arg(uri_path), mode=mode, patterns=patterns
            )
            return [FileInfo(
                name=i.name, path=i.path, size=i.size,
                is_dir=i.is_dir, is_file=i.is_file
            ) for i in items]
    
    elif isinstance(uri_path, HTTPPath):
        raise OperationError("listdir is not supported for HTTP URLs")
    
    elif isinstance(uri_path, ArchivePath):
        from .archive import list_archive
        members = list_archive(uri_path.archive_path, mode=mode, patterns=patterns)
        return [FileInfo(
            name=m.name, path=m.name, size=m.size,
            is_dir=m.is_dir, is_file=m.is_file
        ) for m in members]
    
    else:
        raise OperationError(f"Unsupported path type: {type(uri_path)}")


def read(
    path: Union[str, URIPath],
    encoding: str = "utf-8",
    binary: bool = False,
) -> Union[str, bytes]:
    """Read file content.
    
    Args:
        path: File path (URI string or URIPath object).
        encoding: Text encoding (ignored if binary=True).
        binary: If True, return bytes instead of string.
        
    Returns:
        File content as string or bytes.
        
    Example:
        >>> content = read("local:./config.json")
        >>> content = read("docker:my-container:/app/config.json")
        >>> content = read("ssh:user@host:/etc/config")
        >>> data = read("archive:./backup.zip:/config.json")
    """
    uri_path = resolve_path(path)
    
    if isinstance(uri_path, LocalPath):
        p = Path(uri_path.path)
        if binary:
            return p.read_bytes()
        return p.read_text(encoding=encoding)
    
    elif isinstance(uri_path, DockerPath):
        from .remote.docker import DockerRemote
        with DockerRemote(uri_path.container) as docker:
            if binary:
                return docker.read_bytes(uri_path.path)
            return docker.read_text(uri_path.path, encoding=encoding)
    
    elif isinstance(uri_path, SSHPath):
        from .remote.ssh import SSHRemote
        params = uri_path.get_connection_params()
        with SSHRemote(**params) as ssh:
            if binary:
                return ssh.read_bytes(uri_path.path)
            return ssh.read_text(uri_path.path, encoding=encoding)
    
    elif isinstance(uri_path, K8sPath):
        from .remote.k8s import K8sRemote
        params = uri_path.get_connection_params()
        with K8sRemote(**params) as k:
            if binary:
                return k.read_bytes(uri_path.path)
            return k.read_text(uri_path.path, encoding=encoding)
    
    elif isinstance(uri_path, (S3Path, GCSPath, AzurePath, HTTPPath, SMBPath, WebDAVPath)):
        with _open_remote(uri_path) as client:
            if binary:
                return client.read_bytes(_remote_path_arg(uri_path))
            return client.read_text(_remote_path_arg(uri_path), encoding=encoding)
    
    elif isinstance(uri_path, ArchivePath):
        from .archive import extract_file
        if not uri_path.inner_path:
            raise ReadError("Must specify inner path for archive: archive:./path.zip:/file.txt")
        data = extract_file(uri_path.archive_path, uri_path.inner_path.lstrip('/'))
        if binary:
            return data
        return data.decode(encoding)
    
    else:
        raise ReadError(f"Unsupported path type: {type(uri_path)}")


def write(
    path: Union[str, URIPath],
    content: Union[str, bytes],
    encoding: str = "utf-8",
) -> None:
    """Write file content.
    
    Args:
        path: File path (URI string or URIPath object).
        content: Content to write (string or bytes).
        encoding: Text encoding (for string content).
        
    Example:
        >>> write("local:./config.json", '{"key": "value"}')
        >>> write("docker:my-container:/app/config.json", '{"key": "value"}')
        >>> write("ssh:user@host:/tmp/data.txt", "Hello World")
    """
    uri_path = resolve_path(path)
    
    if isinstance(uri_path, LocalPath):
        p = Path(uri_path.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding=encoding)
    
    elif isinstance(uri_path, DockerPath):
        from .remote.docker import DockerRemote
        with DockerRemote(uri_path.container) as docker:
            if isinstance(content, bytes):
                docker.write_bytes(uri_path.path, content)
            else:
                docker.write_text(uri_path.path, content, encoding=encoding)
    
    elif isinstance(uri_path, SSHPath):
        from .remote.ssh import SSHRemote
        params = uri_path.get_connection_params()
        with SSHRemote(**params) as ssh:
            if isinstance(content, bytes):
                ssh.write_bytes(uri_path.path, content)
            else:
                ssh.write_text(uri_path.path, content, encoding=encoding)
    
    elif isinstance(uri_path, K8sPath):
        from .remote.k8s import K8sRemote
        params = uri_path.get_connection_params()
        with K8sRemote(**params) as k:
            if isinstance(content, bytes):
                k.write_bytes(uri_path.path, content)
            else:
                k.write_text(uri_path.path, content, encoding=encoding)
    
    elif isinstance(uri_path, (S3Path, GCSPath, AzurePath, HTTPPath, SMBPath, WebDAVPath)):
        with _open_remote(uri_path) as client:
            if isinstance(content, bytes):
                client.write_bytes(_remote_path_arg(uri_path), content)
            else:
                client.write_text(_remote_path_arg(uri_path), content, encoding=encoding)
    
    elif isinstance(uri_path, ArchivePath):
        raise WriteError("Cannot write to archive directly. Use copy() to create archives.")
    
    else:
        raise WriteError(f"Unsupported path type: {type(uri_path)}")


def move(
    src: Union[str, URIPath],
    dst: Union[str, URIPath],
    mode: Mode = "all",
    patterns: Optional[List[str]] = None,
    overwrite: bool = False,
) -> int:
    """Move files between locations.
    
    For cross-backend moves, this is equivalent to copy + remove.
    
    Args:
        src: Source path (URI string or URIPath object).
        dst: Destination path (URI string or URIPath object).
        mode: Filter mode ("all", "include", "ignore").
        patterns: Glob patterns for filtering.
        overwrite: Whether to overwrite existing files.
        
    Returns:
        Number of files moved.
        
    Example:
        >>> move("local:./old", "local:./new")
        >>> move("docker:my-container:/tmp/data", "local:./data")
    """
    src_path = resolve_path(src)
    dst_path = resolve_path(dst)
    
    # Same backend local move
    if isinstance(src_path, LocalPath) and isinstance(dst_path, LocalPath):
        from .fs import move as fs_move
        return fs_move(src_path.path, dst_path.path, mode=mode, patterns=patterns)
    
    # Cross-backend: copy then remove
    count = copy(src, dst, mode=mode, patterns=patterns, overwrite=overwrite)
    remove(src, mode=mode, patterns=patterns)
    return count


__all__ = [
    # Operations
    "copy",
    "remove",
    "search",
    "exists",
    "listdir",
    "read",
    "write",
    "move",
    # Types
    "FileInfo",
    # Errors
    "OperationError",
    "CopyError",
    "RemoveError",
    "SearchError",
    "ReadError",
    "WriteError",
]
