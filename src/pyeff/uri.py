"""URI-based path abstraction for unified file operations.

This module provides a URI-style path system for consistent file operations
across local filesystem, Docker containers, SSH remotes, and archives.

URI Format:
    local:./relative/path
    local:/absolute/path
    docker:container-name:/path/in/container
    ssh:user@host:/path/on/remote
    ssh:user@host:2222:/path  (with port)
    k8s:pod:/path
    k8s:namespace/pod:/path
    k8s:namespace/pod/container:/path
    archive:./backup.zip
    archive:./backup.zip:/inner/path

Example:
    >>> from pyeff import copy
    >>> from pyeff.uri import local, docker, ssh, k8s, archive
    >>> 
    >>> # URI strings (simple cases)
    >>> copy("local:./src", "docker:my-container:/app")
    >>> copy("k8s:prod/my-pod:/app/logs", "local:./logs")
    >>> 
    >>> # Path builders (complex cases with options)
    >>> copy(ssh("user@host", "/data", key="~/.ssh/id_rsa"), local("./backup"))
    >>> copy(k8s("my-pod", "/data", namespace="prod"), local("./backup"))
    >>> 
    >>> # Mixed usage
    >>> copy("local:./config", docker("my-container", "/app/config"))
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

Mode = Literal["all", "ignore", "include"]
PathLike = Union[str, Path]


class URIPath(ABC):
    """Abstract base class for URI-based paths."""
    
    @property
    @abstractmethod
    def scheme(self) -> str:
        """Return the URI scheme (local, docker, ssh, archive)."""
        pass
    
    @abstractmethod
    def to_uri(self) -> str:
        """Convert to URI string representation."""
        pass
    
    @abstractmethod
    def __str__(self) -> str:
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_uri()!r})"


@dataclass
class LocalPath(URIPath):
    """Local filesystem path.
    
    URI Format: local:./path or local:/path
    
    Example:
        >>> p = LocalPath("./data")
        >>> p.to_uri()
        'local:./data'
    """
    
    path: str
    
    @property
    def scheme(self) -> str:
        return "local"
    
    def to_uri(self) -> str:
        return f"local:{self.path}"
    
    def __str__(self) -> str:
        return self.path
    
    def resolve(self) -> Path:
        """Resolve to absolute Path object."""
        return Path(self.path).resolve()


@dataclass
class DockerPath(URIPath):
    """Docker container path.
    
    URI Format: docker:container-name:/path
    
    Example:
        >>> p = DockerPath("my-container", "/app/data")
        >>> p.to_uri()
        'docker:my-container:/app/data'
    """
    
    container: str
    path: str
    
    @property
    def scheme(self) -> str:
        return "docker"
    
    def to_uri(self) -> str:
        return f"docker:{self.container}:{self.path}"
    
    def __str__(self) -> str:
        return f"{self.container}:{self.path}"


@dataclass
class SSHPath(URIPath):
    """SSH/SFTP remote path.
    
    URI Format: ssh:user@host:/path or ssh:user@host:port:/path
    
    Example:
        >>> p = SSHPath("user@server.com", "/var/log")
        >>> p.to_uri()
        'ssh:user@server.com:/var/log'
        
        >>> p = SSHPath("user@server.com", "/data", port=2222)
        >>> p.to_uri()
        'ssh:user@server.com:2222:/data'
    """
    
    host: str
    path: str
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    key: Optional[str] = None
    key_password: Optional[str] = None
    
    @property
    def scheme(self) -> str:
        return "ssh"
    
    def to_uri(self) -> str:
        if self.port:
            return f"ssh:{self.host}:{self.port}:{self.path}"
        return f"ssh:{self.host}:{self.path}"
    
    def __str__(self) -> str:
        return f"{self.host}:{self.path}"
    
    def get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters for SSHRemote."""
        params: Dict[str, Any] = {"host": self.host}
        if self.port:
            params["port"] = self.port
        if self.username:
            params["username"] = self.username
        if self.password:
            params["password"] = self.password
        if self.key:
            params["key_file"] = self.key
        if self.key_password:
            params["key_password"] = self.key_password
        return params


