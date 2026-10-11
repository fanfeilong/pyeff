"""SSH/SFTP remote file operations.

This module provides file operations over SSH/SFTP with
the same API as local fs operations.

Requires: paramiko (pip install pyeff[ssh])

Example:
    >>> from pyeff.remote.ssh import SSHRemote, ssh_connect
    >>> 
    >>> # Using context manager
    >>> with SSHRemote("user@host") as ssh:
    ...     ssh.copy_from("/remote/logs", "./logs")
    ...     files = ssh.search("/data", patterns=["*.csv"])
    >>> 
    >>> # Or using ssh_connect
    >>> with ssh_connect("user@host", key_file="~/.ssh/id_rsa") as ssh:
    ...     content = ssh.read_text("/etc/config")
"""

from __future__ import annotations

import fnmatch
import os
import stat
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple, Union

try:
    import paramiko
    from paramiko import SFTPClient, SSHClient
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None
    SFTPClient = None
    SSHClient = None

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
    RemotePermissionError,
)


def _check_paramiko() -> None:
    """Check if paramiko is available."""
    if not PARAMIKO_AVAILABLE:
        raise ImportError(
            "SSH support requires 'paramiko' package. "
            "Install with: pip install pyeff[ssh] or pip install paramiko"
        )


def _parse_host(host: str) -> Tuple[str, Optional[str], int]:
    """Parse user@host:port format.
    
    Returns:
        Tuple of (hostname, username, port).
    """
    username = None
    port = 22
    
    if "@" in host:
        username, host = host.rsplit("@", 1)
    
    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        port = int(port_str)
    
    return host, username, port


