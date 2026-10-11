"""Remote file operations module.

Backends:
- Docker containers via docker()
- SSH/SFTP via ssh()
- Kubernetes pods via k8s()
- S3 / MinIO via s3()
- GCS via gcs()
- Azure Blob via azure()
- HTTP(S) via http()

Example:
    >>> from pyeff.remote import docker, ssh, k8s, s3, http
    >>> from pyeff import copy
    >>> 
    >>> copy("s3://my-bucket/logs/", "local:./logs")
    >>> copy("https://example.com/file.zip", "local:./file.zip")
    >>> copy("local:./data", "s3://bucket/uploads/")
"""

from __future__ import annotations

from .base import (
    RemoteError,
    RemoteConnectionError,
    RemoteFileNotFoundError,
    RemotePermissionError,
    RemoteBackend,
    RemoteFileInfo,
)
from .docker import (
    DockerRemote,
    docker,
    docker_copy,
    docker_remove,
    docker_search,
    docker_exists,
    docker_read,
    docker_write,
)
from .k8s import (
    K8sRemote,
    k8s,
    k8s_copy,
)
from .http import (
    HTTPRemote,
    http,
    http_download,
)
from .webdav import (
    WebDAVRemote,
    webdav,
)
from .smb import (
    SMBRemote,
    smb,
    SMB_AVAILABLE,
)

__all__ = [
    # Base
    "RemoteError",
    "RemoteConnectionError",
    "RemoteFileNotFoundError",
    "RemotePermissionError",
    "RemoteBackend",
    "RemoteFileInfo",
    # Docker
    "DockerRemote",
    "docker",
    "docker_copy",
    "docker_remove",
    "docker_search",
    "docker_exists",
    "docker_read",
    "docker_write",
    # Kubernetes
    "K8sRemote",
    "k8s",
    "k8s_copy",
    # HTTP
    "HTTPRemote",
    "http",
    "http_download",
    # WebDAV (NAS)
    "WebDAVRemote",
    "webdav",
    # SMB/CIFS (NAS)
    "SMBRemote",
    "smb",
    "SMB_AVAILABLE",
]

try:
    from .ssh import SSHRemote, ssh_connect, ssh
    __all__.extend(["SSHRemote", "ssh_connect", "ssh"])
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False

from .s3 import S3Remote, s3, BOTO3_AVAILABLE as S3_AVAILABLE
__all__.extend(["S3Remote", "s3"])

from .gcs import GCSRemote, gcs, GCS_AVAILABLE
__all__.extend(["GCSRemote", "gcs"])

from .azure import AzureRemote, azure, AZURE_AVAILABLE
__all__.extend(["AzureRemote", "azure"])