@dataclass
class K8sPath(URIPath):
    """Kubernetes pod path.
    
    URI Format:
        k8s:pod:/path
        k8s:namespace/pod:/path
        k8s:namespace/pod/container:/path
    
    Example:
        >>> p = K8sPath("my-pod", "/app/data")
        >>> p.to_uri()
        'k8s:my-pod:/app/data'
        
        >>> p = K8sPath("my-pod", "/app/data", namespace="prod", container="app")
        >>> p.to_uri()
        'k8s:prod/my-pod/app:/app/data'
    """
    
    pod: str
    path: str
    namespace: Optional[str] = None
    container: Optional[str] = None
    context: Optional[str] = None
    
    @property
    def scheme(self) -> str:
        return "k8s"
    
    def _pod_spec(self) -> str:
        """Build pod spec string for URI."""
        if self.namespace and self.container:
            return f"{self.namespace}/{self.pod}/{self.container}"
        elif self.namespace and self.namespace != "default":
            return f"{self.namespace}/{self.pod}"
        elif self.container:
            return f"{self.namespace or 'default'}/{self.pod}/{self.container}"
        return self.pod
    
    def to_uri(self) -> str:
        return f"k8s:{self._pod_spec()}:{self.path}"
    
    def __str__(self) -> str:
        return f"{self._pod_spec()}:{self.path}"
    
    def get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters for K8sRemote."""
        params: Dict[str, Any] = {"pod": self.pod}
        if self.namespace:
            params["namespace"] = self.namespace
        if self.container:
            params["container"] = self.container
        if self.context:
            params["context"] = self.context
        return params


@dataclass
class ArchivePath(URIPath):
    """Archive file path.
    
    URI Format: archive:./path.zip or archive:./path.zip:/inner/path
    
    Example:
        >>> p = ArchivePath("./backup.zip")
        >>> p.to_uri()
        'archive:./backup.zip'
        
        >>> p = ArchivePath("./backup.zip", inner_path="/config.json")
        >>> p.to_uri()
        'archive:./backup.zip:/config.json'
    """
    
    archive_path: str
    inner_path: Optional[str] = None
    
    @property
    def scheme(self) -> str:
        return "archive"
    
    def to_uri(self) -> str:
        if self.inner_path:
            return f"archive:{self.archive_path}:{self.inner_path}"
        return f"archive:{self.archive_path}"
    
    def __str__(self) -> str:
        if self.inner_path:
            return f"{self.archive_path}:{self.inner_path}"
        return self.archive_path
    
    def resolve(self) -> Path:
        """Resolve archive path to absolute Path object."""
        return Path(self.archive_path).resolve()


# Path builder functions

def local(path: PathLike) -> LocalPath:
    """Create a local filesystem path.
    
    Args:
        path: Local file or directory path.
        
    Returns:
        LocalPath object.
        
    Example:
        >>> from pyeff.uri import local
        >>> local("./data")
        LocalPath('local:./data')
    """
    return LocalPath(str(path))


def docker(container: str, path: str) -> DockerPath:
    """Create a Docker container path.
    
    Args:
        container: Container name or ID.
        path: Path inside the container.
        
    Returns:
        DockerPath object.
        
    Example:
        >>> from pyeff.uri import docker
        >>> docker("my-container", "/app/data")
        DockerPath('docker:my-container:/app/data')
    """
    return DockerPath(container, path)


def ssh(
    host: str,
    path: str,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    key: Optional[str] = None,
    key_password: Optional[str] = None,
) -> SSHPath:
    """Create an SSH/SFTP remote path.
    
    Args:
        host: Hostname or user@host format.
        path: Path on the remote server.
        port: SSH port (default: 22).
        username: SSH username (overrides host string).
        password: SSH password.
        key: Path to private key file.
        key_password: Password for private key.
        
    Returns:
        SSHPath object.
        
    Example:
        >>> from pyeff.uri import ssh
        >>> ssh("user@server.com", "/var/log")
        SSHPath('ssh:user@server.com:/var/log')
        
        >>> ssh("server.com", "/data", username="admin", key="~/.ssh/id_rsa")
        SSHPath('ssh:server.com:/data')
    """
    return SSHPath(
        host=host,
        path=path,
        port=port,
        username=username,
        password=password,
        key=key,
        key_password=key_password,
    )


def k8s(
    pod: str,
    path: str,
    namespace: Optional[str] = None,
    container: Optional[str] = None,
    context: Optional[str] = None,
) -> K8sPath:
    """Create a Kubernetes pod path.
    
    Args:
        pod: Pod name (or "namespace/pod" / "namespace/pod/container").
        path: Path inside the pod.
        namespace: Kubernetes namespace (default: "default").
        container: Container name within the pod.
        context: kubectl context.
        
    Returns:
        K8sPath object.
        
    Example:
        >>> from pyeff.uri import k8s
        >>> k8s("my-pod", "/app/data")
        K8sPath('k8s:my-pod:/app/data')
        
        >>> k8s("my-pod", "/app/data", namespace="prod", container="app")
        K8sPath('k8s:prod/my-pod/app:/app/data')
    """
    # Allow compact pod specs: "ns/pod" or "ns/pod/ctr"
    if "/" in pod and namespace is None and container is None:
        parts = pod.split("/")
        if len(parts) == 2:
            namespace, pod = parts[0], parts[1]
        elif len(parts) == 3:
            namespace, pod, container = parts[0], parts[1], parts[2]
    
    return K8sPath(
        pod=pod,
        path=path,
        namespace=namespace,
        container=container,
        context=context,
    )


def archive(
    archive_path: PathLike,
    inner_path: Optional[str] = None,
) -> ArchivePath:
    """Create an archive file path.
    
    Args:
        archive_path: Path to the archive file (.zip, .tar.gz, etc.).
        inner_path: Path inside the archive (optional).
        
    Returns:
        ArchivePath object.
        
    Example:
        >>> from pyeff.uri import archive
        >>> archive("./backup.zip")
        ArchivePath('archive:./backup.zip')
        
        >>> archive("./backup.zip", "/config.json")
        ArchivePath('archive:./backup.zip:/config.json')
    """
    return ArchivePath(str(archive_path), inner_path)


# URI parsing

_URI_PATTERN = re.compile(r'^([a-z0-9]+):(.+)$')
_DOCKER_PATH_PATTERN = re.compile(r'^([^:]+):(.+)$')
_SSH_PATH_PATTERN = re.compile(r'^([^:]+?)(?::(\d+))?:(.+)$')
# k8s: pod:/path | ns/pod:/path | ns/pod/ctr:/path
_K8S_PATH_PATTERN = re.compile(r'^((?:[^:/]+/)?[^:/]+(?:/[^:/]+)?):(.+)$')
_ARCHIVE_INNER_PATTERN = re.compile(r'^(.+?\.(?:zip|tar|tar\.gz|tar\.bz2|tar\.xz|tgz|tbz2|txz)):(.+)$', re.I)


def parse_uri(uri: str) -> URIPath:
    """Parse a URI string into a URIPath object.
    
    Args:
        uri: URI string (e.g., "local:./path", "docker:container:/path").
        
    Returns:
        Appropriate URIPath subclass instance.
        
    Raises:
        ValueError: If URI format is invalid.
        
    Example:
        >>> parse_uri("local:./data")
        LocalPath('local:./data')
        
        >>> parse_uri("docker:my-container:/app")
        DockerPath('docker:my-container:/app')
    """
    match = _URI_PATTERN.match(uri)
    if not match:
        raise ValueError(
            f"Invalid URI format: {uri!r}. "
            f"Expected format: scheme:path (e.g., 'local:./path', 'docker:container:/path')"
        )
    
    scheme, rest = match.groups()
    
    if scheme == "local":
        return LocalPath(rest)
    
    elif scheme == "docker":
        docker_match = _DOCKER_PATH_PATTERN.match(rest)
        if not docker_match:
            raise ValueError(
                f"Invalid docker URI: {uri!r}. "
                f"Expected format: docker:container:/path"
            )
        container, path = docker_match.groups()
        return DockerPath(container, path)
    
    elif scheme == "ssh":
        ssh_match = _SSH_PATH_PATTERN.match(rest)
        if not ssh_match:
            raise ValueError(
                f"Invalid ssh URI: {uri!r}. "
                f"Expected format: ssh:user@host:/path or ssh:user@host:port:/path"
            )
        host, port_str, path = ssh_match.groups()
        port = int(port_str) if port_str else None
        return SSHPath(host, path, port=port)
    
    elif scheme == "k8s":
        k8s_match = _K8S_PATH_PATTERN.match(rest)
        if not k8s_match:
            raise ValueError(
                f"Invalid k8s URI: {uri!r}. "
                f"Expected format: k8s:pod:/path, k8s:ns/pod:/path, "
                f"or k8s:ns/pod/container:/path"
            )
        pod_spec, path = k8s_match.groups()
        parts = pod_spec.split("/")
        if len(parts) == 1:
            return K8sPath(pod=parts[0], path=path)
        elif len(parts) == 2:
            return K8sPath(pod=parts[1], path=path, namespace=parts[0])
        elif len(parts) == 3:
            return K8sPath(
                pod=parts[1], path=path,
                namespace=parts[0], container=parts[2],
            )
        else:
            raise ValueError(
                f"Invalid k8s URI: {uri!r}. "
                f"Expected format: k8s:pod:/path, k8s:ns/pod:/path, "
                f"or k8s:ns/pod/container:/path"
            )
    
    elif scheme == "archive":
        inner_match = _ARCHIVE_INNER_PATTERN.match(rest)
        if inner_match:
            archive_path, inner_path = inner_match.groups()
            return ArchivePath(archive_path, inner_path)
        return ArchivePath(rest)
    
    else:
        raise ValueError(f"Unknown URI scheme: {scheme!r}")


def resolve_path(path: Union[str, URIPath]) -> URIPath:
    """Resolve a path (string or URIPath) to a URIPath object.
    
    Args:
        path: URI string or URIPath object.
        
    Returns:
        URIPath object.
        
    Example:
        >>> resolve_path("local:./data")
        LocalPath('local:./data')
        
        >>> resolve_path(LocalPath("./data"))
        LocalPath('local:./data')
    """
    if isinstance(path, URIPath):
        return path
    return parse_uri(path)


__all__ = [
    "URIPath",
    "LocalPath",
    "DockerPath",
    "SSHPath",
    "K8sPath",
    "ArchivePath",
    "local",
    "docker",
    "ssh",
    "k8s",
    "archive",
    "parse_uri",
    "resolve_path",
]