class SSHRemote(RemoteBackend):
    """SSH/SFTP remote file operations.
    
    Provides file operations over SSH/SFTP with the same API
    as local fs operations.
    
    Args:
        host: Hostname or user@host:port format.
        username: SSH username (overrides host string).
        port: SSH port (overrides host string).
        password: SSH password.
        key_file: Path to private key file.
        key_password: Password for private key.
        
    Example:
        >>> with SSHRemote("user@server.com") as ssh:
        ...     ssh.copy_from("/var/log", "./logs", patterns=["*.log"])
        ...     ssh.remove("/tmp/cache", recursive=True)
    """
    
    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        key_file: Optional[PathLike] = None,
        key_password: Optional[str] = None,
    ):
        _check_paramiko()
        
        parsed_host, parsed_user, parsed_port = _parse_host(host)
        
        self.hostname = parsed_host
        self.username = username or parsed_user
        self.port = port or parsed_port
        self.password = password
        self.key_file = Path(key_file).expanduser() if key_file else None
        self.key_password = key_password
        
        self._client: Optional[SSHClient] = None
        self._sftp: Optional[SFTPClient] = None
    
    def __enter__(self) -> "SSHRemote":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def connect(self) -> None:
        """Establish SSH connection."""
        if self._client is not None:
            return
        
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs = {
            "hostname": self.hostname,
            "port": self.port,
            "username": self.username,
        }
        
        if self.password:
            connect_kwargs["password"] = self.password
        
        if self.key_file:
            connect_kwargs["key_filename"] = str(self.key_file)
            if self.key_password:
                connect_kwargs["passphrase"] = self.key_password
        
        try:
            self._client.connect(**connect_kwargs)
            self._sftp = self._client.open_sftp()
        except paramiko.AuthenticationException as e:
            raise RemoteConnectionError(f"Authentication failed: {e}")
        except paramiko.SSHException as e:
            raise RemoteConnectionError(f"SSH connection failed: {e}")
        except Exception as e:
            raise RemoteConnectionError(f"Connection failed: {e}")
    
    def close(self) -> None:
        """Close SSH connection."""
        if self._sftp:
            self._sftp.close()
            self._sftp = None
        if self._client:
            self._client.close()
            self._client = None
    
    @property
    def sftp(self) -> SFTPClient:
        """Get SFTP client, connecting if necessary."""
        if self._sftp is None:
            self.connect()
        return self._sftp
    
    def _exec(self, cmd: str) -> Tuple[str, str, int]:
        """Execute command on remote."""
        if self._client is None:
            self.connect()
        
        stdin, stdout, stderr = self._client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        return stdout.read().decode(), stderr.read().decode(), exit_code
    
    def exists(self, remote_path: str) -> bool:
        """Check if path exists on remote."""
        try:
            self.sftp.stat(remote_path)
            return True
        except IOError:
            return False
    
    def is_file(self, remote_path: str) -> bool:
        """Check if path is a file on remote."""
        try:
            st = self.sftp.stat(remote_path)
            return stat.S_ISREG(st.st_mode)
        except IOError:
            return False
    
    def is_dir(self, remote_path: str) -> bool:
        """Check if path is a directory on remote."""
        try:
            st = self.sftp.stat(remote_path)
            return stat.S_ISDIR(st.st_mode)
        except IOError:
            return False
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        """List files in remote directory."""
        if not self.is_dir(remote_path):
            raise RemoteFileNotFoundError(f"Directory not found: {remote_path}")
        
        filter_obj = PatternFilter(mode, patterns)
        files: List[RemoteFileInfo] = []
        
        for attr in self.sftp.listdir_attr(remote_path):
            if not filter_obj.match(attr.filename):
                continue
            
            is_dir = stat.S_ISDIR(attr.st_mode)
            full_path = f"{remote_path.rstrip('/')}/{attr.filename}"
            
            files.append(RemoteFileInfo(
                name=attr.filename,
                path=full_path,
                size=attr.st_size or 0,
                is_dir=is_dir,
                is_file=not is_dir,
                mode=stat.filemode(attr.st_mode),
            ))
        
        return files
    
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        """Search for files on remote."""
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        filter_obj = PatternFilter(mode, patterns)
        results: List[str] = []
        
        def _walk(path: str) -> None:
            try:
                for attr in self.sftp.listdir_attr(path):
                    full_path = f"{path.rstrip('/')}/{attr.filename}"
                    
                    if stat.S_ISDIR(attr.st_mode):
                        if recursive:
                            _walk(full_path)
                    else:
                        if filter_obj.match(attr.filename):
                            results.append(full_path)
            except IOError:
                pass
        
        if self.is_file(remote_path):
            if filter_obj.match(PurePosixPath(remote_path).name):
                return [remote_path]
            return []
        
        _walk(remote_path)
        return results
    
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files from remote to local."""
        local = Path(local_path)
        
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        if self.is_file(remote_path):
            local.parent.mkdir(parents=True, exist_ok=True)
            if local.is_dir():
                local = local / PurePosixPath(remote_path).name
            self.sftp.get(remote_path, str(local))
            if progress:
                progress(remote_path, 1, 1)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        total = len(files)
        count = 0
        
        for remote_file in files:
            rel_path = PurePosixPath(remote_file).relative_to(remote_path)
            local_file = local / rel_path
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            self.sftp.get(remote_file, str(local_file))
            
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
        """Copy files from local to remote."""
        local = Path(local_path)
        
        if not local.exists():
            raise FileNotFoundError(f"Local path not found: {local_path}")
        
        if local.is_file():
            self._mkdir_p(str(PurePosixPath(remote_path).parent))
            self.sftp.put(str(local), remote_path)
            if progress:
                progress(str(local), 1, 1)
            return 1
        
        filter_obj = PatternFilter(mode, patterns)
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
            self._mkdir_p(str(PurePosixPath(remote_file).parent))
            self.sftp.put(str(local_file), remote_file)
            
            count += 1
            if progress:
                progress(str(local_file), count, total)
        
        return count
    
    def _mkdir_p(self, remote_path: str) -> None:
        """Create remote directory recursively."""
        if not remote_path or remote_path == "/":
            return
        
        try:
            self.sftp.stat(remote_path)
            return
        except IOError:
            pass
        
        parent = str(PurePosixPath(remote_path).parent)
        if parent and parent != remote_path:
            self._mkdir_p(parent)
        
        try:
            self.sftp.mkdir(remote_path)
        except IOError:
            pass
    
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        """Remove files on remote."""
        if not self.exists(remote_path):
            return 0
        
        if self.is_file(remote_path):
            self.sftp.remove(remote_path)
            return 1
        
        if mode == "all" and not patterns:
            if recursive:
                self._rmtree(remote_path)
            else:
                self.sftp.rmdir(remote_path)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        count = 0
        
        for remote_file in files:
            try:
                self.sftp.remove(remote_file)
                count += 1
            except IOError:
                pass
        
        return count
    
    def _rmtree(self, remote_path: str) -> None:
        """Remove directory recursively."""
        for attr in self.sftp.listdir_attr(remote_path):
            full_path = f"{remote_path.rstrip('/')}/{attr.filename}"
            
            if stat.S_ISDIR(attr.st_mode):
                self._rmtree(full_path)
            else:
                self.sftp.remove(full_path)
        
        self.sftp.rmdir(remote_path)
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        """Read text file from remote."""
        if not self.is_file(remote_path):
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        
        with self.sftp.open(remote_path, "r") as f:
            return f.read().decode(encoding)
    
    def read_bytes(self, remote_path: str) -> bytes:
        """Read binary file from remote."""
        if not self.is_file(remote_path):
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        
        with self.sftp.open(remote_path, "rb") as f:
            return f.read()
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """Write text file to remote."""
        self._mkdir_p(str(PurePosixPath(remote_path).parent))
        
        with self.sftp.open(remote_path, "w") as f:
            f.write(content.encode(encoding))
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        """Write binary file to remote."""
        self._mkdir_p(str(PurePosixPath(remote_path).parent))
        
        with self.sftp.open(remote_path, "wb") as f:
            f.write(content)
    
    def copy(
        self,
        src: str,
        dst: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Copy files between remote and local filesystem.
        
        Direction is auto-detected based on path format:
        - Absolute path (starts with /) = remote path
        - Relative path (starts with . or other) = local path
        
        Args:
            src: Source path (remote or local).
            dst: Destination path (remote or local).
            mode: Filter mode ("all", "include", "ignore").
            patterns: Glob patterns for filtering.
            progress: Optional progress callback.
            
        Returns:
            Number of files copied.
            
        Example:
            >>> with ssh("user@host") as s:
            ...     s.copy("/var/log", "./logs")      # remote → local
            ...     s.copy("./config", "/etc/app/")   # local → remote
        """
        src_is_remote = src.startswith("/")
        dst_is_remote = dst.startswith("/")
        
        if src_is_remote and dst_is_remote:
            raise RemoteError(
                "Both paths appear to be remote paths. "
                "Use relative path (./...) for local path."
            )
        
        if not src_is_remote and not dst_is_remote:
            raise RemoteError(
                "Both paths appear to be local paths. "
                "Use absolute path (/...) for remote path."
            )
        
        if src_is_remote:
            return self.copy_from(src, dst, mode, patterns, progress)
        else:
            return self.copy_to(src, dst, mode, patterns, progress)


