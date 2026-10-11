"""Azure Blob Storage file operations.

Requires: azure-storage-blob (pip install pyeff[azure])

URI Format:
    az://container/blob
    azure:container:/blob

Example:
    >>> from pyeff.remote.azure import AzureRemote, azure
    >>> 
    >>> with azure("my-container", connection_string="...") as client:
    ...     client.copy_from("logs/", "./logs")
    ...     client.copy_to("./data.csv", "uploads/data.csv")
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
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
    from azure.storage.blob import BlobServiceClient, ContainerClient
    from azure.core.exceptions import ResourceNotFoundError, AzureError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    BlobServiceClient = None
    ContainerClient = None
    ResourceNotFoundError = Exception
    AzureError = Exception


def _check_azure() -> None:
    if not AZURE_AVAILABLE:
        raise ImportError(
            "Azure Blob support requires 'azure-storage-blob' package. "
            "Install with: pip install pyeff[azure] or pip install azure-storage-blob"
        )


class AzureRemote(RemoteBackend):
    """Azure Blob Storage operations.
    
    Args:
        container: Blob container name.
        connection_string: Azure Storage connection string.
        account_url: Account URL (alternative to connection_string).
        credential: Credential for account_url auth.
    """
    
    def __init__(
        self,
        container: str,
        connection_string: Optional[str] = None,
        account_url: Optional[str] = None,
        credential: Optional[str] = None,
    ):
        _check_azure()
        self.container_name = container
        self.connection_string = connection_string or os.environ.get(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        self.account_url = account_url
        self.credential = credential
        self._service: Optional[BlobServiceClient] = None
        self._container: Optional[ContainerClient] = None
    
    def __enter__(self) -> "AzureRemote":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def connect(self) -> None:
        if self._container is not None:
            return
        try:
            if self.connection_string:
                self._service = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            elif self.account_url:
                self._service = BlobServiceClient(
                    account_url=self.account_url,
                    credential=self.credential,
                )
            else:
                raise RemoteConnectionError(
                    "Provide connection_string or account_url "
                    "(or set AZURE_STORAGE_CONNECTION_STRING)"
                )
            self._container = self._service.get_container_client(self.container_name)
            if not self._container.exists():
                raise RemoteConnectionError(
                    f"Container not found: {self.container_name}"
                )
        except RemoteConnectionError:
            raise
        except Exception as e:
            raise RemoteConnectionError(f"Azure connection failed: {e}") from e
    
    def close(self) -> None:
        self._service = None
        self._container = None
    
    @property
    def container(self) -> ContainerClient:
        if self._container is None:
            self.connect()
        return self._container
    
    def _normalize_key(self, key: str) -> str:
        return key.lstrip("/")
    
    def exists(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key:
            return True
        blob = self.container.get_blob_client(key)
        if blob.exists():
            return True
        prefix = key if key.endswith("/") else key + "/"
        blobs = list(self.container.list_blobs(name_starts_with=prefix, results_per_page=1))
        return len(blobs) > 0
    
    def is_file(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key or key.endswith("/"):
            return False
        return self.container.get_blob_client(key).exists()
    
    def is_dir(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key:
            return True
        if self.is_file(remote_path):
            return False
        prefix = key if key.endswith("/") else key + "/"
        blobs = list(self.container.list_blobs(name_starts_with=prefix, results_per_page=1))
        return len(blobs) > 0
    
    def listdir(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
    ) -> List[RemoteFileInfo]:
        prefix = self._normalize_key(remote_path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        
        filter_obj = PatternFilter(mode, patterns)
        results: List[RemoteFileInfo] = []
        seen_dirs = set()
        
        for item in self.container.walk_blobs(name_starts_with=prefix, delimiter="/"):
            name = item.name[len(prefix):].rstrip("/")
            if not name or "/" in name.rstrip("/"):
                continue
            if not filter_obj.match(name):
                continue
            
            # BlobPrefix vs BlobProperties
            is_prefix = hasattr(item, "prefix") or item.name.endswith("/")
            if is_prefix:
                if name not in seen_dirs:
                    seen_dirs.add(name)
                    results.append(RemoteFileInfo(
                        name=name, path=item.name.rstrip("/"), size=0,
                        is_dir=True, is_file=False,
                    ))
            else:
                results.append(RemoteFileInfo(
                    name=name, path=item.name,
                    size=getattr(item, "size", 0) or 0,
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
        prefix = self._normalize_key(remote_path)
        if prefix and not prefix.endswith("/") and self.is_dir(remote_path):
            prefix += "/"
        
        filter_obj = PatternFilter(mode, patterns)
        
        if prefix and not prefix.endswith("/") and self.is_file(remote_path):
            if filter_obj.match(PurePosixPath(prefix).name):
                return [prefix]
            return []
        
        results = []
        if recursive:
            blobs = self.container.list_blobs(name_starts_with=prefix)
        else:
            blobs = self.container.walk_blobs(name_starts_with=prefix, delimiter="/")
        
        for blob in blobs:
            name = getattr(blob, "name", "")
            if not name or name.endswith("/"):
                continue
            if not recursive and "/" in name[len(prefix):]:
                continue
            if filter_obj.match(PurePosixPath(name).name):
                results.append(name)
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
        key = self._normalize_key(remote_path)
        
        if self.is_file(remote_path):
            local.parent.mkdir(parents=True, exist_ok=True)
            if local.is_dir():
                local = local / PurePosixPath(key).name
            with open(local, "wb") as f:
                stream = self.container.download_blob(key)
                f.write(stream.readall())
            if progress:
                progress(key, 1, 1)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        if not files:
            if not self.exists(remote_path):
                raise RemoteFileNotFoundError(f"Path not found: {remote_path}")
            return 0
        
        total = len(files)
        count = 0
        base = key.rstrip("/")
        
        for remote_key in files:
            if base and remote_key.startswith(base + "/"):
                rel = remote_key[len(base) + 1:]
            else:
                rel = PurePosixPath(remote_key).name
            local_file = local / rel
            local_file.parent.mkdir(parents=True, exist_ok=True)
            with open(local_file, "wb") as f:
                stream = self.container.download_blob(remote_key)
                f.write(stream.readall())
            count += 1
            if progress:
                progress(remote_key, count, total)
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
        
        dest = self._normalize_key(remote_path)
        
        if local.is_file():
            key = dest
            if dest.endswith("/") or (dest and self.is_dir(remote_path)):
                key = f"{dest.rstrip('/')}/{local.name}"
            with open(local, "rb") as f:
                self.container.upload_blob(key, f, overwrite=True)
            if progress:
                progress(str(local), 1, 1)
            return 1
        
        filter_obj = PatternFilter(mode, patterns)
        files_to_upload: List[Tuple[Path, str]] = []
        
        for root, dirs, files in os.walk(local):
            for file in files:
                file_path = Path(root) / file
                rel = file_path.relative_to(local)
                if filter_obj.match(str(rel)):
                    key = f"{dest.rstrip('/')}/{rel}" if dest else str(rel)
                    key = key.replace("\\", "/")
                    files_to_upload.append((file_path, key))
        
        total = len(files_to_upload)
        count = 0
        for local_file, key in files_to_upload:
            with open(local_file, "rb") as f:
                self.container.upload_blob(key, f, overwrite=True)
            count += 1
            if progress:
                progress(str(local_file), count, total)
        return count
    
    def remove(
        self,
        remote_path: str,
        mode: Mode = "all",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> int:
        key = self._normalize_key(remote_path)
        if self.is_file(remote_path):
            self.container.delete_blob(key)
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        for f in files:
            self.container.delete_blob(f)
        return len(files)
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(remote_path).decode(encoding)
    
    def read_bytes(self, remote_path: str) -> bytes:
        key = self._normalize_key(remote_path)
        try:
            return self.container.download_blob(key).readall()
        except ResourceNotFoundError as e:
            raise RemoteFileNotFoundError(f"File not found: {remote_path}") from e
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        self.write_bytes(remote_path, content.encode(encoding))
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        key = self._normalize_key(remote_path)
        self.container.upload_blob(key, content, overwrite=True)


def azure(
    container: str,
    connection_string: Optional[str] = None,
    account_url: Optional[str] = None,
    credential: Optional[str] = None,
) -> AzureRemote:
    """Create an Azure Blob Storage remote interface."""
    return AzureRemote(
        container=container,
        connection_string=connection_string,
        account_url=account_url,
        credential=credential,
    )
