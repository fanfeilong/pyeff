"""HTTP(S) file operations.

Uses stdlib urllib — no extra dependencies.

URI Format:
    http://host/path
    https://host/path

Example:
    >>> from pyeff.remote.http import HTTPRemote, http
    >>> 
    >>> with http("https://example.com") as h:
    ...     h.copy_from("/file.zip", "./file.zip")
    ...     content = h.read_text("/data.json")
    >>> 
    >>> # Or operate on a full URL directly via unified ops:
    >>> from pyeff import copy, read
    >>> copy("https://example.com/file.zip", "local:./file.zip")
    >>> data = read("https://example.com/api/data.json")
"""

from __future__ import annotations

import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Union
from urllib.parse import urljoin, urlparse

from .base import (
    Mode,
    PathLike,
    ProgressCallback,
    RemoteBackend,
    RemoteConnectionError,
    RemoteError,
    RemoteFileInfo,
    RemoteFileNotFoundError,
    RemotePermissionError,
)


class HTTPRemote(RemoteBackend):
    """HTTP(S) remote file operations.
    
    Designed primarily for downloading/uploading individual files.
    Directory listing is not supported (servers vary widely).
    
    Args:
        base_url: Base URL (e.g. "https://example.com" or full file URL).
        timeout: Request timeout in seconds.
        headers: Optional HTTP headers.
        
    Example:
        >>> with HTTPRemote("https://cdn.example.com") as h:
        ...     h.copy_from("/releases/app.tar.gz", "./app.tar.gz")
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 60.0,
        headers: Optional[dict] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}
    
    def __enter__(self) -> "HTTPRemote":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
    
    def _url(self, remote_path: str) -> str:
        """Build full URL from path."""
        if remote_path.startswith("http://") or remote_path.startswith("https://"):
            return remote_path
        if not remote_path.startswith("/"):
            remote_path = "/" + remote_path
        return urljoin(self.base_url + "/", remote_path.lstrip("/"))
    
    def _request(
        self,
        url: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[dict] = None,
    ) -> urllib.request.addinfourl:
        """Make HTTP request."""
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
        
        request = urllib.request.Request(
            url, data=data, headers=req_headers, method=method
        )
        try:
            return urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RemoteFileNotFoundError(f"Not found: {url}") from e
            if e.code in (401, 403):
                raise RemotePermissionError(f"Permission denied: {url}") from e
            raise RemoteError(f"HTTP {e.code}: {url}") from e
        except urllib.error.URLError as e:
            raise RemoteConnectionError(f"Connection failed: {e.reason}") from e
    
    def exists(self, remote_path: str) -> bool:
        url = self._url(remote_path)
        try:
            with self._request(url, method="HEAD"):
                return True
        except (RemoteFileNotFoundError, RemoteError):
            # Some servers don't support HEAD — try GET range
            try:
                with self._request(
                    url, method="GET",
                    headers={"Range": "bytes=0-0"},
                ):
                    return True
            except RemoteFileNotFoundError:
                return False
            except RemoteError:
                return False
    
    def is_file(self, remote_path: str) -> bool:
        return self.exists(remote_path)
    
    def is_dir(self, remote_path: str) -> bool:
        return False  # HTTP paths are treated as files
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        raise RemoteError(
            "listdir is not supported for HTTP. "
            "Use copy/read with a specific URL."
        )
    
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        if self.exists(remote_path):
            return [remote_path]
        return []
    
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Download URL to local file."""
        url = self._url(remote_path)
        local = Path(local_path)
        
        with self._request(url, method="GET") as resp:
            # If local is a directory, use filename from URL
            if local.is_dir() or str(local_path).endswith(("/", os.sep)):
                local.mkdir(parents=True, exist_ok=True)
                name = Path(urlparse(url).path).name or "download"
                local = local / name
            else:
                local.parent.mkdir(parents=True, exist_ok=True)
            
            total_size = resp.headers.get("Content-Length")
            total = int(total_size) if total_size else 0
            written = 0
            
            with open(local, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
                    if progress:
                        progress(url, written, total or written)
        
        return 1
    
    def copy_to(
        self,
        local_path: PathLike,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Upload local file via HTTP PUT."""
        local = Path(local_path)
        if not local.is_file():
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        url = self._url(remote_path)
        data = local.read_bytes()
        content_type = mimetypes.guess_type(str(local))[0] or "application/octet-stream"
        
        with self._request(
            url, method="PUT", data=data,
            headers={"Content-Type": content_type},
        ):
            pass
        
        if progress:
            progress(str(local), 1, 1)
        return 1
    
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        """Delete via HTTP DELETE."""
        url = self._url(remote_path)
        try:
            with self._request(url, method="DELETE"):
                return 1
        except RemoteFileNotFoundError:
            return 0
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(remote_path).decode(encoding)
    
    def read_bytes(self, remote_path: str) -> bytes:
        url = self._url(remote_path)
        with self._request(url, method="GET") as resp:
            return resp.read()
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        self.write_bytes(remote_path, content.encode(encoding))
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        url = self._url(remote_path)
        with self._request(
            url, method="PUT", data=content,
            headers={"Content-Type": "application/octet-stream"},
        ):
            pass


def http(
    base_url: str,
    timeout: float = 60.0,
    headers: Optional[dict] = None,
) -> HTTPRemote:
    """Create an HTTP(S) remote interface.
    
    Example:
        >>> with http("https://cdn.example.com") as h:
        ...     h.copy_from("/file.zip", "./file.zip")
    """
    return HTTPRemote(base_url=base_url, timeout=timeout, headers=headers)


def http_download(url: str, local_path: PathLike, timeout: float = 60.0) -> int:
    """Download a URL to a local path.
    
    Example:
        >>> http_download("https://example.com/file.zip", "./file.zip")
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query
    
    with HTTPRemote(base, timeout=timeout) as h:
        return h.copy_from(path, local_path)