def ssh_connect(
    host: str,
    username: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    key_file: Optional[PathLike] = None,
    key_password: Optional[str] = None,
) -> SSHRemote:
    """Create SSH connection context manager.
    
    Args:
        host: Hostname or user@host:port format.
        username: SSH username.
        port: SSH port.
        password: SSH password.
        key_file: Path to private key file.
        key_password: Password for private key.
        
    Returns:
        SSHRemote context manager.
        
    Example:
        >>> with ssh_connect("user@server.com", key_file="~/.ssh/id_rsa") as ssh:
        ...     ssh.copy_from("/var/log", "./logs")
    """
    return SSHRemote(
        host=host,
        username=username,
        port=port,
        password=password,
        key_file=key_file,
        key_password=key_password,
    )


def ssh(
    host: str,
    username: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    key_file: Optional[PathLike] = None,
    key_password: Optional[str] = None,
) -> SSHRemote:
    """Create an SSH remote interface.
    
    Factory function for creating SSHRemote instances with
    a cleaner API. Alias for ssh_connect.
    
    Args:
        host: Hostname or user@host:port format.
        username: SSH username.
        port: SSH port.
        password: SSH password.
        key_file: Path to private key file.
        key_password: Password for private key.
        
    Returns:
        SSHRemote instance (use as context manager).
        
    Example:
        >>> from pyeff.remote import ssh
        >>> 
        >>> with ssh("user@server.com") as s:
        ...     # copy() auto-detects direction based on path
        ...     s.copy("/var/log", "./logs")      # remote → local
        ...     s.copy("./config", "/etc/app/")   # local → remote
        ...     
        ...     s.remove("/tmp/cache")
        ...     files = s.search("/data", patterns=["*.csv"])
    """
    return SSHRemote(
        host=host,
        username=username,
        port=port,
        password=password,
        key_file=key_file,
        key_password=key_password,
    )
