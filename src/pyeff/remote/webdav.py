"""WebDAV (NAS / Nextcloud / Synology) file operations.

Uses stdlib urllib + xml — no extra dependencies.
Supports HTTP and HTTPS WebDAV endpoints.

URI Format:
    webdav://host/path
    webdavs://host/path   (HTTPS)
    dav://host/path
    davs://host/path

Example:
    >>> from pyeff.remote.webdav import WebDAVRemote, webdav
    >>> 
    >>> with webdav("https://nas.local/remote.php/dav/files/user",
    ...             username="user", password="pass") as w:
    ...     w.copy_from("Documents/", "./docs")
    ...     w.copy_to("./file.txt", "Uploads/file.txt")
"""

from __future__ import annotations

import base64
import mimetypes
import os
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urljoin, urlparse

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

# WebDAV XML namespaces
_DAV_NS = {"d": "DAV:"}


class WebDAVRemote(RemoteBackend):
    """WebDAV remote file operations.
    
    Args:
        base_url: WebDAV base URL (e.g. https://nas/webdav or
                  https://cloud/remote.php/dav/files/user).
        username: Optional basic-auth username.
        password: Optional basic-auth password.
        timeout: Request timeout in seconds.
        verify_ssl: Whether to verify TLS certificates.
    """
    
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 60.0,
        verify_ssl: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.headers = headers or {}
    
    def __enter__(self) -> "WebDAVRemote":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
    
    def connect(self) -> None:
        """Verify WebDAV endpoint is reachable (best-effort)."""
        try:
            with self._request("", method="PROPFIND", headers={"Depth": "0"}):
                pass
        except RemoteFileNotFoundError:
            pass
        except RemotePermissionError:
            raise
        except RemoteError:
            try:
                with self._request("", method="OPTIONS"):
                    pass
            except Exception as e:
                raise RemoteConnectionError(f"WebDAV connection failed: {e}") from e
    
    def _auth_header(self) -> Dict[str, str]:
        if not self.username:
            return {}
        token = base64.b64encode(
            f"{self.username}:{self.password or ''}".encode()
        ).decode()
        return {"Authorization": f"Basic {token}"}
    
    def _url(self, remote_path: str) -> str:
        if remote_path.startswith("http://") or remote_path.startswith("https://"):
            return remote_path
        path = remote_path.lstrip("/")
        # Quote each segment but keep slashes
        parts = [quote(p, safe="") for p in path.split("/") if p]
        encoded = "/".join(parts)
        return urljoin(self.base_url, encoded)
    
    def _request(
        self,
        remote_path: str,
        method: str = "GET",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        url = self._url(remote_path)
        req_headers = dict(self.headers)
        req_headers.update(self._auth_header())
        if headers:
            req_headers.update(headers)
        
        request = urllib.request.Request(
            url, data=data, headers=req_headers, method=method
        )
        
        context = None
        if url.startswith("https://") and not self.verify_ssl:
            context = ssl._create_unverified_context()
        
        try:
            return urllib.request.urlopen(
                request, timeout=self.timeout, context=context
            )
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RemoteFileNotFoundError(f"Not found: {remote_path}") from e
            if e.code in (401, 403):
                raise RemotePermissionError(f"Permission denied: {remote_path}") from e
            # 207 Multi-Status is success for PROPFIND
            if e.code == 207:
                return e
            raise RemoteError(f"WebDAV HTTP {e.code}: {remote_path}") from e
        except urllib.error.URLError as e:
            raise RemoteConnectionError(f"Connection failed: {e.reason}") from e
    
    def _propfind(self, remote_path: str, depth: str = "1") -> List[dict]:
        """PROPFIND and parse multistatus response."""
        body = (
            b'<?xml version="1.0" encoding="utf-8"?>'
            b'<d:propfind xmlns:d="DAV:">'
            b'<d:prop><d:displayname/><d:getcontentlength/>'
            b'<d:resourcetype/><d:getlastmodified/></d:prop>'
            b'</d:propfind>'
        )
        resp = self._request(
            remote_path,
            method="PROPFIND",
            data=body,
            headers={
                "Depth": depth,
                "Content-Type": "application/xml; charset=utf-8",
            },
        )
        with resp:
            xml_data = resp.read()
        
        return self._parse_propfind(xml_data, remote_path)
    
    def _parse_propfind(self, xml_data: bytes, request_path: str) -> List[dict]:
        results = []
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            raise RemoteError(f"Invalid WebDAV PROPFIND response: {e}") from e
        
        base_parsed = urlparse(self.base_url)
        base_path = base_parsed.path.rstrip("/")
        
        for resp in root.findall("d:response", _DAV_NS):
            href_el = resp.find("d:href", _DAV_NS)
            if href_el is None or not href_el.text:
                continue
            href = unquote(href_el.text)
            
            # Convert href to path relative to base_url
            if href.startswith("http"):
                href_path = urlparse(href).path
            else:
                href_path = href
            
            if base_path and href_path.startswith(base_path):
                rel = href_path[len(base_path):].lstrip("/")
            else:
                rel = href_path.lstrip("/")
            
            rel = rel.rstrip("/")
            
            propstat = resp.find("d:propstat", _DAV_NS)
            if propstat is None:
                continue
            prop = propstat.find("d:prop", _DAV_NS)
            if prop is None:
                continue
            
            resourcetype = prop.find("d:resourcetype", _DAV_NS)
            is_dir = (
                resourcetype is not None
                and resourcetype.find("d:collection", _DAV_NS) is not None
            )
            
            size_el = prop.find("d:getcontentlength", _DAV_NS)
            size = int(size_el.text) if size_el is not None and size_el.text else 0
            
            name_el = prop.find("d:displayname", _DAV_NS)
            name = name_el.text if name_el is not None and name_el.text else (
                PurePosixPath(rel).name if rel else ""
            )
            
            results.append({
                "path": rel,
                "name": name,
                "is_dir": is_dir,
                "size": size,
            })
        
        return results
    
    def exists(self, remote_path: str) -> bool:
        try:
            self._propfind(remote_path, depth="0")
            return True
        except RemoteFileNotFoundError:
            return False
        except RemoteError:
            # Fallback HEAD/GET
            try:
                with self._request(remote_path, method="HEAD"):
                    return True
            except RemoteFileNotFoundError:
                return False
            except RemoteError:
                return False
    
    def is_file(self, remote_path: str) -> bool:
        try:
            items = self._propfind(remote_path, depth="0")
            if not items:
                return False
            return not items[0]["is_dir"]
        except RemoteFileNotFoundError:
            return False
    
    def is_dir(self, remote_path: str) -> bool:
        path = remote_path.strip("/")
        if not path:
            return True
        try:
            items = self._propfind(remote_path, depth="0")
            if not items:
                return False
            return items[0]["is_dir"]
        except RemoteFileNotFoundError:
            return False
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        items = self._propfind(remote_path, depth="1")
        filter_obj = PatternFilter(mode, patterns)
        base = remote_path.strip("/")
        results: List[RemoteFileInfo] = []
        
        for item in items:
            # Skip self
            if item["path"].rstrip("/") == base:
                continue
            name = item["name"] or PurePosixPath(item["path"]).name
            if not name or not filter_obj.match(name):
                continue
            results.append(RemoteFileInfo(
                name=name,
                path=item["path"],
                size=item["size"],
                is_dir=item["is_dir"],
                is_file=not item["is_dir"],
            ))
        return results
    
    def search(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> List[str]:
        if not self.exists(remote_path):
            raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
        
        filter_obj = PatternFilter(mode, patterns)
        
        if self.is_file(remote_path):
            name = PurePosixPath(remote_path.rstrip("/")).name
            return [remote_path.strip("/")] if filter_obj.match(name) else []
        
        depth = "infinity" if recursive else "1"
        try:
            items = self._propfind(remote_path, depth=depth)
        except RemoteError:
            # Server may reject Depth: infinity — fall back to recursive walk
            return self._search_walk(remote_path, filter_obj, recursive)
        
        base = remote_path.strip("/")
        results = []
        for item in items:
            if item["is_dir"]:
                continue
            if item["path"].rstrip("/") == base:
                continue
            name = item["name"] or PurePosixPath(item["path"]).name
            if filter_obj.match(name):
                results.append(item["path"])
        return results
    
    def _search_walk(
        self,
        remote_path: str,
        filter_obj: PatternFilter,
        recursive: bool,
    ) -> List[str]:
        results = []
        for info in self.listdir(remote_path):
            if info.is_dir:
                if recursive:
                    results.extend(
                        self._search_walk(info.path, filter_obj, recursive)
                    )
            elif filter_obj.match(info.name):
                results.append(info.path)
        return results
    
    def copy_from(
        self,
        remote_path: str,
        local_path: PathLike,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        local = Path(local_path)
        
        if self.is_file(remote_path):
            local.parent.mkdir(parents=True, exist_ok=True)
            if local.is_dir() or str(local_path).endswith(("/", os.sep)):
                local.mkdir(parents=True, exist_ok=True)
                local = local / PurePosixPath(remote_path.rstrip("/")).name
            with self._request(remote_path, method="GET") as resp:
                local.write_bytes(resp.read())
            if progress:
                progress(remote_path, 1, 1)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        total = len(files)
        count = 0
        base = remote_path.strip("/")
        
        for remote_file in files:
            if base and remote_file.startswith(base + "/"):
                rel = remote_file[len(base) + 1:]
            else:
                rel = PurePosixPath(remote_file).name
            local_file = local / rel
            local_file.parent.mkdir(parents=True, exist_ok=True)
            with self._request(remote_file, method="GET") as resp:
                local_file.write_bytes(resp.read())
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
        local = Path(local_path)
        if not local.exists():
            raise FileNotFoundError(f"Local path not found: {local_path}")
        
        dest = remote_path.strip("/")
        
        if local.is_file():
            key = dest
            if dest.endswith("/") or (dest and self.is_dir(remote_path)):
                key = f"{dest.rstrip('/')}/{local.name}"
            parent = str(PurePosixPath(key).parent)
            if parent and parent != ".":
                self._mkdir_p(parent)
            content_type = (
                mimetypes.guess_type(str(local))[0] or "application/octet-stream"
            )
            with self._request(
                key, method="PUT", data=local.read_bytes(),
                headers={"Content-Type": content_type},
            ):
                pass
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
                    remote_file = (
                        f"{dest}/{rel}".replace("\\", "/")
                        if dest else str(rel).replace("\\", "/")
                    )
                    files_to_copy.append((file_path, remote_file))
        
        total = len(files_to_copy)
        count = 0
        for local_file, remote_file in files_to_copy:
            parent = str(PurePosixPath(remote_file).parent)
            if parent and parent != ".":
                self._mkdir_p(parent)
            content_type = (
                mimetypes.guess_type(str(local_file))[0]
                or "application/octet-stream"
            )
            with self._request(
                remote_file, method="PUT", data=local_file.read_bytes(),
                headers={"Content-Type": content_type},
            ):
                pass
            count += 1
            if progress:
                progress(str(local_file), count, total)
        return count
    
    def _mkdir_p(self, remote_path: str) -> None:
        parts = remote_path.strip("/").split("/")
        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            if not self.exists(current):
                try:
                    with self._request(current, method="MKCOL"):
                        pass
                except RemoteError:
                    pass
    
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        if not self.exists(remote_path):
            return 0
        
        if self.is_file(remote_path) or (mode == "all" and not patterns):
            try:
                with self._request(remote_path, method="DELETE"):
                    return 1
            except RemoteFileNotFoundError:
                return 0
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        count = 0
        for f in files:
            try:
                with self._request(f, method="DELETE"):
                    count += 1
            except RemoteError:
                pass
        return count
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(remote_path).decode(encoding)
    
    def read_bytes(self, remote_path: str) -> bytes:
        with self._request(remote_path, method="GET") as resp:
            return resp.read()
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        self.write_bytes(remote_path, content.encode(encoding))
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        key = remote_path.strip("/")
        parent = str(PurePosixPath(key).parent)
        if parent and parent != ".":
            self._mkdir_p(parent)
        with self._request(
            key, method="PUT", data=content,
            headers={"Content-Type": "application/octet-stream"},
        ):
            pass


def webdav(
    base_url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: float = 60.0,
    verify_ssl: bool = True,
    headers: Optional[Dict[str, str]] = None,
) -> WebDAVRemote:
    """Create a WebDAV remote interface.
    
    Example:
        >>> with webdav("https://nas.local/webdav",
        ...             username="user", password="pass") as w:
        ...     w.copy_from("docs/", "./docs")
    """
    return WebDAVRemote(
        base_url=base_url,
        username=username,
        password=password,
        timeout=timeout,
        verify_ssl=verify_ssl,
        headers=headers,
    )
