"""Google Cloud Storage file operations.

Requires: google-cloud-storage (pip install pyeff[gcs])

URI Format:
    gs://bucket/path
    gcs:bucket:/path

Example:
    >>> from pyeff.remote.gcs import GCSRemote, gcs
    >>> 
    >>> with gcs("my-bucket") as client:
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
    from google.cloud import storage as gcs_storage
    from google.api_core import exceptions as gcs_exceptions
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    gcs_storage = None
    gcs_exceptions = None


def _check_gcs() -> None:
    if not GCS_AVAILABLE:
        raise ImportError(
            "GCS support requires 'google-cloud-storage' package. "
            "Install with: pip install pyeff[gcs] or pip install google-cloud-storage"
        )


class GCSRemote(RemoteBackend):
    """Google Cloud Storage operations.
    
    Args:
        bucket: GCS bucket name.
        project: Optional GCP project ID.
        credentials_path: Path to service account JSON.
    """
    
    def __init__(
        self,
        bucket: str,
        project: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        _check_gcs()
        self.bucket_name = bucket
        self.project = project
        self.credentials_path = credentials_path
        self._client = None
        self._bucket = None
    
    def __enter__(self) -> "GCSRemote":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            kwargs = {}
            if self.project:
                kwargs["project"] = self.project
            if self.credentials_path:
                os.environ.setdefault(
                    "GOOGLE_APPLICATION_CREDENTIALS",
                    str(Path(self.credentials_path).expanduser()),
                )
            self._client = gcs_storage.Client(**kwargs)
            self._bucket = self._client.bucket(self.bucket_name)
            if not self._bucket.exists():
                raise RemoteConnectionError(f"Bucket not found: {self.bucket_name}")
        except RemoteConnectionError:
            raise
        except Exception as e:
            raise RemoteConnectionError(f"GCS connection failed: {e}") from e
    
    def close(self) -> None:
        self._client = None
        self._bucket = None
    
    @property
    def bucket(self):
        if self._bucket is None:
            self.connect()
        return self._bucket
    
    def _normalize_key(self, key: str) -> str:
        return key.lstrip("/")
    
    def exists(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key:
            return True
        blob = self.bucket.blob(key)
        if blob.exists():
            return True
        prefix = key if key.endswith("/") else key + "/"
        blobs = list(self.bucket.list_blobs(prefix=prefix, max_results=1))
        return len(blobs) > 0
    
    def is_file(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key or key.endswith("/"):
            return False
        return self.bucket.blob(key).exists()
    
    def is_dir(self, remote_path: str) -> bool:
        key = self._normalize_key(remote_path)
        if not key:
            return True
        if self.is_file(remote_path):
            return False
        prefix = key if key.endswith("/") else key + "/"
        blobs = list(self.bucket.list_blobs(prefix=prefix, max_results=1))
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
        
        iterator = self.bucket.list_blobs(prefix=prefix, delimiter="/")
        for page in iterator.pages:
            for blob in page:
                name = blob.name[len(prefix):]
                if not name or "/" in name:
                    continue
                if filter_obj.match(name):
                    results.append(RemoteFileInfo(
                        name=name, path=blob.name, size=blob.size or 0,
                        is_dir=False, is_file=True,
                    ))
            for p in getattr(page, "prefixes", []) or iterator.prefixes:
                name = p[len(prefix):].rstrip("/")
                if name and name not in seen_dirs and filter_obj.match(name):
                    seen_dirs.add(name)
                    results.append(RemoteFileInfo(
                        name=name, path=p.rstrip("/"), size=0,
                        is_dir=True, is_file=False,
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
        kwargs = {"prefix": prefix}
        if not recursive:
            kwargs["delimiter"] = "/"
        
        for blob in self.bucket.list_blobs(**kwargs):
            if blob.name.endswith("/"):
                continue
            if filter_obj.match(PurePosixPath(blob.name).name):
                results.append(blob.name)
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
            self.bucket.blob(key).download_to_filename(str(local))
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
            self.bucket.blob(remote_key).download_to_filename(str(local_file))
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
            self.bucket.blob(key).upload_from_filename(str(local))
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
            self.bucket.blob(key).upload_from_filename(str(local_file))
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
            self.bucket.blob(key).delete()
            return 1
        
        files = self.search(remote_path, mode=mode, patterns=patterns)
        for f in files:
            self.bucket.blob(f).delete()
        return len(files)
    
    def read_text(self, remote_path: str, encoding: str = "utf-8") -> str:
        return self.read_bytes(remote_path).decode(encoding)
    
    def read_bytes(self, remote_path: str) -> bytes:
        key = self._normalize_key(remote_path)
        blob = self.bucket.blob(key)
        if not blob.exists():
            raise RemoteFileNotFoundError(f"File not found: {remote_path}")
        return blob.download_as_bytes()
    
    def write_text(
        self,
        remote_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        self.write_bytes(remote_path, content.encode(encoding))
    
    def write_bytes(self, remote_path: str, content: bytes) -> None:
        key = self._normalize_key(remote_path)
        self.bucket.blob(key).upload_from_string(content)


def gcs(
    bucket: str,
    project: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> GCSRemote:
    """Create a GCS remote interface."""
    return GCSRemote(
        bucket=bucket,
        project=project,
        credentials_path=credentials_path,
    )
