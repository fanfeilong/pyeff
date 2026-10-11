"""SMB/CIFS (NAS) file operations.

Requires: smbprotocol (pip install pyeff[smb])

URI Format:
    smb://host/share/path
    smb:host/share:/path

Example:
    >>> from pyeff.remote.smb import SMBRemote, smb
    >>> 
    >>> with smb("nas.local", "shared", username="user", password="pass") as s:
    ...     s.copy_from("docs/", "./docs")
    ...     s.copy_to("./file.txt", "uploads/file.txt")
"""

from __future__ import annotations

import os
import stat as stat_mod
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import List, Optional, Tuple

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

try:
    import smbclient
    from smbprotocol.exceptions import SMBOSError, SMBException
    SMB_AVAILABLE = True
except ImportError:
    SMB_AVAILABLE = False
    smbclient = None
    SMBOSError = OSError
    SMBException = Exception


def _check_smb() -> None:
    if not SMB_AVAILABLE:
        raise ImportError(
            "SMB support requires 'smbprotocol' package. "
            "Install with: pip install pyeff[smb] or pip install smbprotocol"
        )


class SMBRemote(RemoteBackend):
    """SMB/CIFS remote file operations for NAS / Windows shares.
    
    Args:
        host: SMB server hostname or IP.
        share: Share name.
        username: SMB username.
        password: SMB password.
        port: SMB port (default 445).
        domain: Optional domain / workgroup.
    """
    
    def __init__(
        self,
        host: str,
        share: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        port: int = 445,
        domain: Optional[str] = None,
    ):
        _check_smb()
        self.host = host
        self.share = share.strip("/\\")
        self.username = username
        self.password = password
        self.port = port
        self.domain = domain
        self._registered = False
    
    def __enter__(self) -> "SMBRemote":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def connect(self) -> None:
        if self._registered:
            return
        try:
            kwargs = {
                "username": self.username,
                "password": self.password,
                "port": self.port,
            }
            if self.domain:
                kwargs["connection_timeout"] = 60
            smbclient.register_session(
                self.host,
                username=self.username,
                password=self.password,
                port=self.port,
            )
            # Verify share is accessible
            smbclient.listdir(self._unc(""))
            self._registered = True
        except Exception as e:
            raise RemoteConnectionError(f"SMB connection failed: {e}") from e
    
    def close(self) -> None:
        if self._registered and SMB_AVAILABLE:
            try:
                smbclient.delete_session(self.host)
            except Exception:
                pass
            self._registered = False
    
    def _unc(self, remote_path: str) -> str:
        """Build UNC path: \\\\host\\share\\path."""
        path = remote_path.replace("/", "\\").lstrip("\\")
        base = f"\\\\{self.host}\\{self.share}"
        return f"{base}\\{path}" if path else base
    
    def _norm(self, remote_path: str) -> str:
        return remote_path.replace("\\", "/").strip("/")
    
    def exists(self, remote_path: str) -> bool:
        self.connect()
        try:
            smbclient.stat(self._unc(remote_path))
            return True
        except (OSError, SMBOSError, SMBException):
            return False
    
    def is_file(self, remote_path: str) -> bool:
        self.connect()
        try:
            st = smbclient.stat(self._unc(remote_path))
            return stat_mod.S_ISREG(st.st_mode)
        except (OSError, SMBOSError, SMBException):
            return False
    
    def is_dir(self, remote_path: str) -> bool:
        self.connect()
        try:
            st = smbclient.stat(self._unc(remote_path))
            return stat_mod.S_ISDIR(st.st_mode)
        except (OSError, SMBOSError, SMBException):
            return False
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        self.connect()
        unc = self._unc(remote_path)
        try:
            names = smbclient.listdir(unc)
        except (OSError, SMBOSError, SMBException) as e:
            raise RemoteFileNotFoundError(f"Directory not found: {remote_path}") from e
        
        filter_obj = PatternFilter(mode, patterns)
        results: List[RemoteFileInfo] = []
        base = self._norm(remote_path)
        
        for name in names:
            if name in (".", ".."):
                continue
            if not filter_obj.match(name):
                continue
            child = f"{base}/{name}" if base else name
            try:
                st = smbclient.stat(self._unc(child))
                is_dir = stat_mod.S_ISDIR(st.st_mode)
                results.append(RemoteFileInfo(
                    name=name,
                    path=child,
                    size=st.st_size if not is_dir else 0,
                    is_dir=is_dir,
                    is_file=not is_dir,
                ))
            except (OSError, SMBOSError, SMBException):
                results.append(RemoteFileInfo(
                    name=name, path=child, size=0,
                    is_dir=False, is_file=True,
                ))
        return results
    
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        self.connect()
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        filter_obj = PatternFilter(mode, patterns)
        
        if self.is_file(remote_path):
            name = PurePosixPath(self._norm(remote_path)).name
            return [self._norm(remote_path)] if filter_obj.match(name) else []
        
        results: List[str] = []
        
        def _walk(path: str) -> None:
            try:
                for info in self.listdir(path):
                    if info.is_dir:
                        if recursive:
                            _walk(info.path)
                    elif filter_obj.match(info.name):
                        results.append(info.path)
            except RemoteFileNotFoundError:
                pass
        
        _walk(self._norm(remote_path))
        return results
    
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        self.connect()
        local = Path(local_path)
        
        if self.is_file(remote_path):
            local.parent.mkdir(parents=True, exist_ok=True)
            if local.is_dir():
                local = local / PurePosixPath(self._norm(remote_path)).name
            with smbclient.open_file(self._unc(remote_path), mode="rb") as src:
                local.write_bytes(src.read())
            if progress:
                progress(remote_path, 1, 1)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        total = len(files)
        count = 0
        base = self._norm(remote_path)
        
        for remote_file in files:
            if base and remote_file.startswith(base + "/"):
                rel = remote_file[len(base) + 1:]
            else:
                rel = PurePosixPath(remote_file).name
            local_file = local / rel
            local_file.parent.mkdir(parents=True, exist_ok=True)
            with smbclient.open_file(self._unc(remote_file), mode="rb") as src:
                local_file.write_bytes(src.read())
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
        self.connect()
        local = Path(local_path)
        if not local.exists():
            raise FileNotFoundError(f"Local path not found: {local_path}")
        
        dest = self._norm(remote_path)
        
        if local.is_file():
            key = dest
            if dest.endswith("/") or (dest and self.is_dir(remote_path)):
                key = f"{dest.rstrip('/')}/{local.name}"
            parent = str(PurePosixPath(key).parent)
            if parent and parent != ".":
                self._mkdir_p(parent)
            with smbclient.open_file(self._unc(key), mode="wb") as dst:
                dst.write(local.read_bytes())
            if progress:
                progress(str(local), 1, 1)
            return 1
        
        filter_obj = PatternFilter(mode, patterns)
        files_to_copy: List[Tuple[Path, str]] = []
        
        for root, dirs, files in os.walk(local):
            for file in files:
                file_path = Path(root) / file
                rel = file_path.relative_to(local)
                if filter_obj.match(str(rel)):
                    remote_file = f"{dest}/{rel}".replace("\\", "/") if dest else str(rel).replace("\\", "/")
                    files_to_copy.append((file_path, remote_file))
        
        total = len(files_to_copy)
        count = 0
        for local_file, remote_file in files_to_copy:
            parent = str(PurePosixPath(remote_file).parent)
            if parent and parent != ".":
                self._mkdir_p(parent)
            with smbclient.open_file(self._unc(remote_file), mode="wb") as dst:
                dst.write(local_file.read_bytes())
            count += 1
            if progress:
                progress(str(local_file), count, total)
        return count
    
    def _mkdir_p(self, remote_path: str) -> None:
        parts = self._norm(remote_path).split("/")
        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            if not self.exists(current):
                try:
                    smbclient.mkdir(self._unc(current))
                except (OSError, SMBOSError, SMBException):
                    pass
    
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        self.connect()
        if not self.exists(remote_path):
            return 0
        
        if self.is_file(remote_path):
            smbclient.remove(self._unc(remote_path))
            return 1
        
        if mode == "all" and not patterns and recursive:
            self._rmtree(self._norm(remote_path))
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        for f in files:
            try:
                smbclient.remove(self._unc(f))
            except (OSError, SMBOSError, SMBException):
                pass
        return len(files)
    
    def _rmtree(self, remote_path: str) -> None:
        for info in self.listdir(remote_path):
            if info.is_dir:
                self._rmtree(info.path)
            else:
                smbclient.remove(self._unc(info.path))
        smbclient.rmdir(self._unc(remote_path))
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(remote_path).decode(encoding)
    
    def read_bytes(self, remote_path: str) -> bytes:
        self.connect()
        if not self.is_file(remote_path):
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        with smbclient.open_file(self._unc(remote_path), mode="rb") as f:
            return f.read()
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        self.write_bytes(remote_path, content.encode(encoding))
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        self.connect()
        key = self._norm(remote_path)
        parent = str(PurePosixPath(key).parent)
        if parent and parent != ".":
            self._mkdir_p(parent)
        with smbclient.open_file(self._unc(key), mode="wb") as f:
            f.write(content)


def smb(
    host: str,
    share: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    port: int = 445,
    domain: Optional[str] = None,
) -> SMBRemote:
    """Create an SMB/CIFS remote interface.
    
    Example:
        >>> with smb("nas.local", "shared", username="user", password="pass") as s:
        ...     s.copy_from("docs/", "./docs")
    """
    return SMBRemote(
        host=host,
        share=share,
        username=username,
        password=password,
        port=port,
        domain=domain,
    )
