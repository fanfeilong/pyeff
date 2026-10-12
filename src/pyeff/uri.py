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
class S3Path(URIPath):
    """S3 / MinIO object path.
    
    URI Format: s3://bucket/key or s3:bucket:/key
    
    Example:
        >>> p = S3Path("my-bucket", "logs/app.log")
        >>> p.to_uri()
        's3://my-bucket/logs/app.log'
    """
    
    bucket: str
    path: str
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    region: Optional[str] = None
    session_token: Optional[str] = None
    
    @property
    def scheme(self) -> str:
        return "s3"
    
    def to_uri(self) -> str:
        key = self.path.lstrip("/")
        return f"s3://{self.bucket}/{key}" if key else f"s3://{self.bucket}/"
    
    def __str__(self) -> str:
        return self.to_uri()
    
    def get_connection_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {"bucket": self.bucket}
        if self.endpoint_url:
            params["endpoint_url"] = self.endpoint_url
        if self.access_key:
            params["access_key"] = self.access_key
        if self.secret_key:
            params["secret_key"] = self.secret_key
        if self.region:
            params["region"] = self.region
        if self.session_token:
            params["session_token"] = self.session_token
        return params


@dataclass
class GCSPath(URIPath):
    """Google Cloud Storage path.
    
    URI Format: gs://bucket/path or gcs:bucket:/path
    """
    
    bucket: str
    path: str
    project: Optional[str] = None
    credentials_path: Optional[str] = None
    
    @property
    def scheme(self) -> str:
        return "gs"
    
    def to_uri(self) -> str:
        key = self.path.lstrip("/")
        return f"gs://{self.bucket}/{key}" if key else f"gs://{self.bucket}/"
    
    def __str__(self) -> str:
        return self.to_uri()
    
    def get_connection_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {"bucket": self.bucket}
        if self.project:
            params["project"] = self.project
        if self.credentials_path:
            params["credentials_path"] = self.credentials_path
        return params


@dataclass
class AzurePath(URIPath):
    """Azure Blob Storage path.
    
    URI Format: az://container/blob or azure:container:/blob
    """
    
    container: str
    path: str
    connection_string: Optional[str] = None
    account_url: Optional[str] = None
    credential: Optional[str] = None
    
    @property
    def scheme(self) -> str:
        return "az"
    
    def to_uri(self) -> str:
        key = self.path.lstrip("/")
        return f"az://{self.container}/{key}" if key else f"az://{self.container}/"
    
    def __str__(self) -> str:
        return self.to_uri()
    
    def get_connection_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {"container": self.container}
        if self.connection_string:
            params["connection_string"] = self.connection_string
        if self.account_url:
            params["account_url"] = self.account_url
        if self.credential:
            params["credential"] = self.credential
        return params


@dataclass
class HTTPPath(URIPath):
    """HTTP(S) URL path.
    
    URI Format: http://host/path or https://host/path
    """
    
    url: str
    timeout: Optional[float] = None
    headers: Optional[Dict[str, str]] = None
    
    @property
    def scheme(self) -> str:
        return "https" if self.url.startswith("https") else "http"
    
    @property
    def path(self) -> str:
        """Path component for remote ops (full URL works with HTTPRemote)."""
        return self.url
    
    def to_uri(self) -> str:
        return self.url
    
    def __str__(self) -> str:
        return self.url
    
    def get_connection_params(self) -> Dict[str, Any]:
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        params: Dict[str, Any] = {"base_url": base}
        if self.timeout is not None:
            params["timeout"] = self.timeout
        if self.headers:
            params["headers"] = self.headers
        return params
    
    def get_url_path(self) -> str:
        """Return path(+query) relative to base URL."""
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return path


@dataclass
class SMBPath(URIPath):
    """SMB/CIFS NAS path.
    
    URI Format: smb://host/share/path
    """
    
    host: str
    share: str
    path: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    port: int = 445
    domain: Optional[str] = None
    
    @property
    def scheme(self) -> str:
        return "smb"
    
    def to_uri(self) -> str:
        key = self.path.lstrip("/")
        base = f"smb://{self.host}/{self.share}"
        return f"{base}/{key}" if key else f"{base}/"
    
    def __str__(self) -> str:
        return self.to_uri()
    
    def get_connection_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "host": self.host,
            "share": self.share,
            "port": self.port,
        }
        if self.username:
            params["username"] = self.username
        if self.password:
            params["password"] = self.password
        if self.domain:
            params["domain"] = self.domain
        return params


