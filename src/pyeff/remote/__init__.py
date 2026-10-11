"""Remote file operations module.

This module provides unified API for remote file operations:
- Docker containers via docker() factory
- SSH/SFTP remote hosts via ssh() factory
- Kubernetes pods via k8s() factory

All operations use the same mode/patterns API as local fs operations.

Example:
    >>> from pyeff.remote import docker, ssh, k8s
    >>> 
    >>> # Docker
    >>> with docker("my-container") as d:
    ...     d.copy("/app/logs", "./logs")
    >>> 
    >>> # SSH
    >>> with ssh("user@host") as s:
    ...     s.copy("/var/log", "./logs")
    >>> 
    >>> # Kubernetes
    >>> with k8s("my-pod", namespace="prod") as k:
    ...     k.copy("/app/logs", "./logs")
    ...     k.copy("./config", "/app/config")
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

__all__ = [
    # Base classes and exceptions
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
]

try:
    from .ssh import SSHRemote, ssh_connect, ssh
    __all__.extend(["SSHRemote", "ssh_connect", "ssh"])
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
