"""Remote file operations module.

This module provides unified API for remote file operations:
- Docker containers
- SSH/SFTP remote hosts
- Kubernetes pods (future)

All operations use the same mode/patterns API as local fs operations.
"""

from __future__ import annotations

from .base import RemoteError, RemoteConnectionError, RemoteFileNotFoundError
from .docker import DockerRemote, docker_copy, docker_remove, docker_search, docker_exists

__all__ = [
    "RemoteError",
    "RemoteConnectionError",
    "RemoteFileNotFoundError",
    "DockerRemote",
    "docker_copy",
    "docker_remove",
    "docker_search",
    "docker_exists",
]

try:
    from .ssh import SSHRemote, ssh_connect
    __all__.extend(["SSHRemote", "ssh_connect"])
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