@dataclass
class WebDAVPath(URIPath):
    """WebDAV NAS path.
    
    URI Format:
        webdav://host/path
        webdavs://host/path  (HTTPS)
        dav:// / davs://
    """
    
    base_url: str
    path: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: Optional[float] = None
    verify_ssl: bool = True
    
    @property
    def scheme(self) -> str:
        if self.base_url.startswith("https"):
            return "webdavs"
        return "webdav"
    
    def to_uri(self) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        # Prefer webdavs:// for https
        scheme = "webdavs" if parsed.scheme == "https" else "webdav"
        key = self.path.lstrip("/")
        root = f"{scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        return f"{root}/{key}" if key else f"{root}/"
    
    def __str__(self) -> str:
        return self.to_uri()
    
    def get_connection_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "base_url": self.base_url,
            "verify_ssl": self.verify_ssl,
        }
        if self.username:
            params["username"] = self.username
        if self.password:
            params["password"] = self.password
        if self.timeout is not None:
            params["timeout"] = self.timeout
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


def s3_uri(
    bucket: str,
    path: str = "",
    endpoint_url: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
    session_token: Optional[str] = None,
) -> S3Path:
    """Create an S3 / MinIO path.
    
    Example:
        >>> from pyeff.uri import s3_uri
        >>> s3_uri("my-bucket", "logs/app.log")
        >>> s3_uri("bucket", "data/", endpoint_url="http://localhost:9000")
    """
    return S3Path(
        bucket=bucket,
        path=path,
        endpoint_url=endpoint_url,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        session_token=session_token,
    )


# Alias matching other builders
def s3(
    bucket: str,
    path: str = "",
    endpoint_url: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
    session_token: Optional[str] = None,
) -> S3Path:
    """Create an S3 / MinIO path (alias of s3_uri)."""
    return s3_uri(
        bucket, path,
        endpoint_url=endpoint_url,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        session_token=session_token,
    )


