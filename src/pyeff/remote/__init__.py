"""Remote file operations module.

This module provides unified API for remote file operations:
- Docker containers via docker() factory
- SSH/SFTP remote hosts via ssh() factory
- Kubernetes pods (future)

All operations use the same mode/patterns API as local fs operations.

Example:
    >>> from pyeff.remote import docker, ssh
    >>> 
    >>> # Docker: copy() auto-detects direction
    >>> with docker("my-container") as d:
    ...     d.copy("/app/logs", "./logs")      # container → local
    ...     d.copy("./config", "/app/config")  # local → container
    >>> 
    >>> # SSH: same unified API
    >>> with ssh("user@host") as s:
    ...     s.copy("/var/log", "./logs")       # remote → local
    ...     s.copy("./data", "/remote/data")   # local → remote
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
]

try:
    from .ssh import SSHRemote, ssh_connect, ssh
    __all__.extend(["SSHRemote", "ssh_connect", "ssh"])
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