def gs(
    bucket: str,
    path: str = "",
    project: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> GCSPath:
    """Create a GCS path.
    
    Example:
        >>> from pyeff.uri import gs
        >>> gs("my-bucket", "logs/app.log")
    """
    return GCSPath(
        bucket=bucket,
        path=path,
        project=project,
        credentials_path=credentials_path,
    )


def az(
    container: str,
    path: str = "",
    connection_string: Optional[str] = None,
    account_url: Optional[str] = None,
    credential: Optional[str] = None,
) -> AzurePath:
    """Create an Azure Blob path.
    
    Example:
        >>> from pyeff.uri import az
        >>> az("my-container", "logs/app.log", connection_string="...")
    """
    return AzurePath(
        container=container,
        path=path,
        connection_string=connection_string,
        account_url=account_url,
        credential=credential,
    )


def http_url(
    url: str,
    timeout: Optional[float] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HTTPPath:
    """Create an HTTP(S) path.
    
    Example:
        >>> from pyeff.uri import http_url
        >>> http_url("https://example.com/file.zip")
    """
    return HTTPPath(url=url, timeout=timeout, headers=headers)


def smb_uri(
    host: str,
    share: str,
    path: str = "",
    username: Optional[str] = None,
    password: Optional[str] = None,
    port: int = 445,
    domain: Optional[str] = None,
) -> SMBPath:
    """Create an SMB/CIFS path.
    
    Example:
        >>> from pyeff.uri import smb_uri
        >>> smb_uri("nas.local", "shared", "docs/", username="user", password="pass")
    """
    return SMBPath(
        host=host,
        share=share,
        path=path,
        username=username,
        password=password,
        port=port,
        domain=domain,
    )


def webdav_uri(
    base_url: str,
    path: str = "",
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: Optional[float] = None,
    verify_ssl: bool = True,
) -> WebDAVPath:
    """Create a WebDAV path.
    
    Example:
        >>> from pyeff.uri import webdav_uri
        >>> webdav_uri("https://nas.local/webdav", "docs/",
        ...            username="user", password="pass")
    """
    # Normalize webdav(s):// to http(s):// for base_url storage
    url = base_url
    if url.startswith("webdavs://"):
        url = "https://" + url[len("webdavs://"):]
    elif url.startswith("webdav://"):
        url = "http://" + url[len("webdav://"):]
    elif url.startswith("davs://"):
        url = "https://" + url[len("davs://"):]
    elif url.startswith("dav://"):
        url = "http://" + url[len("dav://"):]
    
    return WebDAVPath(
        base_url=url,
        path=path,
        username=username,
        password=password,
        timeout=timeout,
        verify_ssl=verify_ssl,
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


def _parse_bucket_key(rest: str) -> Tuple[str, str]:
    """Parse //bucket/key or bucket:/key into (bucket, key)."""
    if rest.startswith("//"):
        rest = rest[2:]
        if "/" in rest:
            bucket, key = rest.split("/", 1)
        else:
            bucket, key = rest, ""
        return bucket, key
    
    # bucket:/key or bucket:key
    if ":" in rest:
        bucket, key = rest.split(":", 1)
        return bucket, key.lstrip("/")
    
    raise ValueError(f"Invalid bucket path: {rest!r}")


# URI parsing

_URI_PATTERN = re.compile(r'^([a-z0-9]+):(.+)$')
_DOCKER_PATH_PATTERN = re.compile(r'^([^:]+):(.+)$')
_SSH_PATH_PATTERN = re.compile(r'^([^:]+?)(?::(\d+))?:(.+)$')
# k8s: pod:/path | ns/pod:/path | ns/pod/ctr:/path
_K8S_PATH_PATTERN = re.compile(r'^((?:[^:/]+/)?[^:/]+(?:/[^:/]+)?):(.+)$')
_ARCHIVE_INNER_PATTERN = re.compile(r'^(.+?\.(?:zip|tar|tar\.gz|tar\.bz2|tar\.xz|tgz|tbz2|txz)):(.+)$', re.I)

# Known schemes — anything else (e.g. Windows "c:/...") is treated as a local path.
KNOWN_SCHEMES = frozenset({
    "local", "docker", "ssh", "k8s", "archive",
    "s3", "gs", "gcs", "az", "azure",
    "http", "https",
    "smb",
    "webdav", "webdavs", "dav", "davs",
})


def looks_like_uri(path: Union[str, Path, "URIPath"]) -> bool:
    """Return True if *path* uses a known URI scheme."""
    if isinstance(path, URIPath):
        return True
    if isinstance(path, Path):
        return False
    match = _URI_PATTERN.match(str(path))
    return bool(match and match.group(1) in KNOWN_SCHEMES)


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
    
    elif scheme == "s3":
        try:
            bucket, key = _parse_bucket_key(rest)
        except ValueError as e:
            raise ValueError(
                f"Invalid s3 URI: {uri!r}. "
                f"Expected s3://bucket/key or s3:bucket:/key"
            ) from e
        return S3Path(bucket=bucket, path=key)
    
    elif scheme in ("gs", "gcs"):
        try:
            bucket, key = _parse_bucket_key(rest)
        except ValueError as e:
            raise ValueError(
                f"Invalid gs/gcs URI: {uri!r}. "
                f"Expected gs://bucket/key or gcs:bucket:/key"
            ) from e
        return GCSPath(bucket=bucket, path=key)
    
    elif scheme in ("az", "azure"):
        try:
            container, key = _parse_bucket_key(rest)
        except ValueError as e:
            raise ValueError(
                f"Invalid az/azure URI: {uri!r}. "
                f"Expected az://container/blob or azure:container:/blob"
            ) from e
        return AzurePath(container=container, path=key)
    
    elif scheme in ("http", "https"):
        if not rest.startswith("//"):
            raise ValueError(
                f"Invalid http URI: {uri!r}. "
                f"Expected http://host/path or https://host/path"
            )
        return HTTPPath(url=f"{scheme}:{rest}")
    
    elif scheme == "smb":
        if not rest.startswith("//"):
            # smb:host/share:/path
            if ":/" in rest or rest.count(":") == 1:
                try:
                    host_share, key = rest.split(":", 1)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid smb URI: {uri!r}. "
                        f"Expected smb://host/share/path"
                    ) from e
                parts = host_share.strip("/").split("/")
                if len(parts) < 2:
                    raise ValueError(
                        f"Invalid smb URI: {uri!r}. "
                        f"Expected smb://host/share/path"
                    )
                return SMBPath(
                    host=parts[0],
                    share=parts[1],
                    path=key.lstrip("/"),
                )
            raise ValueError(
                f"Invalid smb URI: {uri!r}. "
                f"Expected smb://host/share/path"
            )
        # smb://host/share/path
        body = rest[2:]
        parts = body.split("/")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid smb URI: {uri!r}. "
                f"Expected smb://host/share/path"
            )
        host, share = parts[0], parts[1]
        key = "/".join(parts[2:])
        return SMBPath(host=host, share=share, path=key)
    
    elif scheme in ("webdav", "webdavs", "dav", "davs"):
        if not rest.startswith("//"):
            raise ValueError(
                f"Invalid webdav URI: {uri!r}. "
                f"Expected webdav(s)://host/path"
            )
        https = scheme in ("webdavs", "davs")
        http_scheme = "https" if https else "http"
        body = rest[2:]
        if "/" in body:
            netloc, path = body.split("/", 1)
        else:
            netloc, path = body, ""
        base_url = f"{http_scheme}://{netloc}"
        # If path looks like a dav root with nested path, keep full base
        # webdavs://host/remote.php/dav/files/user/Documents/file
        # → base_url includes dav root; path is relative.
        # Heuristic: treat entire URL path as relative to host root.
        return WebDAVPath(base_url=base_url, path=path)
    
    else:
        raise ValueError(f"Unknown URI scheme: {scheme!r}")


def resolve_path_local(path: Union[str, Path, URIPath]) -> URIPath:
    """Resolve without profile ``@name`` handling (internal / profile module)."""
    if isinstance(path, URIPath):
        return path
    if isinstance(path, Path):
        return LocalPath(str(path))
    s = str(path)
    if looks_like_uri(s):
        return parse_uri(s)
    return LocalPath(s)


def resolve_path(path: Union[str, Path, URIPath]) -> URIPath:
    """Resolve a path (string, Path, or URIPath) to a URIPath object.
    
    Bare local paths (without a known scheme) become ``LocalPath``.
    Windows drive letters (``c:/...``) are treated as local paths.
    Named profile refs (``@staging_k8s:pod:/path``) use the active Profile
    from ``pyeff.profile`` when set.
    
    Args:
        path: URI string, bare local path, ``Path``, or URIPath object.
        
    Returns:
        URIPath object.
        
    Example:
        >>> resolve_path("local:./data")
        LocalPath('local:./data')
        
        >>> resolve_path("./data")
        LocalPath('local:./data')
        
        >>> resolve_path(LocalPath("./data"))
        LocalPath('local:./data')
    """
    if isinstance(path, URIPath):
        return path
    if isinstance(path, Path):
        return LocalPath(str(path))
    s = str(path)
    if s.startswith("@"):
        from .profile import resolve_path as profile_resolve
        return profile_resolve(s)
    return resolve_path_local(s)


def join_uri(base: Union[str, Path, URIPath], relative: str) -> str:
    """Join a base URI/path with a relative path segment.
    
    Example:
        >>> join_uri("docker:ctr:/app/cfg", "data.yml")
        'docker:ctr:/app/cfg/data.yml'
        >>> join_uri("local:./cfg", "a.yml")
        'local:./cfg/a.yml'
    """
    base_path = resolve_path(base)
    rel = relative.lstrip("/")
    
    if isinstance(base_path, LocalPath):
        base = base_path.path.rstrip("/") or "."
        return f"local:{base}/{rel}"
    
    if isinstance(base_path, ArchivePath):
        if base_path.inner_path:
            inner = str(Path(base_path.inner_path.lstrip("/")) / rel)
        else:
            inner = rel
        return f"archive:{base_path.archive_path}:/{inner}"
    
    uri = base_path.to_uri()
    if uri.endswith("/"):
        return f"{uri}{rel}"
    return f"{uri.rstrip('/')}/{rel}"


__all__ = [
    "URIPath",
    "LocalPath",
    "DockerPath",
    "SSHPath",
    "K8sPath",
    "S3Path",
    "GCSPath",
    "AzurePath",
    "HTTPPath",
    "SMBPath",
    "WebDAVPath",
    "ArchivePath",
    "local",
    "docker",
    "ssh",
    "k8s",
    "s3",
    "s3_uri",
    "gs",
    "az",
    "http_url",
    "smb_uri",
    "webdav_uri",
    "archive",
    "KNOWN_SCHEMES",
    "looks_like_uri",
    "parse_uri",
    "resolve_path",
    "join_uri",
]
